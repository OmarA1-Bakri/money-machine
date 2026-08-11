from __future__ import annotations

import hashlib
import importlib
import os
import signal
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from money_machine.integrations.storage.interface import (
        ArtifactCollisionError,
        UnsafeArtifactPathError,
    )
    from money_machine.integrations.storage.local import LocalArtifactStore
else:
    storage_interface = importlib.import_module("money_machine.integrations.storage.interface")
    storage_local = importlib.import_module("money_machine.integrations.storage.local")
    ArtifactCollisionError = cast(
        type[RuntimeError], getattr(storage_interface, "ArtifactCollisionError", RuntimeError)
    )
    UnsafeArtifactPathError = cast(
        type[RuntimeError], getattr(storage_interface, "UnsafeArtifactPathError", RuntimeError)
    )
    LocalArtifactStore = cast(type[object], getattr(storage_local, "LocalArtifactStore", object))


def _raise_timeout(_signum: int, _frame: object) -> None:
    raise TimeoutError("filesystem operation blocked")


@pytest.mark.parametrize(
    ("module_name", "symbol_name"),
    [
        ("money_machine.integrations.storage.interface", "ArtifactStore"),
        ("money_machine.integrations.storage.local", "LocalArtifactStore"),
        ("money_machine.integrations.notion.fixture_adapter", "LocalNotionAdapter"),
        ("money_machine.application.services.product_service", "ProductQAService"),
        ("money_machine.application.services.product_service", "ProductService"),
    ],
)
def test_clean_replay_task6_contract_is_implemented(module_name: str, symbol_name: str) -> None:
    module = importlib.import_module(module_name)
    assert hasattr(module, symbol_name), f"{module_name}.{symbol_name} is not implemented"


def test_r5_behavior_contract_artifact_store_writes_only_below_root(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    reference = store.put_bytes("nested/item.txt", b"content", "text/plain")

    assert reference.relative_path.as_posix() == "nested/item.txt"
    assert (tmp_path / "artifacts/nested/item.txt").read_bytes() == b"content"
    assert not (tmp_path / "item.txt").exists()


def test_put_bytes_writes_and_returns_a_deterministic_reference(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    data = b"hello\n"

    first = store.put_bytes("bundle/README.md", data, "text/markdown")
    second = store.put_bytes("bundle/README.md", data, "text/markdown")

    assert first == second
    assert first.relative_path.as_posix() == "bundle/README.md"
    assert first.byte_count == len(data)
    assert first.content_sha256 == hashlib.sha256(data).hexdigest()
    assert first.artifact_id == (
        "artifact-a5d6b794f0824d85bb953c303fad1c21185b8fae2b0955b90175a3cd05e00b3d"
    )
    assert (tmp_path / "artifacts/bundle/README.md").read_bytes() == data
    assert not list((tmp_path / "artifacts").rglob("*.tmp"))


@pytest.mark.parametrize(
    "relative_path",
    ["", ".", "../escape", "bundle/../escape", "/absolute", "C:/escape", "a\\b"],
)
def test_put_bytes_rejects_noncanonical_or_unsafe_paths(tmp_path: Path, relative_path: str) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")

    with pytest.raises(UnsafeArtifactPathError):
        store.put_bytes(relative_path, b"unsafe", "text/plain")

    assert not (tmp_path / "escape").exists()


def test_put_bytes_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)
    store = LocalArtifactStore(root)

    with pytest.raises(UnsafeArtifactPathError):
        store.put_bytes("linked/escape.txt", b"unsafe", "text/plain")

    assert not (outside / "escape.txt").exists()


def test_put_bytes_rejects_symlink_before_creating_nested_directories(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)
    store = LocalArtifactStore(root)

    with pytest.raises(UnsafeArtifactPathError):
        store.put_bytes("linked/new/escape.txt", b"unsafe", "text/plain")

    assert not (outside / "new").exists()


def test_artifact_root_rejects_symlinked_ancestor_without_external_write(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)

    with pytest.raises(UnsafeArtifactPathError):
        LocalArtifactStore(alias / "artifacts")

    assert not (outside / "artifacts").exists()


def test_put_bytes_rejects_root_replaced_by_symlink_after_initialization(
    tmp_path: Path,
) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    outside.mkdir()
    store = LocalArtifactStore(root)
    root.rename(tmp_path / "original-artifacts")
    root.symlink_to(outside, target_is_directory=True)

    with pytest.raises(UnsafeArtifactPathError):
        store.put_bytes("escape.txt", b"unsafe", "text/plain")

    assert not (outside / "escape.txt").exists()


def test_constructor_rejects_ancestor_swapped_before_final_root_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import money_machine.integrations.storage.local as storage_module

    trusted = tmp_path / "trusted"
    trusted.mkdir()
    relocated = tmp_path / "relocated"
    attacker = tmp_path / "attacker"
    (attacker / "artifacts").mkdir(parents=True)
    swapped = False

    def swap() -> None:
        nonlocal swapped
        if swapped:
            return
        trusted.rename(relocated)
        trusted.symlink_to(attacker, target_is_directory=True)
        swapped = True

    legacy_check = getattr(storage_module, "_reject_symlinked_ancestors", None)
    legacy_calls = 0

    def legacy_swap(path: Path) -> None:
        nonlocal legacy_calls
        assert legacy_check is not None
        legacy_check(path)
        legacy_calls += 1
        if legacy_calls == 2:
            swap()

    original_open = storage_module.os.open

    def descriptor_swap(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if os.fspath(path) == "trusted" and dir_fd is not None:
            swap()
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(storage_module, "_reject_symlinked_ancestors", legacy_swap, raising=False)
    monkeypatch.setattr(storage_module.os, "open", descriptor_swap)

    with pytest.raises(UnsafeArtifactPathError):
        LocalArtifactStore(trusted / "artifacts")

    assert swapped is True
    assert not any((attacker / "artifacts").iterdir())


def test_put_bytes_rejects_intermediate_directory_swapped_after_initialization(
    tmp_path: Path,
) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    outside.mkdir()
    store = LocalArtifactStore(root)
    (root / "bundle").mkdir()
    (root / "bundle").rename(root / "original-bundle")
    (root / "bundle").symlink_to(outside, target_is_directory=True)

    with pytest.raises(UnsafeArtifactPathError):
        store.put_bytes("bundle/escape.txt", b"unsafe", "text/plain")

    assert not (outside / "escape.txt").exists()


def test_put_bytes_rejects_ancestor_replaced_by_symlink_after_initialization(
    tmp_path: Path,
) -> None:
    ancestor = tmp_path / "trusted"
    root = ancestor / "artifacts"
    store = LocalArtifactStore(root)
    relocated = tmp_path / "relocated"
    ancestor.rename(relocated)
    ancestor.symlink_to(relocated, target_is_directory=True)

    with pytest.raises(UnsafeArtifactPathError):
        store.put_bytes("escape.txt", b"unsafe", "text/plain")

    assert not (relocated / "artifacts/escape.txt").exists()


def test_put_bytes_rejects_immutable_collision(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    store.put_bytes("bundle/data.json", b"one", "application/json")

    with pytest.raises(ArtifactCollisionError):
        store.put_bytes("bundle/data.json", b"two", "application/json")

    assert (tmp_path / "artifacts/bundle/data.json").read_bytes() == b"one"


def test_get_bytes_reads_only_exact_verified_regular_file(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    reference = store.put_bytes("bundle/data.json", b"one", "application/json")

    assert (
        store.get_bytes(
            reference.relative_path,
            expected_sha256=reference.content_sha256,
            expected_byte_count=reference.byte_count,
        )
        == b"one"
    )

    with pytest.raises(ValueError, match="artifact byte count mismatch"):
        store.get_bytes(reference.relative_path, expected_byte_count=4)
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        store.get_bytes(reference.relative_path, expected_sha256="0" * 64)


def test_get_bytes_rejects_symlinked_source(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"private")
    store = LocalArtifactStore(root)
    (root / "linked.txt").symlink_to(outside)

    with pytest.raises(UnsafeArtifactPathError):
        store.get_bytes("linked.txt")


def test_get_bytes_reports_missing_parent_as_missing_file(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")

    with pytest.raises(FileNotFoundError):
        store.get_bytes("missing/item.txt")


@pytest.mark.parametrize("operation", ("get", "put"))
def test_artifact_store_rejects_fifo_without_blocking(tmp_path: Path, operation: str) -> None:
    root = tmp_path / "artifacts"
    store = LocalArtifactStore(root)
    os.mkfifo(root / "blocked")
    previous_handler = signal.signal(signal.SIGALRM, _raise_timeout)
    started = time.monotonic()
    signal.setitimer(signal.ITIMER_REAL, 0.25)
    try:
        with pytest.raises(UnsafeArtifactPathError):
            if operation == "get":
                store.get_bytes("blocked")
            else:
                store.put_bytes("blocked", b"data", "application/octet-stream")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
    assert time.monotonic() - started < 0.1


def test_list_files_is_sorted_confined_and_rejects_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    store = LocalArtifactStore(root)
    store.put_bytes("bundle/z.txt", b"z", "text/plain")
    store.put_bytes("bundle/nested/a.txt", b"a", "text/plain")

    assert tuple(path.as_posix() for path in store.list_files("bundle")) == (
        "nested/a.txt",
        "z.txt",
    )
    assert tuple(path.as_posix() for path in store.list_files()) == (
        "bundle/nested/a.txt",
        "bundle/z.txt",
    )
    assert store.list_files("missing") == ()

    (root / "bundle/linked.txt").symlink_to(root / "bundle/z.txt")
    with pytest.raises(UnsafeArtifactPathError):
        store.list_files("bundle")
