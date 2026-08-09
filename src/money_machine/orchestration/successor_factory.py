"""Validation for the immutable first-product successor sequence."""

from money_machine.orchestration.workflows.product_experiment import FIRST_PRODUCT_JOB_SEQUENCE


class SuccessorFactory:
    """Reject skipped, duplicated, backward, or unknown successors."""

    def expected_after(self, job_type: str) -> str | None:
        try:
            position = FIRST_PRODUCT_JOB_SEQUENCE.index(job_type)
        except ValueError as exc:
            raise ValueError(f"unknown job type: {job_type}") from exc
        if position == len(FIRST_PRODUCT_JOB_SEQUENCE) - 1:
            return None
        return FIRST_PRODUCT_JOB_SEQUENCE[position + 1]

    def validate(self, job_type: str, proposed: str | None) -> None:
        expected = self.expected_after(job_type)
        if proposed != expected:
            raise ValueError(
                f"undeclared successor for {job_type}: expected {expected!r}, got {proposed!r}"
            )
