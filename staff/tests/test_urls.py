from django.test import SimpleTestCase
from django.urls import reverse, resolve
from staff.views import activate
from django.urls import path
from staff import views


class TestUrls(SimpleTestCase):

    def test_activate_url_is_resolved(self):
        url=reverse('staff-activate',args=[1])
        print(resolve(url))
        self.assertEqual(resolve(url).func, activate)

    def test_staff_url_is_resolved(self):
        url=reverse('dashboard-staff')
        print(resolve(url))
        self.assertEqual(resolve(url).func, views.staff)

    def test_staff_resource_url_is_resolved(self):
        url=reverse('staff-resource')
        print(resolve(url))
        self.assertEqual(resolve(url).func, views.resource_list)

    def test_staff_resource_update_url_is_resolved(self):
        url=reverse('staff-resource-update',args=[1])
        print(resolve(url))
        self.assertEqual(resolve(url).func, views.resource_update)

    def test_staff_resource_delete_url_is_resolved(self):
        url=reverse('staff-resource-delete',args=[1])
        print(resolve(url))
        self.assertEqual(resolve(url).func, views.resource_delete)

    def test_staff_register_url_is_resolved(self):
        url=reverse('staff-application')
        print(resolve(url))
        self.assertEqual(resolve(url).func, views.staff_register)

    def test_staff_transactions_url_is_resolved(self):
        url=reverse('staff-transactions')
        print(resolve(url))
        self.assertEqual(resolve(url).func, views.transaction_list)

    def test_staff_transaction_update_url_is_resolved(self):
        url=reverse('staff-transaction-update',args=[1])
        print(resolve(url))
        self.assertEqual(resolve(url).func, views.transaction_update)
