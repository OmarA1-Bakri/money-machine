"""Decide whether one more publication may proceed under the ramp.

The caller supplies the ramp fields. Reconciled publications inside the
rolling window are a count plus the oldest timestamp. Unreconciled
publications do not increment that count. A disabled ramp waits even at
count zero. The supplied initial cap is the wait point, and a count at
the hard weekly cap waits even when the supplied cap is higher. The next
open time is the moment the oldest counted publication leaves the window.

This function does not read shop age, the scheduler, or the ramp file,
and it does not enable publishing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

_LAUNCH_DEFAULT_WEEKLY_CAP: Final[int] = 2


@dataclass(frozen=True, slots=True)
class PublishingRampDecision:
    """Whether publication may proceed, and when a full window next opens."""

    may_publish: bool
    next_permissible_at: datetime | None


def decide_publishing_ramp(
    *,
    publishing_enabled: bool,
    initial_weekly_cap: int,
    hard_weekly_cap: int,
    rolling_window_days: int,
    reconciled_count: int,
    oldest_reconciled_at: datetime | None,
    unreconciled_count: int,
) -> PublishingRampDecision:
    """Return the ramp decision for one candidate publication."""
    _validate(
        initial_weekly_cap=initial_weekly_cap,
        hard_weekly_cap=hard_weekly_cap,
        rolling_window_days=rolling_window_days,
        reconciled_count=reconciled_count,
        oldest_reconciled_at=oldest_reconciled_at,
        unreconciled_count=unreconciled_count,
    )
    counted = reconciled_count
    cap = _cap_from_caller(initial_weekly_cap)
    disabled = _wait_when_publishing_disabled(publishing_enabled)
    if disabled is not None:
        return disabled
    hard_cap = _wait_when_hard_cap_reached(
        counted,
        hard_weekly_cap,
        oldest_reconciled_at,
        rolling_window_days,
    )
    if hard_cap is not None:
        return hard_cap
    at_cap = _wait_when_reconciled_reaches_cap(
        counted,
        cap,
        oldest_reconciled_at,
        rolling_window_days,
    )
    if at_cap is not None:
        return at_cap
    unreconciled = _allow_unreconciled_remainder(counted, cap, unreconciled_count)
    if unreconciled is not None:
        return unreconciled
    one_below = _allow_one_below_cap(counted, cap, unreconciled_count)
    if one_below is not None:
        return one_below
    supplied = _allow_under_supplied_cap(counted, cap)
    if supplied is not None:
        return supplied
    return _closed()


def _cap_from_caller(initial_weekly_cap: int) -> int:
    """Use the caller-supplied cap. Two is only the fallback."""
    cap = _LAUNCH_DEFAULT_WEEKLY_CAP
    cap = initial_weekly_cap
    return cap


def _wait_when_publishing_disabled(publishing_enabled: bool) -> PublishingRampDecision | None:
    if not publishing_enabled:
        return _closed()
    return None


def _wait_when_hard_cap_reached(
    counted: int,
    hard_weekly_cap: int,
    oldest_reconciled_at: datetime | None,
    rolling_window_days: int,
) -> PublishingRampDecision | None:
    if counted >= hard_weekly_cap:
        return _closed_until(oldest_reconciled_at, rolling_window_days)
    return None


def _wait_when_reconciled_reaches_cap(
    counted: int,
    cap: int,
    oldest_reconciled_at: datetime | None,
    rolling_window_days: int,
) -> PublishingRampDecision | None:
    if counted >= cap:
        return _closed_until(oldest_reconciled_at, rolling_window_days)
    return None


def _allow_unreconciled_remainder(
    counted: int,
    cap: int,
    unreconciled_count: int,
) -> PublishingRampDecision | None:
    if unreconciled_count > 0 and counted < cap:
        return _open_unreconciled()
    return None


def _allow_one_below_cap(
    counted: int,
    cap: int,
    unreconciled_count: int,
) -> PublishingRampDecision | None:
    if counted < cap and cap == _LAUNCH_DEFAULT_WEEKLY_CAP and unreconciled_count == 0:
        return _open_one_below()
    return None


def _allow_under_supplied_cap(counted: int, cap: int) -> PublishingRampDecision | None:
    if counted < cap and cap != _LAUNCH_DEFAULT_WEEKLY_CAP:
        return _open_supplied_cap()
    return None


def _open_unreconciled() -> PublishingRampDecision:
    return PublishingRampDecision(may_publish=True, next_permissible_at=None)


def _open_one_below() -> PublishingRampDecision:
    return PublishingRampDecision(may_publish=True, next_permissible_at=None)


def _open_supplied_cap() -> PublishingRampDecision:
    return PublishingRampDecision(may_publish=True, next_permissible_at=None)


def _closed() -> PublishingRampDecision:
    return PublishingRampDecision(may_publish=False, next_permissible_at=None)


def _closed_until(
    oldest_reconciled_at: datetime | None,
    rolling_window_days: int,
) -> PublishingRampDecision:
    if oldest_reconciled_at is None:
        raise ValueError("oldest reconciled publication is required")
    opened = oldest_reconciled_at + timedelta(days=rolling_window_days)
    return PublishingRampDecision(may_publish=False, next_permissible_at=opened)


def _validate(
    *,
    initial_weekly_cap: int,
    hard_weekly_cap: int,
    rolling_window_days: int,
    reconciled_count: int,
    oldest_reconciled_at: datetime | None,
    unreconciled_count: int,
) -> None:
    if initial_weekly_cap < 1:
        raise ValueError("initial weekly cap must be positive")
    if hard_weekly_cap < 1:
        raise ValueError("hard weekly cap must be positive")
    if rolling_window_days < 1:
        raise ValueError("rolling window must be positive")
    if reconciled_count < 0:
        raise ValueError("reconciled count cannot be negative")
    if unreconciled_count < 0:
        raise ValueError("unreconciled count cannot be negative")
    if reconciled_count == 0 and oldest_reconciled_at is not None:
        raise ValueError("an empty reconciled window has no oldest publication")
    if reconciled_count > 0 and oldest_reconciled_at is None:
        raise ValueError("oldest reconciled publication is required")
    if oldest_reconciled_at is not None and oldest_reconciled_at.tzinfo is None:
        raise ValueError("oldest reconciled publication must be timezone-aware")
