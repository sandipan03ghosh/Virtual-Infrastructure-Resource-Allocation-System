from django.db import models
from django.contrib.auth.models import User
# Create your models here.
CATEGORY=(
    ('Compute','Compute'),
    ('Storage','Storage'),
    ('Network','Network'),
    ('Dataset','Dataset'),
    ('Service','Service'),
    ('Other','Other'),
)

# The allocation unit each resource category is measured in, used for
# display ("64 vCPU", "4096 GB").
CATEGORY_UNITS = {
    'Compute': 'vCPU',
    'Storage': 'GB',
    'Network': 'Mbps',
    'Dataset': 'GB',
    'Service': 'instances',
    'Other': 'units',
}

# Short code used to build resource handles (res-<code>-00001), mirroring how
# cloud providers prefix resource ids by type (i-, vol-, vpc-, ...).
CATEGORY_CODE = {
    'Compute': 'com',
    'Storage': 'sto',
    'Network': 'net',
    'Dataset': 'dat',
    'Service': 'svc',
    'Other': 'oth',
}

# Preset sizing tiers per category, in the resource's own unit — the same
# idea as picking an EC2 instance type instead of typing an arbitrary vCPU
# count. TransactionSessionForm resolves a (category, tier) pair to one of
# these numbers; 'Custom' bypasses the table for an exact user-entered count.
RESOURCE_TIERS = {
    'Compute': {'Small': 2, 'Medium': 8, 'Large': 32, 'XLarge': 64},
    'Storage': {'Small': 50, 'Medium': 250, 'Large': 1000, 'XLarge': 4000},
    'Network': {'Small': 100, 'Medium': 500, 'Large': 1000, 'XLarge': 5000},
    'Dataset': {'Small': 10, 'Medium': 100, 'Large': 500, 'XLarge': 2000},
    'Service': {'Small': 1, 'Medium': 5, 'Large': 20, 'XLarge': 50},
    'Other': {'Small': 1, 'Medium': 10, 'Large': 50, 'XLarge': 100},
}

SIZE_TIER_CHOICES = [
    ('Small', 'Small'),
    ('Medium', 'Medium'),
    ('Large', 'Large'),
    ('XLarge', 'X-Large'),
    ('Custom', 'Custom (enter exact units)'),
]


class DatabaseResource(models.Model):
    name=models.CharField(max_length=100, null=True)
    description=models.TextField(null=True, default='')
    category=models.CharField(max_length=20, choices=CATEGORY, null=True)
    capacity_units=models.PositiveIntegerField(null=True, default=0, verbose_name='Total Capacity')
    allocated_units=models.PositiveIntegerField(null=True, default=0, verbose_name='Allocated Capacity')
    is_active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'Database Resource'
        verbose_name_plural = 'Database Resources'

    def __str__(self):
        return f'{self.name}'

    @property
    def unit(self):
        return CATEGORY_UNITS.get(self.category, 'units')

    @property
    def handle(self):
        code = CATEGORY_CODE.get(self.category, 'res')
        return f'res-{code}-{(self.pk or 0):05d}'

    @property
    def available_units(self):
        return (self.capacity_units or 0) - (self.allocated_units or 0)

    @property
    def utilization(self):
        capacity = self.capacity_units or 0
        if not capacity:
            return 0
        return (self.allocated_units or 0) / capacity * 100


class DatabaseTransaction(models.Model):

    TRANSACTION_STATE_CHOICES = [
        ('CREATED', 'Created'),
        ('PENDING', 'Pending'),
        ('VALIDATED', 'Validated'),
        ('EXECUTING', 'Executing'),
        ('COMMITTED', 'Committed'),
        ('ROLLED_BACK', 'Rolled Back'),
        ('FAILED', 'Failed'),
    ]

    resource = models.ForeignKey(DatabaseResource, on_delete=models.CASCADE, null=True, verbose_name='Database Resource')
    staff = models.ForeignKey(User, on_delete=models.CASCADE, null=True, verbose_name='Transaction Operator')
    requested_units = models.PositiveIntegerField(null=True)
    date = models.DateTimeField(auto_now_add=True)
    committed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATE_CHOICES, default='CREATED', verbose_name='Transaction State')

    def __str__(self):
        return f'Transaction #{self.pk} [{self.status}] on {self.resource}'


class TransactionAudit(models.Model):
    transaction = models.ForeignKey(DatabaseTransaction, on_delete=models.CASCADE, related_name='audit_trail')
    from_state = models.CharField(max_length=20, blank=True, default='')
    to_state = models.CharField(max_length=20)
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Transaction Audit Entry'
        verbose_name_plural = 'Transaction Audit Log'

    def __str__(self):
        return f'Transaction #{self.transaction_id}: {self.from_state or "start"} -> {self.to_state}'


class Information(models.Model):
    content = models.CharField(max_length=200)

    def __str__(self):
        return self.content
