class ApplicationError(Exception):
    """Base application-layer error, independent from transport concerns."""


class NotFoundError(ApplicationError):
    """Raised when an expected entity does not exist."""


class ConflictError(ApplicationError):
    """Raised when a uniqueness or state conflict occurs."""


class ForbiddenError(ApplicationError):
    """Raised when operation is forbidden by business rules."""


class ValidationError(ApplicationError):
    """Raised when application-level validation fails."""
