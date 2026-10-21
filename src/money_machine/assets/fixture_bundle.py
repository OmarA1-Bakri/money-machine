"""Render and retain bytes from the checked fixture product, never remote pages."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, replace
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid5

from playwright.sync_api import sync_playwright
from pydantic import TypeAdapter

from money_machine.agents.contracts.merchandising import IMAGE_ROLES
from money_machine.assets.asset_lineage import BoundAsset, bind_asset
from money_machine.assets.delivery_pdfs import render_gift_pdf, render_readme_pdf
from money_machine.assets.design_tokens import listing_token_payload, load_tokens
from money_machine.assets.listing_images import render_listing_images
from money_machine.assets.screenshots import LAUNCH_ARGS
from money_machine.assets.video import render_walkthrough


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    data = (json.dumps(value, default=str, sort_keys=True, indent=2) + "\n").encode()
    temporary = path.with_suffix(path.suffix + ".next")
    temporary.write_bytes(data)
    temporary.replace(path)


def verify_bundle(directory: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in (directory / "lineage.jsonl").read_text().splitlines()]
    if not rows:
        raise ValueError("artifact manifest empty")
    for row in rows:
        path = directory / row["relative_path"]
        if not path.resolve().is_relative_to(directory.resolve()) or path.is_symlink():
            raise ValueError("artifact path escaped bundle")
        value = path.read_bytes()
        if len(value) != row["byte_size"] or sha(value) != row["sha256"]:
            raise ValueError(f"artifact bytes changed: {row['relative_path']}")
    return rows


def render_bundle(spec, probe, built, request, copy, directory: Path):
    """Paint actual fixture structure; existing claim-gated renderers derive buyer files."""
    manifest = directory / "lineage.jsonl"
    if manifest.exists():
        rows = verify_bundle(directory)
        saved_assets = TypeAdapter(tuple[BoundAsset, ...]).validate_json(
            (directory / "bound-assets.json").read_bytes()
        )
        for asset in saved_assets:
            matched = [
                row for row in rows if str(directory / row["relative_path"]) == asset.storage_uri
            ]
            if len(matched) != 1 or matched[0]["sha256"] != asset.output_sha256:
                raise ValueError("saved asset binding disagrees with verified bytes")
        return rows, saved_assets
    rows: list[dict[str, Any]] = []
    assets: list[BoundAsset] = []

    def record(name: str, kind: str, value: bytes, parents=(), bound=None):
        path = directory / name
        if path.exists() and path.read_bytes() != value:
            raise ValueError(f"refuse replacing existing artifact: {name}")
        path.write_bytes(value)
        artifact_id = uuid5(spec.spec_id, name)
        row = dict(
            run_id=directory.parent.name,
            artifact_id=str(artifact_id),
            kind=kind,
            relative_path=name,
            sha256=sha(value),
            byte_size=len(value),
            product_id=str(spec.product_id),
            spec_version=spec.version,
            build_version=built.build_version,
            parent_artifact_ids=list(parents),
        )
        rows.append(row)
        if bound is not None:
            assets.append(replace(bound, output_sha256=row["sha256"], storage_uri=str(path)))
        return str(artifact_id)

    structure = {
        key: {identity: asdict(item) for identity, item in getattr(probe, key).items()}
        for key in ("pages", "databases", "blocks", "views", "linked_views")
    }
    structure_bytes = json.dumps(structure, default=str, sort_keys=True).encode()
    parent = record("product-structure.json", "product_structure", structure_bytes)
    # This HTML is generated only from actual fixture page/database/block objects.
    page = probe.pages[built.page_id]
    blocks = "".join(
        f"<p>{escape(getattr(block, 'content', ''))}</p>"
        for _, block in sorted(probe.blocks.items())
    )
    hubs = "".join(f"<li>{escape(hub.name)}</li>" for hub in spec.hubs)
    databases = "".join(f"<li>{escape(kind)}</li>" for kind, _ in built.database_ids)
    document = (
        "<!doctype html><html><meta charset='utf-8'><style>"
        "body{font-family:DejaVu Sans,sans-serif;background:#f6f3ee;"
        "color:#1c1917;margin:18px}h1{font-size:22px}p,li{font-size:12px}"
        "section{display:flex;gap:30px}</style>"
        f"<h1>{escape(page.title)}</h1><section><ul>{hubs}</ul>"
        f"<ul>{databases}</ul></section>{blocks}</html>"
    )
    html_id = record("product.html", "product_html", document.encode(), (parent,))
    screenshots = {}
    source_ids = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=list(LAUNCH_ARGS),
            executable_path=os.environ.get("MONEY_MACHINE_BROWSER_EXECUTABLE"),
        )
        context = browser.new_context(
            viewport={"width": 480, "height": 270}, java_script_enabled=False
        )
        context.route(
            "**/*",
            lambda route: (
                route.abort()
                if route.request.url.startswith(("http:", "https:"))
                else route.continue_()
            ),
        )
        tab = context.new_page()
        for index, variant in enumerate(built.variants):
            tab.set_content(document.replace("<h1>", f"<h1>{escape(variant.name)} · ", 1))
            value = tab.screenshot(type="png")
            name = f"screenshot-{index}.png"
            digest = sha(value)
            bound = BoundAsset(
                spec.product_id,
                spec.version,
                built.build_version,
                (),
                "",
                "actual-fixture-product-1",
                digest,
                480,
                270,
                None,
                "passed",
                str(directory / name),
                "screenshot",
            )
            source_ids.append(record(name, "screenshot", value, (html_id,), bound))
            screenshots[variant.name] = directory / name
        context.close()
        browser.close()
    primary = directory / "screenshot-0.png"
    screenshots.update({role: primary for role in IMAGE_ROLES})
    screenshots.update(
        {
            role: primary
            for role in (
                "dashboard",
                "notification_panel",
                "strongest_hubs",
                "colour_options",
                "duplication_access",
                "hub_1",
                "hub_2",
                "hub_3",
                "hub_4",
                "hub_5",
                "notification",
            )
        }
    )
    allowed = frozenset(sha(path.read_bytes()) for path in screenshots.values())
    tokens = load_tokens(listing_token_payload())
    for index, image in enumerate(
        render_listing_images(
            copy, request, screenshots, allowed, tokens, build_version=built.build_version
        )
    ):
        record(
            f"listing-{index + 1:02}.png",
            "listing_image",
            image.png,
            tuple(source_ids),
            bind_asset(image.lineage),
        )
    video = render_walkthrough(
        copy, request, screenshots, allowed, tokens, build_version=built.build_version
    )
    source_video = directory / "walkthrough.mkv"
    video_id = record("walkthrough.mkv", "walkthrough_source", video.video, tuple(source_ids))
    target = directory / "walkthrough.mp4"
    with TemporaryDirectory(prefix="money-machine-fixture-video-") as temporary:
        encoded = Path(temporary) / "walkthrough.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source_video),
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-threads",
                "1",
                "-map_metadata",
                "-1",
                "-fflags",
                "+bitexact",
                "-flags:v",
                "+bitexact",
                str(encoded),
            ],
            check=True,
            capture_output=True,
        )
        video_bytes = encoded.read_bytes()
    record(
        "walkthrough.mp4",
        "walkthrough",
        video_bytes,
        (video_id,),
        bind_asset(video.lineage),
    )
    metadata = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(target)],
        check=True,
        capture_output=True,
    ).stdout
    observed = json.loads(metadata)
    if (
        "mp4" not in observed["format"]["format_name"]
        or observed["streams"][0]["codec_name"] != "h264"
    ):
        raise ValueError("MP4 codec verification failed")
    record("video-probe.json", "video_probe", metadata, (video_id,))
    for role, renderer in (("readme", render_readme_pdf), ("free_gift", render_gift_pdf)):
        pdf = renderer(copy, request, tokens, build_version=built.build_version)
        record(f"{role}.pdf", "delivery_pdf", pdf.pdf, (), bind_asset(pdf.lineage))
    record(
        "README.txt",
        "readme_text",
        (
            "Fixture-only Notion product. Open product.html for the actual build export.\n"
            + "\n".join(f"{row.name}: {row.secret_link}" for row in built.variants)
        ).encode(),
        (parent,),
    )
    write_json(directory / "bound-assets.json", [asdict(asset) for asset in assets])
    (directory / "lineage.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    )
    verify_bundle(directory)
    return rows, tuple(assets)
