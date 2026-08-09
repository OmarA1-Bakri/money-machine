"""Deterministic local-only Notion-compatible product builder."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from money_machine.domain.models.product import BuildResult
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.value_objects import canonical_json
from money_machine.integrations.notion.interface import deterministic_build_id
from money_machine.integrations.storage.local import LocalArtifactStore

RENDERER_VERSION = "local-notion-v1"
_TEMPLATE_ROOT = Path(__file__).resolve().parents[4] / "templates" / "product"
_SLUG_RUN = re.compile(r"[^a-z0-9]+")


class LocalNotionAdapter:
    """The only write-enabled product adapter, restricted to local files."""

    def __init__(self, template_root: Path = _TEMPLATE_ROOT) -> None:
        self._template_root = template_root
        self._environment = _load_jinja_environment(template_root)

    def build(self, spec: ProductSpec, destination: Path) -> BuildResult:
        """Render a complete deterministic product bundle and manifest."""

        hub_pairs = tuple(sorted((_slug(name), name) for name in spec.hubs))
        variant_pairs = tuple(sorted((_slug(name), name) for name in spec.colour_variants))
        _require_unique_slugs(hub_pairs, "hub")
        _require_unique_slugs(variant_pairs, "variant")

        store = LocalArtifactStore(destination)
        title = f"{spec.identity_niche} {spec.base_category}"
        default_theme = variant_pairs[0][0]
        semantic_files: dict[str, tuple[bytes, str]] = {
            "product.json": (canonical_json(spec) + b"\n", "application/json"),
            "README.md": (
                self._render(
                    "readme.md.j2",
                    {
                        "title": title,
                        "target_buyer": spec.target_buyer,
                        "promised_outcome": spec.promised_outcome,
                        "hubs": hub_pairs,
                        "variants": variant_pairs,
                        "renderer_version": RENDERER_VERSION,
                    },
                ),
                "text/markdown",
            ),
            "home.html": (
                self._render(
                    "home.html.j2",
                    {
                        "title": title,
                        "identity_niche": spec.identity_niche,
                        "target_buyer": spec.target_buyer,
                        "promised_outcome": spec.promised_outcome,
                        "default_theme": default_theme,
                        "hubs": hub_pairs,
                        "product_facts": tuple(sorted(spec.product_facts)),
                    },
                ),
                "text/html",
            ),
        }
        for slug, name in hub_pairs:
            semantic_files[f"hubs/{slug}.html"] = (
                self._render(
                    "hub.html.j2",
                    {
                        "hub_name": name,
                        "title": title,
                        "default_theme": default_theme,
                        "hub_description": (
                            f"A focused {name.lower()} workspace for {spec.target_buyer}."
                        ),
                        "hubs": hub_pairs,
                        "features": tuple(sorted(spec.features)),
                    },
                ),
                "text/html",
            )
        for slug, name in variant_pairs:
            hue = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16) % 360
            semantic_files[f"assets/{slug}.css"] = (
                self._render(
                    "theme.css.j2",
                    {
                        "variant_name": name,
                        "hue": str(hue),
                        "accent_hue": str((hue + 37) % 360),
                    },
                ),
                "text/css",
            )

        references = tuple(
            store.put_bytes(path, data, media_type)
            for path, (data, media_type) in sorted(semantic_files.items())
        )
        manifest = {
            "schema_version": 1,
            "product_spec_id": spec.product_spec_id,
            "renderer_version": RENDERER_VERSION,
            "artifacts": [
                {
                    "path": reference.relative_path.as_posix(),
                    "media_type": reference.media_type,
                    "byte_count": reference.byte_count,
                    "sha256": reference.content_sha256,
                }
                for reference in references
            ],
        }
        manifest_bytes = canonical_json(manifest) + b"\n"
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        store.put_bytes("manifest.json", manifest_bytes, "application/json")
        return BuildResult(
            build_id=deterministic_build_id(
                spec.product_spec_id, manifest_sha256, RENDERER_VERSION
            ),
            product_spec_id=spec.product_spec_id,
            root_artifact_path=str(store.root),
            artifacts=references,
            manifest_sha256=manifest_sha256,
            renderer_version=RENDERER_VERSION,
        )

    def _render(self, template_name: str, values: Mapping[str, object]) -> bytes:
        rendered = self._environment.get_template(template_name).render(**values)
        return rendered.replace("\r\n", "\n").encode("utf-8")


def _slug(value: str) -> str:
    slug = _SLUG_RUN.sub("-", value.casefold()).strip("-")
    if not slug:
        raise ValueError("names must produce a non-empty slug")
    return slug


def _require_unique_slugs(pairs: tuple[tuple[str, str], ...], kind: str) -> None:
    slugs = tuple(slug for slug, _ in pairs)
    if len(slugs) != len(set(slugs)):
        raise ValueError(f"{kind} slugs must be unique")


def _load_jinja_environment(template_root: Path) -> Environment:
    """Create the single strict, autoescaping renderer path."""

    return Environment(
        loader=FileSystemLoader(str(template_root)),
        undefined=StrictUndefined,
        autoescape=select_autoescape(enabled_extensions=("html", "htm", "xml", "j2"), default=True),
        keep_trailing_newline=True,
        newline_sequence="\n",
    )
