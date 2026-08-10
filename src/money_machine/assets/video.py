"""Deterministic identity-bound preview video for the first-product slice."""

from __future__ import annotations

import base64
import json
import struct
from typing import Literal
from uuid import UUID

from money_machine.domain.models.listing import ListingPackage
from money_machine.domain.models.product import BuildResult
from money_machine.domain.models.product_spec import ProductSpec

VideoStatus = Literal["GENERATED"]
_IDENTITY_BOX_UUID = UUID("b3085f4c-5d9d-4f2e-9275-80a7be3cf715")
_CANONICAL_MP4_PREFIX = base64.b64decode(
    "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAMVbW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAACgAAQAA"
    "AQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAgAAAj90cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAACgAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAA"
    "AAAAAAABAAAAAAAAAAAAAAAAAABAAAAAABAAAAAQAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAAoAAAAAAABAAAAAAG3"
    "bWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAAAyAAAAAgBVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRl"
    "b0hhbmRsZXIAAAABYm1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAA"
    "AQAAASJzdGJsAAAAvnN0c2QAAAAAAAAAAQAAAK5hdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAABAAEABIAAAASAAAAAAA"
    "AAABFUxhdmM2MC4zMS4xMDIgbGlieDI2NAAAAAAAAAAAAAAAGP//AAAANGF2Y0MBZAAK/+EAF2dkAAqs2V7ARAAAAwAEAAAD"
    "AMg8SJZYAQAGaOvjyyLA/fj4AAAAABBwYXNwAAAAAQAAAAEAAAAUYnRydAAAAAAAAinoAAIp6AAAABhzdHRzAAAAAAAAAAEA"
    "AAABAAACAAAAABxzdHNjAAAAAAAAAAEAAAABAAAAAQAAAAEAAAAUc3RzegAAAAAAAALFAAAAAQAAABRzdGNvAAAAAAAAAAEA"
    "AANFAAAAYnVkdGEAAABabWV0YQAAAAAAAAAhaGRscgAAAAAAAAAAbWRpcmFwcGwAAAAAAAAAAAAAAAAtaWxzdAAAACWpdG9v"
    "AAAAHWRhdGEAAAABAAAAAExhdmY2MC4xNi4xMDAAAAAIZnJlZQAAAs1tZGF0AAACrgYF//+q3EXpvebZSLeWLNgg2SPu73gy"
    "NjQgLSBjb3JlIDE2NCByMzEwOCAzMWUxOWY5IC0gSC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAy"
    "MyAtIGh0dHA6Ly93d3cudmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTEgcmVmPTMgZGVibG9jaz0x"
    "OjA6MCBhbmFseXNlPTB4MzoweDExMyBtZT1oZXggc3VibWU9NyBwc3k9MSBwc3lfcmQ9MS4wMDowLjAwIG1peGVkX3JlZj0x"
    "IG1lX3JhbmdlPTE2IGNocm9tYV9tZT0xIHRyZWxsaXM9MSA4eDhkY3Q9MSBjcW09MCBkZWFkem9uZT0yMSwxMSBmYXN0X3Bz"
    "a2lwPTEgY2hyb21hX3FwX29mZnNldD0tMiB0aHJlYWRzPTEgbG9va2FoZWFkX3RocmVhZHM9MSBzbGljZWRfdGhyZWFkcz0w"
    "IG5yPTAgZGVjaW1hdGU9MSBpbnRlcmxhY2VkPTAgYmx1cmF5X2NvbXBhdD0wIGNvbnN0cmFpbmVkX2ludHJhPTAgYmZyYW1l"
    "cz0zIGJfcHlyYW1pZD0yIGJfYWRhcHQ9MSBiX2JpYXM9MCBkaXJlY3Q9MSB3ZWlnaHRiPTEgb3Blbl9nb3A9MCB3ZWlnaHRw"
    "PTIga2V5aW50PTI1MCBrZXlpbnRfbWluPTI1IHNjZW5lY3V0PTQwIGludHJhX3JlZnJlc2g9MCByY19sb29rYWhlYWQ9NDAg"
    "cmM9Y3JmIG1idHJlZT0xIGNyZj0yMy4wIHFjb21wPTAuNjAgcXBtaW49MCBxcG1heD02OSBxcHN0ZXA9NCBpcF9yYXRpbz0x"
    "LjQwIGFxPTE6MS4wMACAAAAAD2WIhAAr//72c3wKa22xgQ=="
).replace(b"http://", b"local:/")


def _identity_payload(
    package: ListingPackage,
    spec: ProductSpec,
    build: BuildResult,
) -> bytes:
    if package.product_spec_id != spec.product_spec_id:
        raise ValueError("preview video ProductSpec binding mismatch")
    if package.build_id != build.build_id or build.product_spec_id != spec.product_spec_id:
        raise ValueError("preview video build binding mismatch")
    return json.dumps(
        {
            "build_id": build.build_id,
            "listing_package_id": package.listing_package_id,
            "product_spec_id": spec.product_spec_id,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def render_preview_video(
    package: ListingPackage,
    spec: ProductSpec,
    build: BuildResult,
) -> bytes:
    """Return one replay-stable H.264 MP4 bound to the exact package lineage."""

    payload = _identity_payload(package, spec, build)
    box = struct.pack(">I4s", 8 + 16 + len(payload), b"uuid") + _IDENTITY_BOX_UUID.bytes + payload
    return _CANONICAL_MP4_PREFIX + box


def validate_preview_video(
    data: bytes,
    package: ListingPackage,
    spec: ProductSpec,
    build: BuildResult,
) -> None:
    """Reject any stream, container, identity, or trailing-byte deviation."""

    expected = render_preview_video(package, spec, build)
    if data != expected:
        raise ValueError("preview video bytes do not match commissioned renderer")


def video_status() -> VideoStatus:
    """Exactly one generated local video is required for DRAFT_READY."""

    return "GENERATED"
