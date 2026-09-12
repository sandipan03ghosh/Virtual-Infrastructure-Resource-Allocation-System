from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from dashboard.models import DatabaseTransaction, DatabaseResource, Information
from dashboard.forms import DatabaseResourceForm, DatabaseResourceCapacityForm, TransactionStateForm
from dashboard.services import TransactionService
from dashboard.exceptions import InvalidTransitionError
from dashboard.decorators import manager_required, staff_or_manager_required
from .forms import StaffRegisterForm
from django.contrib.auth.models import User
from django.contrib import messages
from datetime import datetime
from random import randint
from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.forms import UserCreationForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from io import BytesIO
import os

def staff_register(request):
    if request.method == 'POST':
        form = StaffRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)  # Don't save to database yet
            user.is_active = False # Wait for manager to activate account
            user.is_staff = True  # Set is_staff to True
            user.save()  # Now save to database
            username = user.username
            messages.success(request, f'Account has been created for {username}.\
                            Your account is pending approval.\
                            You will receive an email once your account is activated.')
            return redirect('user-login')
    else:
        form = StaffRegisterForm()

    helper = FormHelper()
    helper.form_method = 'post'
    helper.add_input(Submit('submit', 'Sign Up', css_class='btn-primary'))

    return render(request, 'staff/staff_application.html', {'form': form, 'helper': helper})




@manager_required
def activate(request, pk):
    user = User.objects.get(id=pk)
    user.is_active = True
    user.save()
    message = f'Your account has been activated. You can now login to your account.'
    subject = 'Account Activation'
    # no html message just the plain text
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [user.email],
        fail_silently=True,
    )
    messages.success(request, f'{user.username} has been activated')
    return redirect('dashboard-staff')

@login_required
def staff(request):
    workers=User.objects.filter(is_superuser=False, is_staff=True)
    workers_count=workers.count()
    information = Information.objects.first()
    orders_count=DatabaseTransaction.objects.count()
    resources_count=DatabaseResource.objects.count()
    context={
        'workers':workers,
        'workers_count':workers_count,
        'orders_count':orders_count,
        'resources_count':resources_count,
        'information_content': information.content if information else "",
    }
    return render(request, 'staff/staff.html',context)

@login_required
def logout_view(request):
    logout(request)
    # return redirect('dashboard-index')
    return render(request, 'user/logout.html')

@staff_or_manager_required
def resource_list(request):
    items=DatabaseResource.objects.all()
    resources_count=DatabaseResource.objects.count()
    information = Information.objects.first()
    information_content = information.content if information else ""
    if request.method=='POST':
        form=DatabaseResourceForm(request.POST)
        if form.is_valid():
            resource = form.save()

            messages.success(request, f'{resource.name} has been added successfully')
            return redirect('staff-resource')

    form=DatabaseResourceForm()
    context={
        'items':items,
        'forms':form,
        'resources_count':resources_count,
        'information_content': information_content,
    }
    return render(request, 'staff/staff_page.html', context)

@staff_or_manager_required
def resource_delete(request, pk):
    item=DatabaseResource.objects.get(id=pk)
    if request.method=='POST':
        item.is_active = False
        item.save(update_fields=['is_active'])
        return redirect('staff-resource')
    context={
        'item':item
    }
    return render(request, 'staff/staff_delete.html', context)


@staff_or_manager_required
def resource_update(request, pk):
    item=DatabaseResource.objects.get(id=pk)
    if request.method=='POST':
        form=DatabaseResourceCapacityForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            return redirect('staff-resource')
    else:
        form=DatabaseResourceCapacityForm(instance=item)
    context={
        'forms':form
    }
    return render(request, 'staff/staff_update.html', context)

@staff_or_manager_required
def transaction_list(request):
    orders=DatabaseTransaction.objects.select_related('resource', 'staff').all()
    workers=User.objects.filter(is_superuser=False, is_staff=True)
    workers_count=workers.count()
    orders_count=DatabaseTransaction.objects.count()
    resources_count=DatabaseResource.objects.count()

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

    context={
        'orders':orders,
        'workers_count':workers_count,
        'orders_count':orders_count,
        'resources_count':resources_count,
        'status_choices': DatabaseTransaction.TRANSACTION_STATE_CHOICES,
        'filter_resources': DatabaseResource.objects.filter(is_active=True),
        'operators': workers,
        'selected_status': selected_status,
        'selected_resource': selected_resource,
        'selected_operator': selected_operator,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'staff/transaction_list.html',context)

@staff_or_manager_required
def transaction_update(request, pk):
    item=DatabaseTransaction.objects.get(id=pk)
    if request.method=='POST':
        form=TransactionStateForm(request.POST)
        if form.is_valid():
            try:
                TransactionService.transition(
                    item, form.cleaned_data['status'], request.user, note='Manual update via staff console'
                )
                return redirect('staff-transactions')
            except InvalidTransitionError as exc:
                messages.error(request, str(exc))
    else:
        form=TransactionStateForm(initial={'status': item.status})
    context={
        'form':form
    }
    return render(request, 'dashboard/transaction_update.html', context)
