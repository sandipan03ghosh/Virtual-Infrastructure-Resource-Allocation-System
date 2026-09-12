from django.test import TestCase
from django.contrib.auth.models import User

from dashboard import analytics
from dashboard.models import DatabaseResource, DatabaseTransaction


class ResolvedRateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='operator')
        self.resource = DatabaseResource.objects.create(name='Test Resource', category='Compute', capacity_units=10)

    def _make(self, status):
        return DatabaseTransaction.objects.create(
            resource=self.resource, staff=self.user, requested_units=1, status=status,
        )

    def test_rates_are_zero_with_no_resolved_transactions(self):
        self._make('CREATED')
        self._make('PENDING')
        self.assertEqual(analytics.success_rate(), 0)
        self.assertEqual(analytics.failure_rate(), 0)
        self.assertEqual(analytics.rollback_rate(), 0)

    def test_rates_computed_over_resolved_transactions_only(self):
        # 2 committed, 1 failed, 1 rolled back, plus 2 in-flight that must not
        # count toward the denominator.
        self._make('COMMITTED')
        self._make('COMMITTED')
        self._make('FAILED')
        self._make('ROLLED_BACK')
        self._make('PENDING')
        self._make('EXECUTING')

        self.assertAlmostEqual(analytics.success_rate(), 50.0)
        self.assertAlmostEqual(analytics.failure_rate(), 25.0)
        self.assertAlmostEqual(analytics.rollback_rate(), 25.0)

    def test_rates_sum_to_100_over_resolved_transactions(self):
        self._make('COMMITTED')
        self._make('FAILED')
        self._make('ROLLED_BACK')

        total = analytics.success_rate() + analytics.failure_rate() + analytics.rollback_rate()
        self.assertAlmostEqual(total, 100.0)


class CapacityAnalyticsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='operator')

    def test_resource_utilization_is_allocated_over_capacity(self):
        DatabaseResource.objects.create(name='A', category='Compute', capacity_units=100, allocated_units=25)
        DatabaseResource.objects.create(name='B', category='Storage', capacity_units=100, allocated_units=75)
        self.assertAlmostEqual(analytics.resource_utilization(), 50.0)

    def test_commit_allocation_breakdown_sums_committed_units(self):
        resource = DatabaseResource.objects.create(name='A', category='Compute', capacity_units=100)
        DatabaseTransaction.objects.create(resource=resource, staff=self.user, requested_units=10, status='COMMITTED')
        DatabaseTransaction.objects.create(resource=resource, staff=self.user, requested_units=5, status='COMMITTED')
        DatabaseTransaction.objects.create(resource=resource, staff=self.user, requested_units=99, status='CREATED')

        rows = analytics.commit_allocation_breakdown()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['allocated_units'], 15)
        self.assertEqual(rows[0]['transaction_count'], 2)
