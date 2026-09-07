"""Domain contract errors."""


class InvalidTransitionError(ValueError):
    """Raised when a requested lifecycle or job transition is not admitted."""
