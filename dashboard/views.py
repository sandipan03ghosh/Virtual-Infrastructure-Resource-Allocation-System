import logging
import os
from datetime import datetime
from pathlib import Path
from random import randint

from dotenv import set_key
from google import genai

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import analytics
from .decorators import staff_or_manager_required
from .exceptions import InsufficientResourceError, InvalidTransitionError
from .forms import (
    DatabaseResourceCapacityForm,
    DatabaseResourceForm,
    InformationForm,
    TransactionSessionForm,
    TransactionStateForm,
)
from .models import CATEGORY, DatabaseResource, DatabaseTransaction, Information
from .services import TransactionService

logger = logging.getLogger(__name__)

GOOGLE_API_KEY_ENV = 'GOOGLE_API_KEY'
ENV_PATH = Path(__file__).resolve().parent.parent / '.env'


@login_required
def index(request):
    resources = DatabaseResource.objects.filter(is_active=True)
    orders = DatabaseTransaction.objects.filter(status='COMMITTED')
    workers = User.objects.filter(is_superuser=False, is_staff=True)
    information = Information.objects.first()
    capacity_total, capacity_allocated = analytics.capacity_totals()

    context = {
        'orders': orders,
        'pending_transactions': DatabaseTransaction.objects.filter(status='CREATED', staff=request.user).count(),
        'form': TransactionSessionForm(),
        'resources': resources,
        'workers_count': workers.count(),
        'orders_count': DatabaseTransaction.objects.count(),
        'resources_count': resources.count(),
        'information_content': information.content if information else "",
        'transaction_counts': analytics.transaction_state_counts(),
        'throughput_24h': analytics.throughput(),
        'avg_commit_time': analytics.average_commit_time(),
        'resource_utilization': analytics.resource_utilization(),
        'capacity_total': capacity_total,
        'capacity_allocated': capacity_allocated,
        'capacity_available': capacity_total - capacity_allocated,
        'success_rate': analytics.success_rate(),
        'failure_rate': analytics.failure_rate(),
        'rollback_rate': analytics.rollback_rate(),
    }
    return render(request, 'dashboard/index.html', context)


@login_required
def create_transaction(request):
    if request.method == 'POST':
        form = TransactionSessionForm(request.POST)
        if form.is_valid():
            resource = form.cleaned_data['resource']
            units = form.cleaned_data['requested_units']
            try:
                TransactionService.create(resource, request.user, units)
                messages.success(request, 'Added to transaction session successfully')
            except InsufficientResourceError as exc:
                messages.error(request, str(exc))
    return redirect('dashboard-index')


@login_required
def transaction_session(request):
    session_transactions = DatabaseTransaction.objects.filter(status='CREATED', staff=request.user)
    context = {
        'session_transactions': session_transactions,
        'session_count': session_transactions.count(),
    }
    return render(request, 'dashboard/transaction_session.html', context)


@login_required
def submit_for_validation(request):
    session_transactions = DatabaseTransaction.objects.filter(status='CREATED', staff=request.user)
    for txn in session_transactions:
        TransactionService.transition(txn, 'PENDING', request.user, note='Submitted to counter')

    context = {
        'counter_orders': DatabaseTransaction.objects.filter(status='PENDING').count(),
        'accepted_orders': DatabaseTransaction.objects.filter(status='VALIDATED'),
    }
    return render(request, 'dashboard/validation_queue.html', context)


@login_required
def validation_queue(request):
    context = {
        'counter_orders': DatabaseTransaction.objects.filter(status='PENDING').count(),
        'accepted_orders': DatabaseTransaction.objects.filter(status='VALIDATED'),
    }
    return render(request, 'dashboard/validation_queue.html', context)


def compute_total_units(transactions):
    return sum((txn.requested_units or 0) for txn in transactions)


@login_required
def review_commit(request):
    validated_transactions = DatabaseTransaction.objects.filter(status='VALIDATED', staff=request.user)
    total_units = compute_total_units(validated_transactions)
    context = {
        'total_units': total_units,
    }
    return render(request, 'dashboard/review_commit.html', context)


@login_required
@require_POST
def commit_transactions(request):
    validated_transactions = list(DatabaseTransaction.objects.filter(status='VALIDATED', staff=request.user))
    total_units = compute_total_units(validated_transactions)

    committed_ids = []
    for txn in validated_transactions:
        try:
            TransactionService.commit(txn, request.user)
            committed_ids.append(txn.pk)
        except Exception:
            messages.error(request, f'Transaction #{txn.pk} failed to commit and was marked FAILED')

    allocation_ref = f'{datetime.now().strftime("%Y%m%d%H%M%S")}{randint(1000, 9999)}'
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    context = {
        'committed_transactions': DatabaseTransaction.objects.filter(pk__in=committed_ids),
        'total_units': total_units,
        'date': date,
        'allocation_ref': allocation_ref,
    }
    return render(request, 'dashboard/transaction_receipt.html', context)


@login_required
def rollback_transaction(request, resource_id):
    txn = DatabaseTransaction.objects.filter(resource_id=resource_id, staff=request.user, status='CREATED').first()
    if txn:
        TransactionService.rollback(txn, request.user, reason='Removed from transaction session')
    return redirect('transaction-session')


@login_required
def rollback_all_transactions(request):
    session_transactions = DatabaseTransaction.objects.filter(staff=request.user, status='CREATED')
    for txn in session_transactions:
        TransactionService.rollback(txn, request.user, reason='Transaction session cleared')
    return redirect('transaction-session')


@staff_or_manager_required
def resource_list(request):
    items = DatabaseResource.objects.all()
    info = Information.objects.first() if Information.objects.exists() else ""
    workers = User.objects.filter(is_superuser=False, is_staff=True)

    if request.method == 'POST':
        form = DatabaseResourceForm(request.POST)
        if form.is_valid():
            resource = form.save()

            messages.success(request, f'{resource.name} has been added successfully')
            return redirect('dashboard-resource')
    form = DatabaseResourceForm()

    context = {
        'information_content': info,
        'items': items,
        'form': form,
        'workers_count': workers.count(),
        'orders_count': DatabaseTransaction.objects.count(),
        'resources_count': items.count(),
    }
    return render(request, 'dashboard/resource.html', context)


@staff_or_manager_required
def resource_delete(request, pk):
    item = DatabaseResource.objects.get(id=pk)
    if request.method == 'POST':
        item.is_active = False
        item.save(update_fields=['is_active'])
        return redirect('dashboard-resource')
    context = {'item': item}
    return render(request, 'manager/resource_delete.html', context)


@staff_or_manager_required
def transaction_list(request):
    orders = DatabaseTransaction.objects.select_related('resource', 'staff').all()
    workers = User.objects.filter(is_superuser=False, is_staff=True)
    info = Information.objects.first() if Information.objects.exists() else ""

    selected_status = request.GET.get('status', '')
    selected_resource = request.GET.get('resource', '')
    selected_operator = request.GET.get('operator', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if selected_status:
        orders = orders.filter(status=selected_status)
    if selected_resource:
        orders = orders.filter(resource_id=selected_resource)
    if selected_operator:
        orders = orders.filter(staff_id=selected_operator)
    if date_from:
        orders = orders.filter(date__date__gte=date_from)
    if date_to:
        orders = orders.filter(date__date__lte=date_to)

    context = {
        'information_content': info,
        'orders': orders,
        'workers_count': workers.count(),
        'orders_count': DatabaseTransaction.objects.count(),
        'resources_count': DatabaseResource.objects.count(),
        'status_choices': DatabaseTransaction.TRANSACTION_STATE_CHOICES,
        'filter_resources': DatabaseResource.objects.filter(is_active=True),
        'operators': workers,
        'selected_status': selected_status,
        'selected_resource': selected_resource,
        'selected_operator': selected_operator,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'dashboard/transaction_list.html', context)


@login_required
def transaction_analytics(request):
    statistics = []
    for row in analytics.commit_allocation_breakdown():
        statistics.append({
            'resource': row['resource__name'],
            'category': row['resource__category'],
            'allocated_units': row['allocated_units'] or 0,
            'transaction_count': row['transaction_count'],
        })
    return render(request, 'dashboard/sales_statistics.html', {'statistics': statistics})


@staff_or_manager_required
def edit_information(request):
    information = Information.objects.first()
    if request.method == 'POST':
        form = InformationForm(request.POST, instance=information)
        if form.is_valid():
            form.save()
            return redirect('dashboard-index')
    else:
        form = InformationForm(instance=information)

    return render(request, 'dashboard/edit_information.html', {'form': form})


@staff_or_manager_required
def resource_update(request, pk):
    item = DatabaseResource.objects.get(id=pk)
    FormClass = DatabaseResourceForm if request.user.is_superuser else DatabaseResourceCapacityForm

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            return redirect('dashboard-resource')
    else:
        form = FormClass(instance=item)
    context = {'form': form}
    return render(request, 'manager/resource_update.html', context)


@staff_or_manager_required
def transaction_update(request, pk):
    item = DatabaseTransaction.objects.get(id=pk)
    if request.method == 'POST':
        form = TransactionStateForm(request.POST)
        if form.is_valid():
            try:
                TransactionService.transition(
                    item, form.cleaned_data['status'], request.user, note='Manual update via dashboard'
                )
                return redirect('dashboard-transactions')
            except InvalidTransitionError as exc:
                messages.error(request, str(exc))
    else:
        form = TransactionStateForm(initial={'status': item.status})
    context = {'form': form}
    return render(request, 'dashboard/transaction_update.html', context)


@staff_or_manager_required
def transaction_detail(request, pk):
    txn = get_object_or_404(
        DatabaseTransaction.objects.select_related('resource', 'staff'), pk=pk
    )
    audit_events = txn.audit_trail.all()
    duration = (txn.committed_at - txn.date) if txn.committed_at else None
    context = {
        'txn': txn,
        'audit_events': audit_events,
        'duration': duration,
    }
    return render(request, 'dashboard/transaction_detail.html', context)


@login_required
def search_resources(request):
    query_text = request.GET.get('query', '')
    category = request.GET.get('category', "")
    resources = DatabaseResource.objects.filter(is_active=True)

    if category:
        resources = resources.filter(category=category)

    categories = [c[0] for c in CATEGORY]
    if query_text:
        resources = resources.filter(Q(name__icontains=query_text) | Q(category__icontains=query_text))

    return render(request, 'requester/search_resources.html', {
        'resources': resources,
        'query': query_text,
        'categories': categories,
        'category': category,
    })


def _build_transaction_answer(question):
    api_key = os.environ.get(GOOGLE_API_KEY_ENV)
    if not api_key:
        raise RuntimeError('No GOOGLE_API_KEY configured')

    summary = analytics.build_summary_text()
    prompt = (
        "You are a database transaction operations assistant for an enterprise "
        "transaction-management platform. Use ONLY the summary below to answer the "
        "operator's question about transaction throughput, commit/rollback behaviour, "
        "resource utilization, failures, and concurrency. If the question is unrelated "
        "to this transaction data, say so plainly.\n\n"
        f"Transaction summary:\n{summary}\n\n"
        f"Question: {question}\n"
        "Answer:"
    )

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    return response.text


@login_required
def transaction_insights(request):
    if not request.user.is_superuser:
        return redirect('dashboard-index')

    context = {'messages': ''}
    if request.method == 'POST':
        user_query = request.POST.get('query')
        if not user_query:
            context['messages'] = 'Please enter a query'
            return render(request, 'manager/query.html', context)
        try:
            answer = _build_transaction_answer(user_query)
        except Exception as exc:
            logger.exception('Transaction assistant query failed')
            if 'quota' in str(exc).lower() or 'limit' in str(exc).lower():
                return redirect('change_api_key')
            context['messages'] = 'An error occurred. Please try again.'
            return render(request, 'manager/query.html', context)

        context['answer'] = answer
        context['query'] = user_query
        return render(request, 'manager/query.html', context)

    return render(request, 'manager/query.html', context)


@login_required
def update_api_key(request):
    if not request.user.is_superuser:
        return redirect('dashboard-index')
    if request.method == 'POST':
        api_key = (request.POST.get('api_key') or '').strip()
        if not api_key or any(ch in api_key for ch in ('\r', '\n', '\0')):
            messages.error(request, 'Invalid API key format')
            return render(request, 'manager/change_api_key.html')
        set_key(str(ENV_PATH), GOOGLE_API_KEY_ENV, api_key)
        os.environ[GOOGLE_API_KEY_ENV] = api_key
        messages.success(request, 'API key updated')
        return redirect('transaction-insights')
    return render(request, 'manager/change_api_key.html')


def resource_details(request, pk):
    resource = DatabaseResource.objects.get(id=pk)
    context = {'resource': resource}
    return render(request, 'dashboard/resource_details.html', context)
