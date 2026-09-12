from django.test import TestCase
from dashboard.forms import (
    DatabaseResourceForm,
    TransactionStateForm,
    TransactionSessionForm,
    InformationForm,
    DatabaseResourceCapacityForm,
)
from dashboard.models import DatabaseResource

class TestForms(TestCase):
    def test_resource_form_valid_data(self):
        form = DatabaseResourceForm(data={
            'name': 'Compute Node',
            'description': 'General purpose compute',
            'category': 'Compute',
            'capacity_units': 128,
        })

        self.assertTrue(form.is_valid())

    def test_resource_form_no_data(self):
        form = DatabaseResourceForm(data={})

        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 4)  # 4 fields in the form


    def test_information_form_valid_data(self):
        form = InformationForm(data={
            'content': 'Test Content'
        })

        self.assertTrue(form.is_valid())

    def test_transaction_state_form_valid_data(self):
        form = TransactionStateForm(data={
            'status': 'COMMITTED'
        })

        self.assertTrue(form.is_valid())

    def test_resource_capacity_form_valid_data(self):
        form = DatabaseResourceCapacityForm(data={
            'capacity_units': 256
        })

        self.assertTrue(form.is_valid())


class TransactionSessionFormTierTest(TestCase):
    """TransactionSessionForm resolves a Small/Medium/Large/X-Large size tier
    to a category-specific unit count via RESOURCE_TIERS, instead of taking
    a raw number directly from the user."""

    def setUp(self):
        self.compute = DatabaseResource.objects.create(name='Node', category='Compute', capacity_units=100)
        self.storage = DatabaseResource.objects.create(name='Bucket', category='Storage', capacity_units=5000)

    def test_medium_compute_resolves_to_8_vcpu(self):
        form = TransactionSessionForm(data={'resource': self.compute.pk, 'size': 'Medium'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['requested_units'], 8)

    def test_same_tier_resolves_differently_by_category(self):
        compute_form = TransactionSessionForm(data={'resource': self.compute.pk, 'size': 'Large'})
        storage_form = TransactionSessionForm(data={'resource': self.storage.pk, 'size': 'Large'})

        self.assertTrue(compute_form.is_valid(), compute_form.errors)
        self.assertTrue(storage_form.is_valid(), storage_form.errors)
        self.assertEqual(compute_form.cleaned_data['requested_units'], 32)
        self.assertEqual(storage_form.cleaned_data['requested_units'], 1000)

    def test_custom_size_uses_exact_entered_units(self):
        form = TransactionSessionForm(data={
            'resource': self.compute.pk, 'size': 'Custom', 'custom_units': 17,
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['requested_units'], 17)

    def test_custom_size_without_units_is_invalid(self):
        form = TransactionSessionForm(data={'resource': self.compute.pk, 'size': 'Custom'})
        self.assertFalse(form.is_valid())
        self.assertIn('custom_units', form.errors)

    def test_invalid_size_choice_is_rejected(self):
        form = TransactionSessionForm(data={'resource': self.compute.pk, 'size': 'Enormous'})
        self.assertFalse(form.is_valid())
        self.assertIn('size', form.errors)
