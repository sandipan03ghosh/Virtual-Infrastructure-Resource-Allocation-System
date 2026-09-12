from django.test import TestCase
from django.contrib.auth.models import User
from dashboard.exceptions import InvalidTransitionError
from dashboard.models import DatabaseResource, DatabaseTransaction, Information
from dashboard.services import TransactionService

class DatabaseResourceModelTest(TestCase):
    def test_resource_str_representation(self):
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        self.assertEqual(str(resource), 'Test Resource')

    def test_resource_derived_capacity_fields(self):
        resource = DatabaseResource.objects.create(
            name='Compute Node', category='Compute', capacity_units=64, allocated_units=16
        )
        self.assertEqual(resource.unit, 'vCPU')
        self.assertEqual(resource.available_units, 48)
        self.assertAlmostEqual(resource.utilization, 25.0)
        self.assertEqual(resource.handle, f'res-com-{resource.pk:05d}')

    def test_resource_handle_falls_back_for_unknown_category(self):
        resource = DatabaseResource.objects.create(name='Mystery', category='Other', capacity_units=1)
        self.assertEqual(resource.handle, f'res-oth-{resource.pk:05d}')

class DatabaseTransactionModelTest(TestCase):
    def test_transaction_str_representation(self):
        user = User.objects.create(username='testuser')
        resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)
        txn = DatabaseTransaction.objects.create(resource=resource, staff=user, requested_units=5)
        self.assertEqual(str(txn), f'Transaction #{txn.pk} [{txn.status}] on {resource}')

class InformationModelTest(TestCase):
    def test_information_str_representation(self):
        info = Information.objects.create(content='Test Information')
        self.assertEqual(str(info), 'Test Information')


class TransactionRetryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='operator')
        self.resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)

    def test_failed_transaction_can_be_retried_to_pending(self):
        txn = DatabaseTransaction.objects.create(resource=self.resource, staff=self.user, requested_units=1, status='FAILED')
        TransactionService.transition(txn, 'PENDING', self.user, note='Retry after failure')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'PENDING')
        self.assertEqual(txn.audit_trail.first().to_state, 'PENDING')

    def test_failed_transaction_cannot_skip_to_committed(self):
        txn = DatabaseTransaction.objects.create(resource=self.resource, staff=self.user, requested_units=1, status='FAILED')
        with self.assertRaises(InvalidTransitionError):
            TransactionService.transition(txn, 'COMMITTED', self.user)

    def test_committed_transaction_cannot_be_retried(self):
        txn = DatabaseTransaction.objects.create(resource=self.resource, staff=self.user, requested_units=1, status='COMMITTED')
        with self.assertRaises(InvalidTransitionError):
            TransactionService.transition(txn, 'PENDING', self.user)


class TransactionAllocationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='operator')
        self.resource = DatabaseResource.objects.create(name='Compute Node', category='Compute', capacity_units=100)

    def test_create_reserves_capacity(self):
        TransactionService.create(self.resource, self.user, 30)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.allocated_units, 30)
        self.assertEqual(self.resource.available_units, 70)

    def test_create_rejects_over_capacity_request(self):
        from dashboard.exceptions import InsufficientResourceError
        with self.assertRaises(InsufficientResourceError):
            TransactionService.create(self.resource, self.user, 150)

    def test_rollback_releases_capacity(self):
        txn = TransactionService.create(self.resource, self.user, 40)
        TransactionService.rollback(txn, self.user, reason='no longer needed')
        txn.refresh_from_db()
        self.resource.refresh_from_db()
        self.assertEqual(txn.status, 'ROLLED_BACK')
        self.assertEqual(self.resource.allocated_units, 0)

    def test_commit_keeps_capacity_reserved_and_timestamps(self):
        txn = TransactionService.create(self.resource, self.user, 25)
        TransactionService.transition(txn, 'PENDING', self.user)
        TransactionService.transition(txn, 'VALIDATED', self.user)
        TransactionService.commit(txn, self.user)
        txn.refresh_from_db()
        self.resource.refresh_from_db()
        self.assertEqual(txn.status, 'COMMITTED')
        self.assertIsNotNone(txn.committed_at)
        self.assertEqual(self.resource.allocated_units, 25)
