"""Deterministic identities for replay-safe workflow construction."""

from uuid import UUID, uuid5

_WORKFLOW_NAMESPACE = UUID("6659719d-8c80-54e0-b89d-fba2ef9cb999")


def workflow_identity(packet_id: str) -> UUID:
    normalized = packet_id.strip()
    if not normalized:
        raise ValueError("packet_id must not be empty")
    return uuid5(_WORKFLOW_NAMESPACE, f"packet:{normalized}")


def job_identity(workflow_run_id: UUID, position: int, job_type: str) -> UUID:
    if position < 0 or not job_type.strip():
        raise ValueError("job identity inputs are invalid")
    return uuid5(workflow_run_id, f"job:{position}:{job_type}")


def workflow_idempotency_key(packet_id: str) -> str:
    return f"first-product:{packet_id.strip()}"


def job_idempotency_key(workflow_run_id: UUID, position: int, job_type: str) -> str:
    return f"{workflow_run_id}:{position}:{job_type}"
