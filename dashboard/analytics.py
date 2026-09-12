from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from .models import DatabaseResource, DatabaseTransaction, TransactionAudit


def transaction_state_counts():
    counts = {state: 0 for state, _ in DatabaseTransaction.TRANSACTION_STATE_CHOICES}
    for row in DatabaseTransaction.objects.values('status').annotate(total=Count('id')):
        counts[row['status']] = row['total']
    return counts


def average_commit_time():
    """Averaged in Python rather than via Avg(DurationField): SQLite doesn't
    support aggregating (Sum/Avg) over duration expressions, only computing them."""
    pairs = DatabaseTransaction.objects.filter(
        status='COMMITTED', committed_at__isnull=False
    ).values_list('date', 'committed_at')
    durations = [committed_at - date for date, committed_at in pairs if date and committed_at]
    if not durations:
        return None
    return sum(durations, timedelta()) / len(durations)


def throughput(window=timedelta(hours=24)):
    since = timezone.now() - window
    return DatabaseTransaction.objects.filter(status='COMMITTED', committed_at__gte=since).count()


def capacity_totals():
    totals = DatabaseResource.objects.filter(is_active=True).aggregate(
        capacity=Sum('capacity_units'), allocated=Sum('allocated_units')
    )
    return (totals['capacity'] or 0), (totals['allocated'] or 0)


def resource_utilization():
    capacity, allocated = capacity_totals()
    return (allocated / capacity * 100) if capacity else 0


def _resolved_rate(state, counts=None):
    """Percentage of *resolved* transactions (COMMITTED/FAILED/ROLLED_BACK) that
    ended in `state`. In-flight transactions (CREATED/PENDING/VALIDATED/EXECUTING)
    are excluded from the denominator since they haven't reached an outcome yet."""
    counts = counts or transaction_state_counts()
    resolved = counts['COMMITTED'] + counts['FAILED'] + counts['ROLLED_BACK']
    return (counts[state] / resolved * 100) if resolved else 0


def success_rate(counts=None):
    return _resolved_rate('COMMITTED', counts)


def failure_rate(counts=None):
    return _resolved_rate('FAILED', counts)


def rollback_rate(counts=None):
    return _resolved_rate('ROLLED_BACK', counts)


def recent_audit_events(to_states=('FAILED', 'ROLLED_BACK'), limit=10):
    return list(
        TransactionAudit.objects.filter(to_state__in=to_states)
        .select_related('transaction', 'operator')
        .order_by('-timestamp')[:limit]
    )


def commit_allocation_breakdown():
    committed = DatabaseTransaction.objects.filter(status='COMMITTED')
    return list(
        committed.values('resource__name', 'resource__category').annotate(
            allocated_units=Sum('requested_units'),
            transaction_count=Count('id'),
        )
    )


def build_summary_text():
    counts = transaction_state_counts()
    avg_commit = average_commit_time()
    util = resource_utilization()
    capacity, allocated = capacity_totals()
    recent_events = recent_audit_events()

    lines = ["Transaction state counts:"]
    for state, count in counts.items():
        lines.append(f"- {state}: {count}")
    lines.append(f"Average commit time: {avg_commit}")
    lines.append(f"Total capacity: {capacity} units; allocated: {allocated} units")
    lines.append(f"Resource utilization: {util:.1f}%")
    lines.append(f"Committed in the last 24h (throughput): {throughput()}")
    lines.append(
        f"Success rate: {success_rate(counts):.1f}% | "
        f"Failure rate: {failure_rate(counts):.1f}% | "
        f"Rollback rate: {rollback_rate(counts):.1f}% "
        "(rates computed over resolved transactions only)"
    )
    lines.append("Recent failures/rollbacks:")
    for event in recent_events:
        lines.append(
            f"- Transaction #{event.transaction_id}: {event.from_state} -> {event.to_state} "
            f"({event.note or 'no note'}) at {event.timestamp}"
        )
    return "\n".join(lines)
