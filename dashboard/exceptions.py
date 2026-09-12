class TransactionError(Exception):
    """Base class for transaction-lifecycle errors."""


class InsufficientResourceError(TransactionError):
    """Raised when a transaction requests more of a resource than is available."""


class InvalidTransitionError(TransactionError):
    """Raised when a transaction attempts to move to a state it cannot legally reach from its current state."""
