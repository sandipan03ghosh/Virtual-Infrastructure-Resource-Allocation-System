from django.urls import path
from . import views


urlpatterns = [
    path('activate/<int:pk>', views.activate, name='staff-activate'),
    path('staff/',views.staff, name='dashboard-staff'),
    path('staff_page/',views.resource_list,name='staff-resource'),
    path('staff_resource_update/<int:pk>/',views.resource_update,name='staff-resource-update'),
    path('staff_resource_delete/<int:pk>/',views.resource_delete,name='staff-resource-delete'),
    path('staff-register/', views.staff_register, name = 'staff-application'),
    path('staff_transactions/', views.transaction_list, name = 'staff-transactions'),
    path('staff_transactions/update/<int:pk>/',views.transaction_update, name='staff-transaction-update'),
]
