from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import User
from dashboard.models import DatabaseResource, DatabaseTransaction, Information, TransactionAudit
from datetime import datetime
from unittest.mock import patch
from dashboard.views import compute_total_units, edit_information
from dashboard.services import TransactionService

class TestViews(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='123@Gerimara', is_staff=True)
        self.client.login(username='testuser', password='123@Gerimara')

    def test_index_view(self):
        response = self.client.get(reverse('dashboard-index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/index.html')

    def test_index_view_capacity_totals(self):
        DatabaseResource.objects.create(name='A', category='Compute', capacity_units=100, allocated_units=25)
        DatabaseResource.objects.create(name='B', category='Storage', capacity_units=50, allocated_units=10)

        response = self.client.get(reverse('dashboard-index'))

        self.assertEqual(response.context['capacity_total'], 150)
        self.assertEqual(response.context['capacity_allocated'], 35)
        self.assertEqual(response.context['capacity_available'], 115)

    def test_create_transaction_view(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        response = self.client.post(reverse('create-transaction'), {
            'resource': resource.id,
            'size': 'Medium',  # Compute:Medium resolves to 8 vCPU via RESOURCE_TIERS
        })
        self.assertEqual(response.status_code, 302)
        resource.refresh_from_db()
        self.assertEqual(resource.allocated_units, 8)

    def test_transaction_session_view(self):
        response = self.client.get(reverse('transaction-session'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/transaction_session.html')

    def test_compute_total_units(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=100)
        txn = DatabaseTransaction.objects.create(resource=resource, requested_units=5)
        self.assertEqual(compute_total_units([txn]), 5)

    def test_to_counter_view(self):
        DatabaseTransaction.objects.create(status='CREATED', staff=self.user)
        DatabaseTransaction.objects.create(status='CREATED', staff=self.user)

        response = self.client.get(reverse('submit-for-validation'))

        session_transactions = DatabaseTransaction.objects.filter(status='CREATED', staff=self.user)
        self.assertEqual(session_transactions.count(), 0)

        pending_transactions = DatabaseTransaction.objects.filter(status='PENDING').count()
        self.assertEqual(pending_transactions, 2)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/validation_queue.html')

    def test_counter_view(self):
        DatabaseTransaction.objects.create(status='PENDING')
        DatabaseTransaction.objects.create(status='PENDING')
        DatabaseTransaction.objects.create(status='VALIDATED')

        response = self.client.get(reverse('validation-queue'))

        pending_transactions = DatabaseTransaction.objects.filter(status='PENDING').count()
        validated_transactions = DatabaseTransaction.objects.filter(status='VALIDATED').count()
        self.assertEqual(pending_transactions, 2)
        self.assertEqual(validated_transactions, 1)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/validation_queue.html')

    def test_review_commit_view(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=100)
        DatabaseTransaction.objects.create(resource=resource, requested_units=5, status='VALIDATED', staff=self.user)

        response = self.client.get(reverse('review-commit'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/review_commit.html')
        self.assertIn('total_units', response.context)
        self.assertEqual(response.context['total_units'], 5)

    def test_billing_view(self):
        resource = DatabaseResource.objects.create(
            name='Test Resource', category='Compute', capacity_units=100
        )
        txn = DatabaseTransaction.objects.create(
            resource=resource, requested_units=5, status='VALIDATED', staff=self.user
        )

        response = self.client.post(reverse('commit-transactions'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/transaction_receipt.html')

        # Check the transaction committed
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'COMMITTED')
        self.assertIsNotNone(txn.committed_at)

        # Check if allocation_ref is generated
        self.assertIn('allocation_ref', response.context)
        self.assertTrue(response.context['allocation_ref'])

        # Check if date is generated
        self.assertIn('date', response.context)
        self.assertTrue(response.context['date'])

        # Check if total_units is passed to the context
        self.assertIn('total_units', response.context)
        self.assertEqual(response.context['total_units'], 5)

    def test_rollback_transaction_view(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        TransactionService.create(resource, self.user, 5)
        resource.refresh_from_db()
        self.assertEqual(resource.allocated_units, 5)

        response = self.client.get(reverse('rollback-transaction', kwargs={'resource_id': resource.id}))
        self.assertEqual(response.status_code, 302)  # Should redirect to the transaction session

        # Check the transaction was rolled back (not deleted) and capacity released
        txn = DatabaseTransaction.objects.get(resource=resource, staff=self.user)
        self.assertEqual(txn.status, 'ROLLED_BACK')
        resource.refresh_from_db()
        self.assertEqual(resource.allocated_units, 0)

    def test_rollback_all_transactions_view(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        TransactionService.create(resource, self.user, 5)

        response = self.client.get(reverse('rollback-all-transactions'))
        self.assertEqual(response.status_code, 302)  # Should redirect to the transaction session

        # Check the transaction was rolled back (not deleted) and capacity released
        txn = DatabaseTransaction.objects.get(resource=resource, staff=self.user)
        self.assertEqual(txn.status, 'ROLLED_BACK')
        self.assertFalse(DatabaseTransaction.objects.filter(staff=self.user, status='CREATED').exists())
        resource.refresh_from_db()
        self.assertEqual(resource.allocated_units, 0)

    def test_staff_view(self):
        # Create sample users and data
        User.objects.create_user(username='staff1', password='123@Srinjoy', is_staff=True)
        User.objects.create_user(username='staff2', password='123@Gerimara', is_staff=True)
        Information.objects.create(content='Test information')

        response = self.client.get(reverse('dashboard-staff'))
        self.assertEqual(response.status_code, 200)  # Should return success

        # Check if correct context is passed
        self.assertIn('workers', response.context)
        self.assertIn('workers_count', response.context)
        self.assertIn('orders_count', response.context)
        self.assertIn('resources_count', response.context)
        self.assertIn('information_content', response.context)

    def test_resource_list_view(self):
        response = self.client.get(reverse('dashboard-resource'))
        self.assertEqual(response.status_code, 200)  # Should return success

        # Check if correct context is passed
        self.assertIn('information_content', response.context)
        self.assertIn('items', response.context)
        self.assertIn('form', response.context)
        self.assertIn('workers_count', response.context)
        self.assertIn('orders_count', response.context)
        self.assertIn('resources_count', response.context)

    def test_resource_create_post(self):
        data = {
            'name': 'Test Resource',
            'description': 'Test description',
            'category': 'Compute',
            'capacity_units': 128,
        }
        response = self.client.post(reverse('dashboard-resource'), data=data)
        self.assertEqual(response.status_code, 302)  # Should redirect to 'dashboard-resource'

        # Check if resource is created
        self.assertTrue(DatabaseResource.objects.filter(name='Test Resource').exists())

    def test_resource_delete_view(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        response = self.client.get(reverse('dashboard-resource-delete', kwargs={'pk': resource.id}))
        self.assertEqual(response.status_code, 200)

        self.assertIn('item', response.context)

    def test_resource_delete_view_post_soft_deletes_resource(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        txn = DatabaseTransaction.objects.create(resource=resource, requested_units=2, status='COMMITTED', staff=self.user)
        TransactionAudit.objects.create(transaction=txn, from_state='EXECUTING', to_state='COMMITTED', operator=self.user)

        response = self.client.post(reverse('dashboard-resource-delete', kwargs={'pk': resource.id}))
        self.assertEqual(response.status_code, 302)

        # Resource is deactivated, not destroyed
        resource.refresh_from_db()
        self.assertFalse(resource.is_active)
        self.assertTrue(DatabaseResource.objects.filter(pk=resource.pk).exists())

        # Its transaction and audit history both survive
        txn.refresh_from_db()
        self.assertEqual(txn.resource_id, resource.pk)
        self.assertTrue(TransactionAudit.objects.filter(transaction=txn).exists())

    def test_transaction_list_filter_by_status(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        DatabaseTransaction.objects.create(resource=resource, staff=self.user, requested_units=1, status='PENDING')
        DatabaseTransaction.objects.create(resource=resource, staff=self.user, requested_units=1, status='COMMITTED')

        response = self.client.get(reverse('dashboard-transactions'), {'status': 'PENDING'})

        self.assertEqual(response.status_code, 200)
        orders = list(response.context['orders'])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].status, 'PENDING')

    def test_transaction_list_filter_by_resource(self):
        resource1 = DatabaseResource.objects.create(name='Resource 1', category='Compute', capacity_units=10)
        resource2 = DatabaseResource.objects.create(name='Resource 2', category='Storage', capacity_units=10)
        DatabaseTransaction.objects.create(resource=resource1, staff=self.user, requested_units=1, status='PENDING')
        DatabaseTransaction.objects.create(resource=resource2, staff=self.user, requested_units=1, status='PENDING')

        response = self.client.get(reverse('dashboard-transactions'), {'resource': resource1.id})

        orders = list(response.context['orders'])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].resource_id, resource1.id)

    def test_transaction_list_filter_by_operator(self):
        other_user = User.objects.create_user(username='otheruser', password='123@Gerimara', is_staff=True)
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        DatabaseTransaction.objects.create(resource=resource, staff=self.user, requested_units=1, status='PENDING')
        DatabaseTransaction.objects.create(resource=resource, staff=other_user, requested_units=1, status='PENDING')

        response = self.client.get(reverse('dashboard-transactions'), {'operator': self.user.id})

        orders = list(response.context['orders'])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].staff_id, self.user.id)

    def test_transaction_list_no_results_for_unmatched_filter(self):
        # The dashboard transaction list template only renders for superusers.
        self.user.is_superuser = True
        self.user.save()
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        DatabaseTransaction.objects.create(resource=resource, staff=self.user, requested_units=1, status='PENDING')

        response = self.client.get(reverse('dashboard-transactions'), {'status': 'COMMITTED'})

        self.assertEqual(list(response.context['orders']), [])
        self.assertContains(response, 'No transactions match your filters.')

    def test_transaction_detail_view(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        txn = DatabaseTransaction.objects.create(resource=resource, staff=self.user, requested_units=5, status='FAILED')
        TransactionAudit.objects.create(transaction=txn, from_state='EXECUTING', to_state='FAILED', operator=self.user, note='Simulated failure')

        response = self.client.get(reverse('transaction-detail', kwargs={'pk': txn.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/transaction_detail.html')
        self.assertEqual(response.context['txn'], txn)
        self.assertEqual(len(response.context['audit_events']), 1)
        self.assertIsNone(response.context['duration'])

    def test_transaction_detail_view_404_for_missing_transaction(self):
        response = self.client.get(reverse('transaction-detail', kwargs={'pk': 999999}))
        self.assertEqual(response.status_code, 404)

    def test_allocation_statistics(self):
        resource1 = DatabaseResource.objects.create(name='Resource 1', category='Compute', capacity_units=100, allocated_units=5)
        resource2 = DatabaseResource.objects.create(name='Resource 2', category='Storage', capacity_units=200, allocated_units=10)
        DatabaseTransaction.objects.create(resource=resource1, requested_units=5, status='COMMITTED', staff=self.user)
        DatabaseTransaction.objects.create(resource=resource2, requested_units=10, status='COMMITTED', staff=self.user)

        response = self.client.get(reverse('transaction-analytics'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/sales_statistics.html')

    def test_edit_information_view_get(self):
        response = self.client.get(reverse('edit-information'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/edit_information.html')

    def test_edit_information_view_post(self):
        data = {'content': 'Updated Content'}
        response = self.client.post(reverse('edit-information'), data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard-index'))
        information = Information.objects.first()
        self.assertEqual(information.content, 'Updated Content')

    def test_edit_information_view_invalid_form(self):

        data = {'content': ''}
        response = self.client.post(reverse('edit-information'), data)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/edit_information.html')

        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertTrue(form.errors)
        self.assertIn('content', form.errors)
        self.assertIn('This field is required.', form.errors['content'])


    def test_edit_information_view_nonexistent_instance(self):
        Information.objects.all().delete()
        request = RequestFactory().get(reverse('edit-information'))
        request.user = self.user
        response = edit_information(request)


        self.assertEqual(response.status_code, 200)

    def test_resource_update_get_renders_form(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        response = self.client.get(reverse('dashboard-resource-update', kwargs={'pk': resource.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'manager/resource_update.html')

    def test_resource_update_staff_changes_capacity(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        data = {'capacity_units': 40}
        response = self.client.post(reverse('dashboard-resource-update', kwargs={'pk': resource.pk}), data)
        self.assertEqual(response.status_code, 302)
        resource.refresh_from_db()
        self.assertEqual(resource.capacity_units, 40)

    def test_resource_update_manager_edits_full_resource(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        User.objects.create_superuser(username='boss', password='123@Gerimara', email='boss@example.com')
        self.client.login(username='boss', password='123@Gerimara')
        data = {
            'name': 'Renamed Node',
            'description': 'updated',
            'category': 'Storage',
            'capacity_units': 512,
        }
        response = self.client.post(reverse('dashboard-resource-update', kwargs={'pk': resource.pk}), data)
        self.assertEqual(response.status_code, 302)
        resource.refresh_from_db()
        self.assertEqual(resource.name, 'Renamed Node')
        self.assertEqual(resource.capacity_units, 512)

    @patch('dashboard.views.redirect')
    def test_order_update(self, mock_redirect):
        txn = DatabaseTransaction.objects.create(requested_units=5)
        response = self.client.post(reverse('dashboard-transaction-update', kwargs={'pk': txn.pk}))
        self.assertEqual(response.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.requested_units, 5)  # TransactionStateForm doesn't change the units
        #mock_redirect.assert_called_once_with('dashboard-transactions')


class EditInformationAuthorizationTests(TestCase):
    """edit_information is guarded by @staff_or_manager_required: anonymous
    visitors are redirected to login, authenticated non-staff users get a 403,
    and staff/manager users keep full access."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('edit-information')

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('user-login'), response.url)

    def test_anonymous_user_cannot_post_information(self):
        response = self.client.post(self.url, {'content': 'anonymous banner'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Information.objects.filter(content='anonymous banner').exists())

    def test_authenticated_non_staff_user_is_forbidden(self):
        User.objects.create_user(username='plain', password='123@Gerimara')
        self.client.login(username='plain', password='123@Gerimara')
        response = self.client.post(self.url, {'content': 'sneaky banner'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Information.objects.filter(content='sneaky banner').exists())

    def test_staff_user_retains_get_access(self):
        User.objects.create_user(username='staffo', password='123@Gerimara', is_staff=True)
        self.client.login(username='staffo', password='123@Gerimara')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/edit_information.html')

    def test_staff_user_can_update_information(self):
        User.objects.create_user(username='staffo', password='123@Gerimara', is_staff=True)
        self.client.login(username='staffo', password='123@Gerimara')
        response = self.client.post(self.url, {'content': 'Official banner'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Information.objects.first().content, 'Official banner')

    def test_manager_retains_access(self):
        User.objects.create_superuser(username='boss', password='123@Gerimara', email='boss@example.com')
        self.client.login(username='boss', password='123@Gerimara')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class ResourceUpdateAuthorizationTests(TestCase):
    """resource_update is guarded by @staff_or_manager_required: ordinary
    authenticated users can no longer modify a resource's capacity."""

    def setUp(self):
        self.client = Client()
        self.resource = DatabaseResource.objects.create(
            name='Auth Resource', category='Compute', capacity_units=10
        )
        self.url = reverse('dashboard-resource-update', kwargs={'pk': self.resource.pk})

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('user-login'), response.url)

    def test_authenticated_non_staff_user_is_forbidden(self):
        User.objects.create_user(username='plain', password='123@Gerimara')
        self.client.login(username='plain', password='123@Gerimara')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_authenticated_non_staff_user_cannot_change_capacity(self):
        User.objects.create_user(username='plain', password='123@Gerimara')
        self.client.login(username='plain', password='123@Gerimara')
        response = self.client.post(self.url, {'capacity_units': 999})
        self.assertEqual(response.status_code, 403)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.capacity_units, 10)

    def test_staff_user_retains_get_access(self):
        User.objects.create_user(username='staffo', password='123@Gerimara', is_staff=True)
        self.client.login(username='staffo', password='123@Gerimara')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'manager/resource_update.html')

    def test_staff_user_can_change_capacity(self):
        User.objects.create_user(username='staffo', password='123@Gerimara', is_staff=True)
        self.client.login(username='staffo', password='123@Gerimara')
        response = self.client.post(self.url, {'capacity_units': 25})
        self.assertEqual(response.status_code, 302)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.capacity_units, 25)

    def test_manager_retains_access(self):
        User.objects.create_superuser(username='boss', password='123@Gerimara', email='boss@example.com')
        self.client.login(username='boss', password='123@Gerimara')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'manager/resource_update.html')
