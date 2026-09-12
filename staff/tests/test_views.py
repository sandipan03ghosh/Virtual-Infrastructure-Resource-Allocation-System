from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from dashboard.models import DatabaseResource, DatabaseTransaction, Information
from dashboard.services import TransactionService


class StaffRegisterViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_get_renders_registration_form(self):
        response = self.client.get(reverse('staff-application'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'staff/staff_application.html')

    def test_post_creates_inactive_staff_account(self):
        data = {
            'username': 'newclerk',
            'email': 'newclerk@example.com',
            'password1': 'S3cure!Pass123',
            'password2': 'S3cure!Pass123',
        }
        response = self.client.post(reverse('staff-application'), data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('user-login'))

        user = User.objects.get(username='newclerk')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_active)

    def test_new_account_cannot_log_in_before_activation(self):
        User.objects.create_user(
            username='newclerk', password='S3cure!Pass123',
            is_staff=True, is_active=False, email='newclerk@example.com',
        )
        logged_in = self.client.login(username='newclerk', password='S3cure!Pass123')
        self.assertFalse(logged_in)


class ActivateViewTest(TestCase):
    """activate is guarded by @manager_required (superuser only)."""

    def setUp(self):
        self.client = Client()
        self.pending_user = User.objects.create_user(
            username='newclerk', password='pw', is_staff=True,
            is_active=False, email='newclerk@example.com',
        )
        self.url = reverse('staff-activate', args=[self.pending_user.pk])

    def test_manager_can_activate(self):
        User.objects.create_superuser(username='boss', password='pw', email='boss@example.com')
        self.client.login(username='boss', password='pw')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.pending_user.refresh_from_db()
        self.assertTrue(self.pending_user.is_active)

    def test_non_manager_staff_is_forbidden(self):
        User.objects.create_user(username='clerk', password='pw', is_staff=True, email='clerk@example.com')
        self.client.login(username='clerk', password='pw')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
        self.pending_user.refresh_from_db()
        self.assertFalse(self.pending_user.is_active)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('user-login'), response.url)


class StaffDashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        User.objects.create_user(username='clerk', password='pw', is_staff=True, email='clerk@example.com')
        self.client.login(username='clerk', password='pw')

    def test_staff_dashboard_renders_with_expected_context(self):
        Information.objects.create(content='Ops notice')

        response = self.client.get(reverse('dashboard-staff'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('workers', response.context)
        self.assertIn('workers_count', response.context)
        self.assertIn('orders_count', response.context)
        self.assertIn('resources_count', response.context)
        self.assertEqual(response.context['information_content'], 'Ops notice')


class StaffResourceListViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('staff-resource'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('user-login'), response.url)

    def test_non_staff_is_forbidden(self):
        User.objects.create_user(username='plain', password='pw', email='plain@example.com')
        self.client.login(username='plain', password='pw')

        response = self.client.get(reverse('staff-resource'))

        self.assertEqual(response.status_code, 403)

    def test_staff_can_view_and_create_resource(self):
        User.objects.create_user(username='clerk', password='pw', is_staff=True, email='clerk@example.com')
        self.client.login(username='clerk', password='pw')

        response = self.client.get(reverse('staff-resource'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'staff/staff_page.html')

        data = {
            'name': 'Object Store',
            'description': 'Blob storage',
            'category': 'Storage',
            'capacity_units': 500,
        }
        response = self.client.post(reverse('staff-resource'), data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DatabaseResource.objects.filter(name='Object Store').exists())


class StaffResourceDeleteViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        User.objects.create_user(username='clerk', password='pw', is_staff=True, email='clerk@example.com')
        self.client.login(username='clerk', password='pw')
        self.resource = DatabaseResource.objects.create(name='Object Store', category='Storage', capacity_units=500)

    def test_get_renders_confirmation(self):
        response = self.client.get(reverse('staff-resource-delete', kwargs={'pk': self.resource.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('item', response.context)

    def test_post_soft_deletes_resource(self):
        response = self.client.post(reverse('staff-resource-delete', kwargs={'pk': self.resource.pk}))

        self.assertEqual(response.status_code, 302)
        self.resource.refresh_from_db()
        self.assertFalse(self.resource.is_active)
        self.assertTrue(DatabaseResource.objects.filter(pk=self.resource.pk).exists())


class StaffResourceUpdateAuthorizationTest(TestCase):
    """resource_update now carries @staff_or_manager_required (it only had
    @login_required before), matching the equivalent fix already applied to
    dashboard.views.resource_update — ordinary authenticated users must not
    be able to change a resource's capacity."""

    def setUp(self):
        self.client = Client()
        self.resource = DatabaseResource.objects.create(name='Object Store', category='Storage', capacity_units=500)
        self.url = reverse('staff-resource-update', kwargs={'pk': self.resource.pk})

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('user-login'), response.url)

    def test_non_staff_is_forbidden(self):
        User.objects.create_user(username='plain', password='pw', email='plain@example.com')
        self.client.login(username='plain', password='pw')

        response = self.client.post(self.url, {'capacity_units': 999})

        self.assertEqual(response.status_code, 403)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.capacity_units, 500)

    def test_staff_can_update_capacity(self):
        User.objects.create_user(username='clerk', password='pw', is_staff=True, email='clerk@example.com')
        self.client.login(username='clerk', password='pw')

        response = self.client.post(self.url, {'capacity_units': 750})

        self.assertEqual(response.status_code, 302)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.capacity_units, 750)


class StaffTransactionListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.clerk = User.objects.create_user(username='clerk', password='pw', is_staff=True, email='clerk@example.com')
        self.resource = DatabaseResource.objects.create(name='Compute Node', category='Compute', capacity_units=64)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('staff-transactions'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('user-login'), response.url)

    def test_non_staff_is_forbidden(self):
        User.objects.create_user(username='plain', password='pw', email='plain@example.com')
        self.client.login(username='plain', password='pw')

        response = self.client.get(reverse('staff-transactions'))

        self.assertEqual(response.status_code, 403)

    def test_filter_by_status(self):
        self.client.login(username='clerk', password='pw')
        DatabaseTransaction.objects.create(resource=self.resource, staff=self.clerk, requested_units=8, status='PENDING')
        DatabaseTransaction.objects.create(resource=self.resource, staff=self.clerk, requested_units=8, status='COMMITTED')

        response = self.client.get(reverse('staff-transactions'), {'status': 'PENDING'})

        self.assertEqual(response.status_code, 200)
        orders = list(response.context['orders'])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].status, 'PENDING')


class StaffTransactionUpdateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.clerk = User.objects.create_user(username='clerk', password='pw', is_staff=True, email='clerk@example.com')
        self.client.login(username='clerk', password='pw')
        self.resource = DatabaseResource.objects.create(name='Compute Node', category='Compute', capacity_units=64)

    def test_valid_transition_updates_status(self):
        txn = TransactionService.create(self.resource, self.clerk, 8)
        TransactionService.transition(txn, 'PENDING', self.clerk)

        response = self.client.post(
            reverse('staff-transaction-update', kwargs={'pk': txn.pk}), {'status': 'VALIDATED'}
        )

        self.assertEqual(response.status_code, 302)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'VALIDATED')

    def test_invalid_transition_is_rejected(self):
        txn = DatabaseTransaction.objects.create(
            resource=self.resource, staff=self.clerk, requested_units=8, status='COMMITTED'
        )

        response = self.client.post(
            reverse('staff-transaction-update', kwargs={'pk': txn.pk}), {'status': 'PENDING'}
        )

        self.assertEqual(response.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'COMMITTED')
