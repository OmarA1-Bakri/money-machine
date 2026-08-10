"""Qualification and shortlist contracts."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from money_machine.domain.value_objects import FrozenModel, NonEmptyStr, Sha256


class QualificationScore(FrozenModel):
    """A candidate's score across the four playbook dimensions."""

    candidate_id: NonEmptyStr
    demand: int = Field(ge=0, le=10)
    differentiation: int = Field(ge=0, le=10)
    build_feasibility: int = Field(ge=0, le=10)
    buyer_value: int = Field(ge=0, le=10)
    evidence_ids: tuple[str, ...]

    @property
    def total(self) -> int:
        """Return the score out of forty."""

        return self.demand + self.differentiation + self.build_feasibility + self.buyer_value

    @property
    def meets_threshold(self) -> bool:
        """Whether the candidate reaches the frozen 30/40 threshold."""

        return self.total >= 30


class CandidateShortlist(FrozenModel):
    """Up to five ranked candidates and the qualifying selection, if any."""

    shortlist_id: NonEmptyStr
    packet_id: NonEmptyStr
    candidates: Annotated[tuple[QualificationScore, ...], Field(min_length=1, max_length=5)]
    selected_candidate_id: str | None
    backup_candidate_id: str | None
    shortlist_sha256: Sha256

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        """Require a selection to identify a shortlisted score of at least 30."""

        if self.selected_candidate_id is None:
            if self.backup_candidate_id is not None:
                raise ValueError("backup candidate requires a selected candidate")
            return self
        selected = next(
            (
                score
                for score in self.candidates
                if score.candidate_id == self.selected_candidate_id
            ),
            None,
        )
        if selected is None:
            raise ValueError("selected candidate must appear in candidates")
        if not selected.meets_threshold:
            raise ValueError("selected candidate must meet the 30/40 threshold")
        if self.backup_candidate_id is None:
            return self
        if self.backup_candidate_id == self.selected_candidate_id:
            raise ValueError("backup candidate must differ from selected candidate")
        backup = next(
            (score for score in self.candidates if score.candidate_id == self.backup_candidate_id),
            None,
        )
        if backup is None:
            raise ValueError("backup candidate must appear in candidates")
        if not backup.meets_threshold:
            raise ValueError("backup candidate must meet the 30/40 threshold")
        return self
