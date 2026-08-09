"""Deterministic, truth-bound listing package assembly."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from money_machine.domain.models.listing import ListingPackage
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.services.claim_validation import (
    AdmittedFact,
    ClaimRecord,
    ClaimValidationService,
    FactCategory,
)
from money_machine.domain.value_objects import canonical_sha256

_NON_TAG = re.compile(r"[^a-z0-9 ]+")
_SPACE = re.compile(r"\s+")
_TEMPLATE_ROOT = Path(__file__).resolve().parents[4] / "templates"
_BUYER_FIT = re.compile(
    r"^[A-Za-z][A-Za-z -]+ (?:who need (?:a|an|the)|planning) [A-Za-z][A-Za-z -]+$"
)
_FEATURE = re.compile(r"^[A-Za-z][A-Za-z ]+ and [A-Za-z][A-Za-z ]+ views$")
_WORKFLOW_OUTCOME = re.compile(
    r"^(?:Organize|Plan|Track|Manage|Centralize|Simplify|Customize|Access) "
    r"[A-Za-z][A-Za-z -]+$"
)


def _tag(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    normalized = _NON_TAG.sub(" ", normalized.casefold().replace("-", " "))
    words = _SPACE.sub(" ", normalized).strip().split()
    while words and len(" ".join(words)) > 20:
        words.pop()
    return " ".join(words)


def _unique_tags(candidates: Iterable[str]) -> tuple[str, ...]:
    tags: list[str] = []
    for candidate in candidates:
        normalized = _tag(candidate)
        if normalized and normalized not in tags:
            tags.append(normalized)
        if len(tags) == 13:
            return tuple(tags)
    raise ValueError("cannot produce thirteen compliant unique tags without filler")


def _listing_title(spec: ProductSpec) -> str:
    niche = " ".join(
        word.upper() if word.casefold() in {"adhd", "pdf"} else word.title()
        for word in spec.identity_niche.split()
    )
    category = " ".join(word.capitalize() for word in spec.base_category.split())
    words = f"{niche} {category}".split()
    while words and len(" ".join(words)) > 140:
        words.pop()
    title = " ".join(words)
    if not title:
        raise ValueError("cannot produce a compliant title")
    return title


def listing_package_sha256(package: ListingPackage) -> str:
    """Hash all package fields except the self-referential digest."""

    return canonical_sha256(package.model_dump(mode="json", exclude={"package_sha256"}))


def copy_package_sha256(package: ListingPackage) -> str:
    """Recover the hash of the copy-only package before asset rendering."""

    copy_only = package.model_copy(
        update={
            "listing_images": (),
            "preview_video": None,
            "preview_video_status": "NOT_GENERATED",
            "delivery_document": None,
            "package_manifest": None,
            "package_sha256": "0" * 64,
        }
    )
    return listing_package_sha256(copy_only)


def _joined(values: tuple[str, ...]) -> str:
    if len(values) == 1:
        return values[0].casefold()
    return f"{', '.join(values[:-1]).casefold()}, and {values[-1].casefold()}"


def admitted_product_facts(spec: ProductSpec) -> tuple[AdmittedFact, ...]:
    """Derive the only admissible factual claims from typed ProductSpec fields."""

    if not spec.source_evidence_ids:
        return ()
    evidence_ids = spec.source_evidence_ids
    number_words = {6: "six", 7: "seven", 8: "eight"}
    candidates: list[tuple[str, FactCategory]] = []
    hub_count = number_words.get(len(spec.hubs))
    if hub_count is not None:
        candidates.append((f"Includes {hub_count} navigation hubs", "HUB_INVENTORY"))
    candidates.extend(
        (f"Includes {feature[:1].lower()}{feature[1:]}", "FEATURE")
        for feature in spec.features
        if _FEATURE.fullmatch(feature)
    )
    candidates.append(
        (f"Available in {_joined(spec.colour_variants)} colour variants", "COLOUR_VARIANTS")
    )
    if _BUYER_FIT.fullmatch(spec.target_buyer):
        candidates.append((spec.target_buyer, "BUYER_FIT"))
    if _WORKFLOW_OUTCOME.fullmatch(spec.promised_outcome):
        candidates.append((spec.promised_outcome, "WORKFLOW_OUTCOME"))
    declared = set(spec.product_facts)
    return tuple(
        AdmittedFact(claim=claim, category=category, evidence_ids=evidence_ids)
        for claim, category in candidates
        if claim in declared
    )


def listing_claim_records(spec: ProductSpec, package: ListingPackage) -> tuple[ClaimRecord, ...]:
    """Rebuild the complete, typed claim ledger from the admitted ProductSpec."""

    structural = (
        _listing_title(spec),
        f"A digital {spec.base_category} for {spec.identity_niche}.",
        f"The workspace is organized around: {', '.join(spec.hubs)}.",
        f"Choose from {', '.join(spec.colour_variants)}.",
        "Digital download. Setup guidance is included in the delivery PDF.",
        "Support information and a duplication reminder are included.",
    )
    claims = tuple(
        dict.fromkeys(
            (
                package.title,
                *package.feature_statements,
                spec.target_buyer,
                spec.promised_outcome,
                *structural[1:],
            )
        )
    )
    result = ClaimValidationService().validate(
        claims,
        spec.product_facts,
        admitted_facts=admitted_product_facts(spec),
        structural_claims=structural,
    )
    if not result.passed:
        raise ValueError("listing contains a claim not bound to an admitted product fact")
    return result.records


class ListingService:
    """Create replay-stable merchandising from frozen Task 2 contracts."""

    def create(
        self,
        spec: ProductSpec,
        build: BuildResult,
        qa: ProductQAResult,
    ) -> ListingPackage:
        if build.product_spec_id != spec.product_spec_id:
            raise ValueError("build does not belong to ProductSpec")
        if qa.build_id != build.build_id:
            raise ValueError("QA build does not match build")
        if not qa.passed:
            raise ValueError("product QA must pass before merchandising")

        validation = ClaimValidationService().validate(
            spec.product_facts,
            spec.product_facts,
            admitted_facts=admitted_product_facts(spec),
        )
        if not validation.passed:
            raise ValueError("ProductSpec contains an unsupported product fact")

        title = _listing_title(spec)

        facts = "\n".join(f"- {fact}" for fact in spec.product_facts)
        hubs = ", ".join(spec.hubs)
        colours = ", ".join(spec.colour_variants)
        environment = Environment(
            loader=FileSystemLoader(_TEMPLATE_ROOT),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=False,
        )
        description = environment.get_template("listing/description.md.j2").render(
            overview=f"A digital {spec.base_category} for {spec.identity_niche}.",
            product_facts=facts,
            promised_outcome=spec.promised_outcome,
            hubs=f"The workspace is organized around: {hubs}.",
            colour_variants=f"Choose from {colours}.",
            target_buyer=spec.target_buyer,
            access_instructions="Digital download. Setup guidance is included in the delivery PDF.",
            support_information="Support information and a duplication reminder are included.",
        )

        candidates = (
            spec.identity_niche,
            spec.base_category,
            f"{spec.identity_niche} {spec.base_category}",
            spec.target_buyer,
            spec.promised_outcome,
            "digital download",
            *spec.hubs,
            *(f"{colour} {spec.base_category}" for colour in spec.colour_variants),
            *(f"{hub} {spec.base_category}" for hub in spec.hubs),
            *(
                " ".join(spec.target_buyer.split()[index : index + 2])
                for index in range(len(spec.target_buyer.split()) - 1)
            ),
            *(
                " ".join(spec.promised_outcome.split()[index : index + 2])
                for index in range(len(spec.promised_outcome.split()) - 1)
            ),
        )
        tags = _unique_tags(candidates)
        draft = ListingPackage(
            listing_package_id=f"listing-{spec.product_spec_id}-{build.build_id}",
            product_spec_id=spec.product_spec_id,
            build_id=build.build_id,
            title=title,
            description=description,
            tags=tags,
            feature_statements=spec.product_facts,
            buyer_fit_statements=(spec.target_buyer, spec.promised_outcome),
            preview_video_status="NOT_GENERATED",
            package_sha256="0" * 64,
        )
        package = draft.model_copy(update={"package_sha256": listing_package_sha256(draft)})
        listing_claim_records(spec, package)
        return package
