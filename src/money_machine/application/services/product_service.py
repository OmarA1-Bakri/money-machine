"""Deterministic local product build and quality-assurance services."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import stat
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from itertools import pairwise
from pathlib import Path, PurePosixPath
from typing import TypedDict, cast
from urllib.parse import unquote, urlsplit
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select

from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import DedupeResult, ProductSpec
from money_machine.domain.value_objects import canonical_sha256
from money_machine.integrations.notion.interface import (
    ProductBundleBuilder,
    deterministic_build_id,
)
from money_machine.persistence.database import Database
from money_machine.persistence.tables import dedupe_results
from money_machine.persistence.unit_of_work import UnitOfWork

_PLACEHOLDER = re.compile(r"{{|\bTODO\b|lorem ipsum", re.IGNORECASE)
_CSS_THEME_NAME = re.compile(r'--theme-name:\s*"[^"]+"')
_CSS_HSL = re.compile(r"hsl\(\d+")
_SLUG_RUN = re.compile(r"[^a-z0-9]+")
_CSS_REMOTE = re.compile(
    r"(?:@import\s+(?:url\()?\s*|url\(\s*)[\"']?(?P<url>[^\"')\s;]+)",
    re.IGNORECASE,
)
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_CSS_ESCAPE = re.compile(r"\\(?:(?P<hex>[0-9a-fA-F]{1,6})\s?|(?P<char>.))", re.DOTALL)
_CSS_FUNCTION = re.compile(r"(?P<name>-?[_a-z][-_a-z0-9]*)\s*\(", re.IGNORECASE)
_CSS_AT_RULE = re.compile(r"@\s*[-_a-z]", re.IGNORECASE)
_ALLOWED_CSS_FUNCTIONS = frozenset({"hsl", "var"})
_BASIC_REQUIRED_PATHS = frozenset({"product.json", "README.md", "home.html"})
_ALLOWED_TAG_ATTRIBUTES: Mapping[str, frozenset[str]] = {
    "html": frozenset({"lang"}),
    "head": frozenset(),
    "meta": frozenset({"charset", "name", "content"}),
    "title": frozenset(),
    "link": frozenset({"rel", "href"}),
    "body": frozenset(),
    "header": frozenset(),
    "main": frozenset(),
    "section": frozenset({"aria-label", "data-build-progress"}),
    "nav": frozenset({"aria-label"}),
    "p": frozenset(),
    "strong": frozenset(),
    "ul": frozenset(),
    "li": frozenset(),
    "h1": frozenset(),
    "h2": frozenset(),
    "h3": frozenset(),
    "a": frozenset({"href", "aria-label", "title"}),
    "img": frozenset({"src", "srcset", "alt"}),
    "button": frozenset({"type", "aria-label", "title"}),
}
_SEMANTIC_METADATA_NAMES = frozenset(
    {
        "description",
        "title",
        "og:title",
        "og:description",
        "twitter:title",
        "twitter:description",
    }
)
_VIEWPORT_CONTENT = "width=device-width, initial-scale=1"
_AMBIGUOUS_CONTROL_NAMES = frozenset(
    {"click here", "here", "learn more", "more", "read more", "link", "go"}
)


class _ManifestArtifact(TypedDict):
    path: str
    media_type: str
    byte_count: int
    sha256: str


class _Manifest(TypedDict):
    schema_version: int
    product_spec_id: str
    renderer_version: str
    artifacts: list[_ManifestArtifact]


class _ControlState(TypedDict):
    tag: str
    label: str
    text: list[str]
    index: int


class ProductService:
    """Handle the build and QA steps of the first-product workflow."""

    def __init__(
        self,
        artifact_root: Path,
        builder: ProductBundleBuilder,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._artifact_root = artifact_root
        self._builder = builder
        self._qa = ProductQAService(clock=clock)

    def build_local_product(
        self,
        spec: ProductSpec,
        dedupe: DedupeResult,
        workflow_run_id: UUID,
    ) -> BuildResult:
        """Build only the exact specification approved by catalogue dedupe."""

        if not dedupe.passed or dedupe.product_spec_id != spec.product_spec_id:
            raise ValueError("BUILD_PRODUCT requires a dedupe-approved ProductSpec")
        spec.ensure_truth_contract()
        destination = self._artifact_root / str(workflow_run_id) / "product"
        return self._builder.build(spec, destination)

    def run_product_qa(self, build: BuildResult) -> ProductQAResult:
        """Evaluate the stored build result without creating a successor."""

        return self._qa.evaluate(build)

    async def handle_build_local_product(
        self,
        *,
        database: Database,
        product_spec_id: str,
        dedupe_result_id: str,
        workflow_run_id: UUID,
    ) -> BuildResult:
        """Load exact persisted predecessors and persist the deterministic build."""

        async with UnitOfWork(database) as uow:
            spec = await uow.products.get_spec(product_spec_id)
            if spec is None:
                raise ValueError(f"ProductSpec not found: {product_spec_id}")
            session = uow.session
            if session is None:
                raise RuntimeError("UnitOfWork session unavailable")
            payload = (
                await session.execute(
                    select(dedupe_results.c.payload).where(
                        dedupe_results.c.dedupe_result_id == dedupe_result_id
                    )
                )
            ).scalar_one_or_none()
            if payload is None:
                raise ValueError(f"DedupeResult not found: {dedupe_result_id}")
            dedupe = DedupeResult.model_validate_json(json.dumps(payload, separators=(",", ":")))
            build = self.build_local_product(spec, dedupe, workflow_run_id)
            await uow.products.add_build(build)
            return build

    async def handle_run_product_qa(self, *, database: Database, build_id: str) -> ProductQAResult:
        """Load one stored build, evaluate it, and durably persist the verdict."""

        async with UnitOfWork(database) as uow:
            build = await uow.products.get_build(build_id)
            if build is None:
                raise ValueError(f"BuildResult not found: {build_id}")
            result = self.run_product_qa(build)
            await uow.products.add_qa(result)
            return result

    @staticmethod
    def successor_allowed(result: ProductQAResult) -> bool:
        """Permit orchestration to create a successor only after passing QA."""

        return result.passed


class ProductQAService:
    """Verify one manifest-backed product bundle without leaving its root."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def evaluate(self, build: BuildResult) -> ProductQAResult:
        """Return all deterministic blocking findings for ``build``."""

        findings: set[str] = set()
        root = Path(build.root_artifact_path)
        if root.is_symlink() or not root.is_absolute() or not root.is_dir():
            findings.add("BUILD_ROOT_INVALID")
            return self._result(build, findings)
        try:
            root_descriptor = _open_absolute_directory(root)
        except OSError:
            findings.add("BUILD_ROOT_INVALID")
            return self._result(build, findings)
        try:
            return self._evaluate_verified_root(build, root_descriptor, findings)
        finally:
            os.close(root_descriptor)

    def _evaluate_verified_root(
        self, build: BuildResult, root_descriptor: int, findings: set[str]
    ) -> ProductQAResult:
        try:
            manifest_bytes = _read_regular_file_at(root_descriptor, PurePosixPath("manifest.json"))
        except FileNotFoundError:
            findings.add("MANIFEST_MISSING")
            return self._result(build, findings)
        except OSError:
            findings.add("SYMLINK_ARTIFACT:manifest.json")
            return self._result(build, findings)
        if hashlib.sha256(manifest_bytes).hexdigest() != build.manifest_sha256:
            findings.add("MANIFEST_HASH_MISMATCH")
        try:
            raw_manifest: object = json.loads(manifest_bytes)
            manifest = _validate_manifest(raw_manifest)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            findings.add("MANIFEST_INVALID")
            return self._result(build, findings)

        if manifest["product_spec_id"] != build.product_spec_id:
            findings.add("MANIFEST_PRODUCT_SPEC_MISMATCH")
        if manifest["renderer_version"] != build.renderer_version:
            findings.add("MANIFEST_RENDERER_MISMATCH")
        if build.build_id != deterministic_build_id(
            build.product_spec_id, build.manifest_sha256, build.renderer_version
        ):
            findings.add("BUILD_ID_MISMATCH")

        manifest_paths: set[str] = set()
        readable: dict[str, bytes] = {}
        for entry in manifest["artifacts"]:
            path_text = entry["path"]
            if PurePosixPath(path_text).is_absolute():
                findings.add(f"ABSOLUTE_ARTIFACT_PATH:{path_text}")
                continue
            if not _is_canonical_relative(path_text):
                findings.add(f"UNSAFE_ARTIFACT_PATH:{path_text}")
                continue
            if path_text in manifest_paths:
                findings.add(f"DUPLICATE_MANIFEST_PATH:{path_text}")
                continue
            manifest_paths.add(path_text)
            try:
                data = _read_regular_file_at(root_descriptor, PurePosixPath(path_text))
            except FileNotFoundError:
                findings.add(f"ARTIFACT_MISSING:{path_text}")
                continue
            except OSError:
                findings.add(f"SYMLINK_ARTIFACT:{path_text}")
                continue
            readable[path_text] = data
            if len(data) != entry["byte_count"]:
                findings.add(f"ARTIFACT_SIZE_MISMATCH:{path_text}")
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                findings.add(f"ARTIFACT_HASH_MISMATCH:{path_text}")

        declared_paths = {reference.relative_path.as_posix() for reference in build.artifacts}
        references_by_path = {
            reference.relative_path.as_posix(): reference for reference in build.artifacts
        }
        if len(references_by_path) != len(build.artifacts):
            findings.add("DUPLICATE_BUILD_ARTIFACT_PATH")
        for missing in sorted(declared_paths - manifest_paths):
            findings.add(f"MANIFEST_ARTIFACT_MISSING:{missing}")
        for unexpected in sorted(manifest_paths - declared_paths):
            findings.add(f"MANIFEST_ARTIFACT_UNEXPECTED:{unexpected}")
        entries_by_path = {entry["path"]: entry for entry in manifest["artifacts"]}
        for path in sorted(declared_paths & manifest_paths):
            reference = references_by_path[path]
            entry = entries_by_path[path]
            if reference.media_type != entry["media_type"]:
                findings.add(f"BUILD_ARTIFACT_MEDIA_TYPE_MISMATCH:{path}")
            if reference.byte_count != entry["byte_count"]:
                findings.add(f"BUILD_ARTIFACT_BYTE_COUNT_MISMATCH:{path}")
            if reference.content_sha256 != entry["sha256"]:
                findings.add(f"BUILD_ARTIFACT_HASH_MISMATCH:{path}")
            expected_id = _artifact_identity(path, entry["media_type"], entry["sha256"])
            if reference.artifact_id != expected_id:
                findings.add(f"BUILD_ARTIFACT_ID_MISMATCH:{path}")

        _check_descriptor_inventory(root_descriptor, manifest_paths, findings)

        for required_path in sorted(_BASIC_REQUIRED_PATHS - manifest_paths):
            findings.add(f"REQUIRED_ARTIFACT_MISSING:{required_path}")

        spec = _load_spec(readable.get("product.json"), findings)
        if spec is not None:
            if spec.product_spec_id != build.product_spec_id:
                findings.add("PRODUCT_SPEC_IDENTITY_MISMATCH")
            _check_exact_artifact_contract(spec, manifest, manifest_paths, findings)
            self._check_structure(spec, readable, manifest_paths, findings)
        self._check_text_and_links(readable, manifest_paths, findings, spec, build.renderer_version)
        return self._result(build, findings)

    def _check_structure(
        self,
        spec: ProductSpec,
        readable: Mapping[str, bytes],
        manifest_paths: set[str],
        findings: set[str],
    ) -> None:
        hub_slugs = tuple(_slug(name) for name in spec.hubs)
        for duplicate in _duplicates(hub_slugs):
            findings.add(f"DUPLICATE_HUB_SLUG:{duplicate}")
        for slug in sorted(set(hub_slugs)):
            path = f"hubs/{slug}.html"
            if path not in manifest_paths or path not in readable:
                findings.add(f"HUB_MISSING:{slug}")

        variant_slugs = tuple(_slug(name) for name in spec.colour_variants)
        for duplicate in _duplicates(variant_slugs):
            findings.add(f"DUPLICATE_VARIANT_SLUG:{duplicate}")
        variant_paths = [f"assets/{slug}.css" for slug in sorted(set(variant_slugs))]
        for path in variant_paths:
            if path not in manifest_paths or path not in readable:
                findings.add(f"VARIANT_MISSING:{path.removeprefix('assets/').removesuffix('.css')}")
        readable_variants = [(path, readable[path]) for path in variant_paths if path in readable]
        if readable_variants:
            baseline = _normalise_theme(readable_variants[0][1])
            for path, data in readable_variants[1:]:
                if _normalise_theme(data) != baseline:
                    findings.add(f"VARIANT_DRIFT:{path}")

        home = readable.get("home.html", b"").decode("utf-8", errors="replace")
        for fact in sorted(item.claim for item in spec.product_facts):
            if fact not in home:
                findings.add(f"FACT_MISSING:{fact}")

    def _check_text_and_links(
        self,
        readable: Mapping[str, bytes],
        manifest_paths: set[str],
        findings: set[str],
        spec: ProductSpec | None,
        renderer_version: str,
    ) -> None:
        for path, data in sorted(readable.items()):
            if not path.endswith((".html", ".md", ".css")):
                continue
            text = data.decode("utf-8", errors="replace")
            if _PLACEHOLDER.search(text):
                findings.add(f"PLACEHOLDER_TEXT:{path}")
            if path.endswith(".css") and _contains_css_network_construct(text):
                findings.add(f"CSS_NETWORK_CONSTRUCT:{path}")
            for match in _CSS_REMOTE.finditer(text):
                url = match.group("url")
                if _is_network_url(url):
                    findings.add(f"UNEXPECTED_NETWORK_URL:{path}->{url}")
                elif _has_unsafe_scheme(url):
                    findings.add(f"UNSAFE_URL_SCHEME:{path}->{url}")
            if not path.endswith(".html"):
                if path == "README.md" and spec is not None:
                    readme_valid, unsupported_copy = _validate_readme(text, spec, renderer_version)
                    if not readme_valid:
                        findings.add("README_INVALID")
                    if unsupported_copy:
                        findings.add("UNSUPPORTED_CLAIM:README.md")
                continue
            parser = _LinkParser()
            parser.feed(text)
            parser.close()
            if spec is not None and _contains_unapproved_html_copy(
                (*parser.text_chunks, *parser.semantic_copy), spec
            ):
                findings.add(f"UNSUPPORTED_CLAIM:{path}")
            for detail in sorted(parser.active_content):
                findings.add(f"ACTIVE_CONTENT:{path}:{detail}")
            for detail in sorted(parser.active_tags):
                findings.add(f"ACTIVE_TAG:{path}:{detail}")
            for detail in sorted(parser.active_attributes):
                findings.add(f"ACTIVE_ATTRIBUTE:{path}:{detail}")
            for detail in sorted(parser.duplicate_attributes):
                findings.add(f"DUPLICATE_ATTRIBUTE:{path}:{detail}")
            if parser.invalid_metadata:
                findings.add(f"INVALID_METADATA:{path}")
            if not parser.has_accessible_h1:
                findings.add(f"ACCESSIBLE_HEADING_MISSING:{path}")
            if not _valid_heading_hierarchy(parser.heading_levels):
                findings.add(f"HEADING_HIERARCHY_INVALID:{path}")
            for index in sorted(parser.empty_control_indexes):
                findings.add(f"EMPTY_LINK_LABEL:{path}:{index}")
            for index in sorted(parser.ambiguous_control_indexes):
                findings.add(f"AMBIGUOUS_CONTROL_NAME:{path}:{index}")
            if parser.malformed_control:
                findings.add(f"MALFORMED_CONTROL:{path}")
            if parser.nested_control:
                findings.add(f"NESTED_CONTROL:{path}")
            if path == "home.html":
                required_sections = {
                    "build-progress": "bundle ready",
                    "product-hubs": "product hubs",
                    "designed-for": "designed for",
                    "verified-product-facts": "verified product facts",
                }
                visible = " ".join(parser.text_chunks).casefold()
                attributes = " ".join(parser.accessible_labels).casefold()
                for section, needle in required_sections.items():
                    if needle not in visible and needle not in attributes:
                        findings.add(f"REQUIRED_SECTION_MISSING:{path}:{section}")
            for link in sorted(parser.links):
                if _is_network_url(link):
                    findings.add(f"UNEXPECTED_NETWORK_URL:{path}->{link}")
                    continue
                if _has_unsafe_scheme(link):
                    findings.add(f"UNSAFE_URL_SCHEME:{path}->{link}")
                    continue
                if "#" in link:
                    findings.add(f"BROKEN_INTERNAL_FRAGMENT:{path}->{link}")
                    continue
                target = link.split("#", 1)[0].split("?", 1)[0]
                if not target:
                    continue
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
                if not _is_canonical_relative(resolved) or resolved not in manifest_paths:
                    findings.add(f"BROKEN_INTERNAL_LINK:{path}->{link}")

    def _result(self, build: BuildResult, findings: Iterable[str]) -> ProductQAResult:
        ordered = tuple(sorted(set(findings)))
        payload = {"build_id": build.build_id, "passed": not ordered, "findings": list(ordered)}
        result_sha256 = canonical_sha256(payload)
        qa_identity = hashlib.sha256(f"{build.build_id}\0{result_sha256}".encode()).hexdigest()
        return ProductQAResult(
            qa_result_id=f"qa-{qa_identity}",
            build_id=build.build_id,
            passed=not ordered,
            findings=ordered,
            checked_at=self._clock(),
            result_sha256=result_sha256,
        )


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: set[str] = set()
        self.active_content: set[str] = set()
        self.active_tags: set[str] = set()
        self.active_attributes: set[str] = set()
        self.duplicate_attributes: set[str] = set()
        self.accessible_labels: list[str] = []
        self.semantic_copy: list[str] = []
        self.text_chunks: list[str] = []
        self.heading_levels: list[int] = []
        self.empty_control_indexes: set[int] = set()
        self.ambiguous_control_indexes: set[int] = set()
        self.malformed_control = False
        self.nested_control = False
        self.invalid_metadata = False
        self._control_stack: list[_ControlState] = []
        self._control_index = 0
        self._h1_depth = 0
        self._h1_text: list[str] = []

    @property
    def has_accessible_h1(self) -> bool:
        return bool("".join(self._h1_text).strip())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered_tag = tag.casefold()
        ordered_attributes = [(name.casefold(), value) for name, value in attrs]
        seen_attributes: set[str] = set()
        duplicate_names: set[str] = set()
        for name, _ in ordered_attributes:
            if name in seen_attributes:
                duplicate_names.add(name)
            seen_attributes.add(name)
        for name in duplicate_names:
            self.duplicate_attributes.add(f"{lowered_tag}[{name}]")
        validated_attributes = () if duplicate_names else tuple(ordered_attributes)
        attributes = dict(validated_attributes)
        allowed_attributes = _ALLOWED_TAG_ATTRIBUTES.get(lowered_tag)
        if allowed_attributes is None:
            self.active_tags.add(lowered_tag)
        if lowered_tag in {"script", "style", "iframe", "object", "embed", "form", "base"}:
            self.active_content.add(lowered_tag)
        if lowered_tag == "meta":
            if (attributes.get("http-equiv") or "").casefold() == "refresh":
                self.active_content.add("meta-refresh")
            self._validate_metadata(attributes)
        if lowered_tag in {"a", "button"}:
            if self._control_stack:
                self.nested_control = True
            self._control_index += 1
            self._control_stack.append(
                {
                    "tag": lowered_tag,
                    "label": attributes.get("aria-label") or attributes.get("title") or "",
                    "text": [],
                    "index": self._control_index,
                }
            )
        if lowered_tag == "h1":
            self._h1_depth += 1
        if re.fullmatch(r"h[1-6]", lowered_tag):
            self.heading_levels.append(int(lowered_tag[1]))
        for label_name in ("aria-label", "title", "alt"):
            label = attributes.get(label_name)
            if label:
                self.accessible_labels.append(label)
                self.semantic_copy.append(label)
        for lowered_name, value in validated_attributes:
            if value is None:
                continue
            if lowered_name.startswith("on") or (
                allowed_attributes is not None and lowered_name not in allowed_attributes
            ):
                self.active_attributes.add(f"{lowered_tag}[{lowered_name}]")
                continue
            if lowered_name in {
                "href",
                "src",
                "action",
                "formaction",
                "poster",
                "data",
                "cite",
                "background",
            }:
                self.links.add(value)
            elif lowered_name == "srcset":
                self.links.update(candidate.strip().split()[0] for candidate in value.split(","))
            elif lowered_name == "style":
                for match in _CSS_REMOTE.finditer(value):
                    self.links.add(match.group("url"))
        if lowered_tag == "img" and self._control_stack:
            image_alt = attributes.get("alt")
            if image_alt:
                for state in self._control_stack:
                    state["text"].append(image_alt)

    def _validate_metadata(self, attributes: Mapping[str, str | None]) -> None:
        if attributes == {"charset": "utf-8"}:
            return
        if set(attributes) != {"name", "content"}:
            self.invalid_metadata = True
            return
        name = attributes["name"]
        content = attributes["content"]
        if name == "viewport" and content == _VIEWPORT_CONTENT:
            return
        if name in _SEMANTIC_METADATA_NAMES and content:
            self.semantic_copy.append(content)
            return
        self.invalid_metadata = True

    def handle_endtag(self, tag: str) -> None:
        lowered_tag = tag.casefold()
        if lowered_tag in {"a", "button"}:
            if not self._control_stack or self._control_stack[-1]["tag"] != lowered_tag:
                self.malformed_control = True
            else:
                self._validate_control(self._control_stack.pop())
        if lowered_tag == "h1" and self._h1_depth:
            self._h1_depth -= 1

    def handle_data(self, data: str) -> None:
        self.text_chunks.append(data)
        for state in self._control_stack:
            state["text"].append(data)
        if self._h1_depth:
            self._h1_text.append(data)

    def close(self) -> None:
        super().close()
        if self._control_stack:
            self.malformed_control = True
            while self._control_stack:
                self._validate_control(self._control_stack.pop())

    def _validate_control(self, state: _ControlState) -> None:
        accessible_name = _collapse_whitespace(state["label"] or "".join(state["text"]))
        semantic_name = _normalise_control_name(accessible_name)
        if not semantic_name:
            self.empty_control_indexes.add(state["index"])
        elif semantic_name in _AMBIGUOUS_CONTROL_NAMES:
            self.ambiguous_control_indexes.add(state["index"])


def _validate_manifest(value: object) -> _Manifest:
    if not isinstance(value, dict):
        raise TypeError("manifest must be an object")
    raw = cast(dict[object, object], value)
    if set(raw) != {
        "schema_version",
        "product_spec_id",
        "renderer_version",
        "artifacts",
    }:
        raise ValueError("invalid manifest fields")
    schema_version = raw["schema_version"]
    product_spec_id = raw["product_spec_id"]
    renderer_version = raw["renderer_version"]
    raw_artifacts = raw["artifacts"]
    if not isinstance(schema_version, int) or schema_version != 1:
        raise ValueError("unsupported manifest schema")
    if not isinstance(product_spec_id, str) or not product_spec_id:
        raise TypeError("manifest product spec identity must be a string")
    if not isinstance(renderer_version, str) or not renderer_version:
        raise TypeError("manifest renderer version must be a string")
    if not isinstance(raw_artifacts, list):
        raise TypeError("manifest artifacts must be a list")
    artifacts: list[_ManifestArtifact] = []
    for raw_entry in cast(list[object], raw_artifacts):
        if not isinstance(raw_entry, dict):
            raise TypeError("manifest artifact must be an object")
        entry = cast(dict[object, object], raw_entry)
        if set(entry) != {
            "path",
            "media_type",
            "byte_count",
            "sha256",
        }:
            raise ValueError("invalid manifest artifact")
        path = entry["path"]
        media_type = entry["media_type"]
        byte_count = entry["byte_count"]
        sha256 = entry["sha256"]
        if not isinstance(path, str):
            raise TypeError("manifest path must be a string")
        if not isinstance(media_type, str):
            raise TypeError("manifest media type must be a string")
        if not isinstance(byte_count, int) or byte_count < 0:
            raise TypeError("manifest byte count must be a non-negative integer")
        if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise ValueError("invalid manifest digest")
        artifacts.append(
            {
                "path": path,
                "media_type": media_type,
                "byte_count": byte_count,
                "sha256": sha256,
            }
        )
    return {
        "schema_version": schema_version,
        "product_spec_id": product_spec_id,
        "renderer_version": renderer_version,
        "artifacts": artifacts,
    }


def _load_spec(data: bytes | None, findings: set[str]) -> ProductSpec | None:
    if data is None:
        findings.add("PRODUCT_SPEC_MISSING")
        return None
    try:
        return ProductSpec.model_validate_json(data, strict=True)
    except (ValidationError, ValueError):
        findings.add("PRODUCT_SPEC_INVALID")
        return None


def _slug(value: str) -> str:
    return _SLUG_RUN.sub("-", value.casefold()).strip("-")


def _duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if values.count(value) > 1}))


def _normalise_theme(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    return _CSS_HSL.sub("hsl(HUE", _CSS_THEME_NAME.sub('--theme-name: "THEME"', text))


def _is_canonical_relative(value: str) -> bool:
    decoded = unquote(unescape(value))
    secured = _security_normalise(decoded)
    path = PurePosixPath(value)
    return bool(
        value
        and decoded == value
        and secured == value
        and value not in {".", ".."}
        and "\\" not in value
        and not value.startswith("./")
        and "//" not in value
        and ":" not in path.parts[0]
        and not _has_unsafe_scheme(value)
        and not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in path.parts)
        and path.as_posix() == value
    )


def _is_network_url(value: str) -> bool:
    lowered = _normalise_url(value)
    return lowered.startswith(("http://", "https://", "//", "data:"))


def _has_unsafe_scheme(value: str) -> bool:
    lowered = _normalise_url(value)
    parsed = urlsplit(lowered)
    return bool(parsed.scheme or parsed.netloc or lowered.startswith("//"))


def _normalise_url(value: str) -> str:
    decoded = unquote(unescape(value)).casefold()
    return re.sub(r"[\x00-\x20]+", "", decoded)


def _valid_heading_hierarchy(levels: list[int]) -> bool:
    return (
        bool(levels)
        and levels[0] == 1
        and all(current <= previous + 1 for previous, current in pairwise(levels))
    )


def _normalise_copy(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _security_normalise(value).casefold()).strip()


def _contains_unapproved_html_copy(text_chunks: Iterable[str], spec: ProductSpec) -> bool:
    title = f"{spec.identity_niche} {spec.base_category}"
    allowed = {
        _normalise_copy(value)
        for value in (
            spec.identity_niche,
            title,
            spec.target_buyer,
            spec.promised_outcome,
            "Bundle ready",
            "Build progress",
            "Designed for",
            "Other hubs",
            "Product hubs",
            "Verified product facts",
            "Back to dashboard",
            "Useful views",
            *spec.hubs,
            *spec.features,
            *(fact.claim for fact in spec.product_facts),
            *(f"{name} | {title}" for name in spec.hubs),
            *(f"A focused {name.lower()} workspace for {spec.target_buyer}." for name in spec.hubs),
        )
    }
    return any(
        bool(normalised := _normalise_copy(chunk)) and normalised not in allowed
        for chunk in text_chunks
    )


def _validate_readme(text: str, spec: ProductSpec, renderer_version: str) -> tuple[bool, bool]:
    title = f"{spec.identity_niche} {spec.base_category}"
    hub_names = [name for _, name in sorted((_slug(name), name) for name in spec.hubs)]
    variant_names = [
        name for _, name in sorted((_slug(name), name) for name in spec.colour_variants)
    ]
    expected_text = (
        f"# {title}\n\n"
        f"Built for **{spec.target_buyer}** to {spec.promised_outcome}.\n\n"
        "## Open the product\n\n"
        "Open `home.html` in a browser. The bundle is self-contained and makes no "
        "network requests.\n\n"
        "## Included hubs\n\n"
        + "".join(f"- {name}\n" for name in hub_names)
        + "\n\n## Colour themes\n\n"
        + "".join(f"- {name}\n" for name in variant_names)
        + f"\n\nRenderer: `{renderer_version}`\n"
    )
    expected = tuple(
        normalised for line in expected_text.splitlines() if (normalised := _normalise_copy(line))
    )
    actual = tuple(
        normalised for line in text.splitlines() if (normalised := _normalise_copy(line))
    )
    admitted = set(expected) | {_normalise_copy(fact.claim) for fact in spec.product_facts}
    return text == expected_text and actual == expected, any(
        line not in admitted for line in actual
    )


def _expected_artifact_media_types(spec: ProductSpec) -> dict[str, str]:
    expected = {
        "product.json": "application/json",
        "README.md": "text/markdown",
        "home.html": "text/html",
    }
    expected.update({f"hubs/{_slug(name)}.html": "text/html" for name in spec.hubs})
    expected.update({f"assets/{_slug(name)}.css": "text/css" for name in spec.colour_variants})
    return expected


def _check_exact_artifact_contract(
    spec: ProductSpec,
    manifest: _Manifest,
    manifest_paths: set[str],
    findings: set[str],
) -> None:
    expected_media_types = _expected_artifact_media_types(spec)
    expected_paths = set(expected_media_types)
    for path in sorted(expected_paths - manifest_paths):
        findings.add(f"EXPECTED_MANIFEST_ARTIFACT_MISSING:{path}")
    for path in sorted(manifest_paths - expected_paths):
        findings.add(f"UNEXPECTED_MANIFEST_ARTIFACT:{path}")
    for entry in manifest["artifacts"]:
        path = entry["path"]
        expected_media_type = expected_media_types.get(path)
        if expected_media_type is not None and entry["media_type"] != expected_media_type:
            findings.add(f"ARTIFACT_MEDIA_TYPE_INVALID:{path}")


def _check_descriptor_inventory(
    root_descriptor: int,
    manifest_paths: set[str],
    findings: set[str],
) -> None:
    try:
        files, directories, unsafe = _scan_descriptor_tree(root_descriptor)
    except OSError:
        findings.add("BUNDLE_INVENTORY_INVALID")
        return
    declared_files = {*manifest_paths, "manifest.json"}
    declared_directories = {
        parent.as_posix()
        for path in declared_files
        for parent in PurePosixPath(path).parents
        if parent.as_posix() != "."
    }
    for path in sorted(files - declared_files):
        findings.add(f"UNEXPECTED_BUNDLE_ENTRY:{path}")
    for path in sorted(directories - declared_directories):
        findings.add(f"UNEXPECTED_BUNDLE_ENTRY:{path}")
    for path in sorted(unsafe):
        findings.add(f"UNSAFE_BUNDLE_ENTRY:{path}")


def _scan_descriptor_tree(root_descriptor: int) -> tuple[set[str], set[str], set[str]]:
    files: set[str] = set()
    directories: set[str] = set()
    unsafe: set[str] = set()

    def visit(directory_descriptor: int, prefix: PurePosixPath) -> None:
        for name in sorted(os.listdir(directory_descriptor)):
            relative = prefix / name
            path = relative.as_posix()
            metadata = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
            if stat.S_ISREG(metadata.st_mode):
                files.add(path)
                continue
            if not stat.S_ISDIR(metadata.st_mode):
                unsafe.add(path)
                continue
            directories.add(path)
            try:
                child_descriptor = os.open(
                    name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=directory_descriptor,
                )
            except OSError:
                unsafe.add(path)
                continue
            try:
                visit(child_descriptor, relative)
            finally:
                os.close(child_descriptor)

    visit(root_descriptor, PurePosixPath())
    return files, directories, unsafe


def _artifact_identity(path: str, media_type: str, content_sha256: str) -> str:
    identity = f"{path}\0{media_type}\0{content_sha256}".encode()
    return f"artifact-{hashlib.sha256(identity).hexdigest()}"


def _contains_css_network_construct(text: str) -> bool:
    without_comments = _CSS_COMMENT.sub("", _security_normalise(text))

    def decode_escape(match: re.Match[str]) -> str:
        hex_value = match.group("hex")
        return chr(int(hex_value, 16)) if hex_value is not None else (match.group("char") or "")

    decoded = _security_normalise(_CSS_ESCAPE.sub(decode_escape, without_comments)).casefold()
    if _CSS_AT_RULE.search(decoded):
        return True
    return any(
        match.group("name").casefold() not in _ALLOWED_CSS_FUNCTIONS
        for match in _CSS_FUNCTION.finditer(decoded)
    )


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", _security_normalise(value)).strip()


def _normalise_control_name(value: str) -> str:
    return _normalise_copy(value)


def _security_normalise(value: str) -> str:
    normalised = unicodedata.normalize("NFKC", value)
    return "".join(
        " "
        if character.isspace()
        else ""
        if unicodedata.category(character)[0] == "C"
        else character
        for character in normalised
    )


def _open_absolute_directory(path: Path) -> int:
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_regular_file_at(root_descriptor: int, path: PurePosixPath) -> bytes:
    """Read one root-relative regular file without following any symlink component."""

    descriptor = os.dup(root_descriptor)
    try:
        for part in path.parts[:-1]:
            child = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
        file_descriptor = os.open(path.parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor)
        try:
            if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
                raise OSError("artifact is not a regular file")
            chunks: list[bytes] = []
            while chunk := os.read(file_descriptor, 1024 * 1024):
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(file_descriptor)
    finally:
        os.close(descriptor)
