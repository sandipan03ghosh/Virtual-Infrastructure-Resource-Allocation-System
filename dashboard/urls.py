from django.urls import path
from . import views
from .views import rollback_transaction, rollback_all_transactions


urlpatterns=[
    path('dashboard/', views.index, name='dashboard-index'),
    path('resource/',views.resource_list, name='dashboard-resource'),
    path('resource/delete/<int:pk>/',views.resource_delete, name='dashboard-resource-delete'),
    path('resource/update/<int:pk>/',views.resource_update, name='dashboard-resource-update'),
    path('transactions/',views.transaction_list, name='dashboard-transactions'),
    path('transactions/update/<int:pk>/',views.transaction_update, name='dashboard-transaction-update'),
    path('transactions/<int:pk>/',views.transaction_detail, name='transaction-detail'),
    path('transaction-analytics/', views.transaction_analytics, name='transaction-analytics'),
    path('edit-information/', views.edit_information, name='edit-information'),
    path('transaction-session/', views.transaction_session, name='transaction-session'),
    path('create-transaction/', views.create_transaction, name='create-transaction'),
    path('submit-for-validation/', views.submit_for_validation, name='submit-for-validation'),
    path('validation-queue/', views.validation_queue, name='validation-queue'),
    path('review-commit/', views.review_commit, name='review-commit'),
    path('commit-transactions/', views.commit_transactions, name='commit-transactions'),
    path('rollback/<int:resource_id>/', rollback_transaction, name='rollback-transaction'),
    path('rollback-all/', rollback_all_transactions, name='rollback-all-transactions'),
    path('search/', views.search_resources, name='search-resources'),
    path('transaction-insights/', views.transaction_insights, name='transaction-insights'),
    path('change_api_key/', views.update_api_key, name='change_api_key'),
    path('resource-details/<int:pk>/', views.resource_details, name='resource-details'),
]
