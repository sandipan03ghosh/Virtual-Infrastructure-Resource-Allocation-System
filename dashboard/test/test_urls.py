from django.test import SimpleTestCase
from django.urls import reverse, resolve
from dashboard.views import (
    index,
    resource_list,
    resource_delete,
    resource_update,
    transaction_list,
    transaction_update,
    transaction_analytics,
    edit_information,
    transaction_session,
    create_transaction,
    submit_for_validation,
    validation_queue,
    review_commit,
    commit_transactions,
    rollback_transaction,
    rollback_all_transactions,
)

class TestUrls(SimpleTestCase):

        def test_dashboard_index_url_is_resolved(self):
            url=reverse('dashboard-index')
            print(resolve(url))
            self.assertEqual(resolve(url).func, index)

        def test_dashboard_resource_url_is_resolved(self):
            url=reverse('dashboard-resource')
            print(resolve(url))
            self.assertEqual(resolve(url).func, resource_list)

        def test_dashboard_resource_delete_url_is_resolved(self):
            url=reverse('dashboard-resource-delete', args=[1])
            print(resolve(url))
            self.assertEqual(resolve(url).func, resource_delete)


        def test_dashboard_resource_update_url_is_resolved(self):
            url=reverse('dashboard-resource-update', args=[1])
            print(resolve(url))
            self.assertEqual(resolve(url).func, resource_update)


        def test_dashboard_transactions_url_is_resolved(self):
            url=reverse('dashboard-transactions')
            print(resolve(url))
            self.assertEqual(resolve(url).func, transaction_list)


        def test_dashboard_transaction_update_url_is_resolved(self):
            url=reverse('dashboard-transaction-update', args=[1])
            print(resolve(url))
            self.assertEqual(resolve(url).func, transaction_update)

        def test_transaction_analytics_url_is_resolved(self):
            url=reverse('transaction-analytics')
            print(resolve(url))
            self.assertEqual(resolve(url).func, transaction_analytics)

        def test_edit_information_url_is_resolved(self):
            url=reverse('edit-information')
            print(resolve(url))
            self.assertEqual(resolve(url).func, edit_information)

        def test_transaction_session_url_is_resolved(self):
            url=reverse('transaction-session')
            print(resolve(url))
            self.assertEqual(resolve(url).func, transaction_session)

        def test_create_transaction_url_is_resolved(self):
            url=reverse('create-transaction')
            print(resolve(url))
            self.assertEqual(resolve(url).func, create_transaction)

        def test_submit_for_validation_url_is_resolved(self):
            url=reverse('submit-for-validation')
            print(resolve(url))
            self.assertEqual(resolve(url).func, submit_for_validation)

        def test_validation_queue_url_is_resolved(self):
            url=reverse('validation-queue')
            print(resolve(url))
            self.assertEqual(resolve(url).func, validation_queue)

        def test_review_commit_url_is_resolved(self):
            url=reverse('review-commit')
            print(resolve(url))
            self.assertEqual(resolve(url).func, review_commit)

        def test_commit_transactions_url_is_resolved(self):
            url=reverse('commit-transactions')
            print(resolve(url))
            self.assertEqual(resolve(url).func, commit_transactions)

        def test_rollback_transaction_url_is_resolved(self):
            url=reverse('rollback-transaction', args=[1])
            print(resolve(url))
            self.assertEqual(resolve(url).func, rollback_transaction)

        def test_rollback_all_transactions_url_is_resolved(self):
            url=reverse('rollback-all-transactions')
            print(resolve(url))
            self.assertEqual(resolve(url).func, rollback_all_transactions)
