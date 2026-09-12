from django.contrib import admin
from .models import DatabaseResource, DatabaseTransaction, TransactionAudit
from django.contrib.auth.models import Group
# Register your models here.
admin.site.site_header = "Keystone Transaction Management Platform"

class DatabaseResourceAdmin(admin.ModelAdmin):
    list_display=('name','category','capacity_units', 'allocated_units', 'is_active')
    list_filter=['category', 'is_active']
    fields=('name','category','description','capacity_units','is_active')

class DatabaseTransactionAdmin(admin.ModelAdmin):
    list_display=('id', 'resource', 'staff', 'requested_units', 'status', 'date', 'committed_at')
    list_filter=['status']

class TransactionAuditAdmin(admin.ModelAdmin):
    list_display=('transaction', 'from_state', 'to_state', 'operator', 'timestamp')
    list_filter=['to_state']

admin.site.register(DatabaseResource, DatabaseResourceAdmin)
admin.site.register(DatabaseTransaction, DatabaseTransactionAdmin)
admin.site.register(TransactionAudit, TransactionAuditAdmin)
#admin.site.unregister(Group)
