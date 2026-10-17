"""Earn the Session 11 intake key.

The proof does not open a socket, read a credential, insert a job, or send a message.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from money_machine.assets.support_intake import (
    IntakeLedger,
    IntakeRecord,
    SupportRefusal,
    open_issue,
)

INTAKE_EVIDENCE_KEY = "support_intake_implemented"
EARNED_EVIDENCE_KEYS = frozenset({INTAKE_EVIDENCE_KEY})
_WHEN = datetime(2026, 10, 16, 12, tzinfo=UTC)
_LATER = datetime(2026, 10, 16, 12, 5, tzinfo=UTC)
_SHOP = UUID("00000000-0000-4000-8000-000000000011")
_LISTING = UUID("00000000-0000-4000-8000-000000000012")
_PRODUCT = UUID("00000000-0000-4000-8000-000000000013")
_VARIANT = UUID("00000000-0000-4000-8000-000000000014")
_HASH = "ab" * 32
_SECRET = "sk_exampletoken"


class Session11ProofError(ValueError):
    """The Session 11 fixture did not earn its evidence key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prove_session_11() -> frozenset[str]:
    """Return the earned Session 11 keys. A miss raises instead of returning them."""
    _prove_intake()
    return EARNED_EVIDENCE_KEYS


def _open(
    ledger: IntakeLedger,
    *,
    received_at: datetime = _WHEN,
    safe_summary: str = "the purchase cannot be used",
    buyer_reference: str = "buyer-opaque-1",
) -> IntakeRecord:
    return open_issue(
        ledger,
        shop_id=_SHOP,
        buyer_reference=buyer_reference,
        listing_id=_LISTING,
        product_id=_PRODUCT,
        variant_id=_VARIANT,
        issue_code="BROKEN_DELIVERY_LINK",
        safe_summary=safe_summary,
        attachment_sha256=_HASH,
        attachment_content_type="application/pdf",
        received_at=received_at,
        urgency="normal",
    )


def _prove_intake() -> None:
    if "incident_id" in inspect.signature(open_issue).parameters:
        raise Session11ProofError("intake_id")
    ledger = IntakeLedger()
    first = _open(ledger)
    second = _open(ledger, safe_summary="a later safe note")
    if (
        second.incident_id != first.incident_id
        or second.safe_summary != first.safe_summary
        or len(ledger.issues()) != 1
    ):
        raise Session11ProofError("intake_idempotent")
    other = _open(ledger, received_at=_LATER)
    if other.incident_id == first.incident_id or len(ledger.issues()) != 2:
        raise Session11ProofError("intake_key")
    if (
        first.attachment_sha256 != _HASH
        or first.attachment_content_type != "application/pdf"
        or isinstance(first.attachment_sha256, bytes)
        or first.send_count != 0
        or first.provider_writes != 0
        or first.jobs_inserted != 0
        or any(step.inserted for step in first.plan)
    ):
        raise Session11ProofError("intake_store")
    try:
        _open(IntakeLedger(), safe_summary=f"see {_SECRET}")
    except SupportRefusal as error:
        if error.code != "unsafe_summary" or _SECRET in str(error):
            raise Session11ProofError("intake_secret") from error
    else:
        raise Session11ProofError("intake_secret")
    source = Path(open_issue.__code__.co_filename).read_text(encoding="utf-8")
    if (
        "import httpx" in source
        or "import socket" in source
        or "SESSION_11_SUPPORT_AND_REPAIR_COMPLETE" in source
    ):
        raise Session11ProofError("intake_boundary")
    root = Path(__file__).resolve().parents[3]
    block = (root / "config" / "agents.yaml").read_text(encoding="utf-8").split("agent_id: A16", 1)
    if len(block) != 2:
        raise Session11ProofError("intake_a16")
    agent = block[1]
    if "commissioning_state: DESIGNED" not in agent or "commissioning_evidence: []" not in agent:
        raise Session11ProofError("intake_a16")
