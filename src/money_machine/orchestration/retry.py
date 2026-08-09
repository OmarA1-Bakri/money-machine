"""Bounded retry classification without transactional sleeping."""

from datetime import timedelta

from money_machine.domain.enums import RetryClass

_RETRYABLE = frozenset({RetryClass.TRANSIENT_INTERNAL, RetryClass.TRANSIENT_PROVIDER_READ})


def retry_delay(retry_class: RetryClass | str, attempt_number: int) -> timedelta | None:
    """Return the deterministic exponential delay, capped at five minutes."""

    if attempt_number < 1:
        raise ValueError("attempt_number must be positive")
    classification = RetryClass(retry_class)
    if classification not in _RETRYABLE:
        return None
    seconds = min(5 * (2 ** (attempt_number - 1)), 300)
    return timedelta(seconds=seconds)
