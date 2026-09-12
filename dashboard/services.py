import logging

from django.contrib.auth.models import User
from django.db import transaction as db_transaction
from django.utils import timezone

from .exceptions import InsufficientResourceError, InvalidTransitionError
from .models import DatabaseResource, DatabaseTransaction, TransactionAudit

logger = logging.getLogger(__name__)

ALLOWED_TRANSITIONS = {
    'CREATED': {'PENDING', 'ROLLED_BACK'},
    'PENDING': {'VALIDATED', 'ROLLED_BACK'},
    'VALIDATED': {'EXECUTING', 'ROLLED_BACK'},
    'EXECUTING': {'COMMITTED', 'FAILED'},
    'COMMITTED': set(),
    'ROLLED_BACK': set(),
    'FAILED': {'PENDING'},
}


class TransactionService:
    """Single choke point for every DatabaseTransaction state change, so the
    lifecycle, capacity allocation, and audit trail can never drift apart."""

    @staticmethod
    def transition(txn: DatabaseTransaction, to_state: str, operator: User, note: str = "") -> DatabaseTransaction:
        allowed = ALLOWED_TRANSITIONS.get(txn.status, set())
        if to_state not in allowed:
            raise InvalidTransitionError(
                f"Cannot move transaction #{txn.pk} from {txn.status} to {to_state}"
            )
        from_state = txn.status
        with db_transaction.atomic():
            txn.status = to_state
            txn.save(update_fields=['status'])
            TransactionAudit.objects.create(
                transaction=txn,
                from_state=from_state,
                to_state=to_state,
                operator=operator,
                note=note,
            )
        logger.info("Transaction #%s: %s -> %s (operator=%s)", txn.pk, from_state, to_state, operator)
        return txn

    @staticmethod
    def create(resource: DatabaseResource, operator: User, units: int) -> DatabaseTransaction:
        with db_transaction.atomic():
            resource = DatabaseResource.objects.select_for_update().get(pk=resource.pk)
            if units > resource.available_units:
                raise InsufficientResourceError(
                    f"Requested {units} {resource.unit} exceeds available capacity "
                    f"({resource.available_units} {resource.unit}) for {resource}"
                )

            existing = DatabaseTransaction.objects.filter(
                resource=resource, staff=operator, status='CREATED'
            ).first()

            resource.allocated_units = (resource.allocated_units or 0) + units
            resource.save(update_fields=['allocated_units'])

            if existing:
                existing.requested_units = (existing.requested_units or 0) + units
                existing.save(update_fields=['requested_units'])
                txn = existing
            else:
                txn = DatabaseTransaction.objects.create(
                    resource=resource, staff=operator, requested_units=units, status='CREATED'
                )
                TransactionAudit.objects.create(
                    transaction=txn, from_state='', to_state='CREATED', operator=operator,
                )

        logger.info(
            "Allocation reserved: resource=%s operator=%s units=%s",
            resource, operator, units,
        )
        return txn

    @staticmethod
    def rollback(txn: DatabaseTransaction, operator: User, reason: str = "") -> DatabaseTransaction:
        with db_transaction.atomic():
            resource = DatabaseResource.objects.select_for_update().get(pk=txn.resource_id)
            resource.allocated_units = max(0, (resource.allocated_units or 0) - (txn.requested_units or 0))
            resource.save(update_fields=['allocated_units'])
            TransactionService.transition(txn, 'ROLLED_BACK', operator, note=reason or 'Allocation released')
        return txn

    @staticmethod
    def commit(txn: DatabaseTransaction, operator: User) -> DatabaseTransaction:
        if txn.status == 'COMMITTED':
            logger.info("Transaction #%s already committed; ignoring duplicate commit request", txn.pk)
            return txn

        with db_transaction.atomic():
            txn = DatabaseTransaction.objects.select_for_update().get(pk=txn.pk)
            if txn.status == 'COMMITTED':
                return txn

            # Capacity was reserved against the resource at creation time; commit
            # promotes that reservation to a live allocation and timestamps it.
            TransactionService.transition(txn, 'EXECUTING', operator, note='Beginning commit')
            txn.committed_at = timezone.now()
            txn.save(update_fields=['committed_at'])
            TransactionService.transition(txn, 'COMMITTED', operator, note='Commit successful')

        return txn
