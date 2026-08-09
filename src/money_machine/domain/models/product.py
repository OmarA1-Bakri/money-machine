"""Product build and quality-assurance contracts."""

from pydantic import AwareDatetime

from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.value_objects import FrozenModel, NonEmptyStr, Sha256


class BuildResult(FrozenModel):
    """Manifest-backed result of the deterministic local product build."""

    build_id: NonEmptyStr
    product_spec_id: NonEmptyStr
    root_artifact_path: NonEmptyStr
    artifacts: tuple[ArtifactReference, ...]
    manifest_sha256: Sha256
    renderer_version: NonEmptyStr


class ProductQAResult(FrozenModel):
    """Deterministic product QA verdict and all ordered findings."""

    qa_result_id: NonEmptyStr
    build_id: NonEmptyStr
    passed: bool
    findings: tuple[str, ...]
    checked_at: AwareDatetime
    result_sha256: Sha256
