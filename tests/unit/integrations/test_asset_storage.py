"""Fixture asset storage. Each refusal has its own kill."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

import pytest

from money_machine.integrations.storage.interface import refuse_collision
from money_machine.integrations.storage.local import LocalAssetStore
from money_machine.integrations.storage.s3 import SimS3AssetStore

_PRODUCT = UUID("00000000-0000-4000-8000-000000000001")
_PNG = b"png-bytes"
_GIF = b"gif-bytes"
_OLD = b"old-bytes"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    root.mkdir()
    return root


def _local(tmp_path: Path) -> LocalAssetStore:
    return LocalAssetStore(_root(tmp_path))


def _uri_path(store: LocalAssetStore, uri: str) -> Path:
    if uri.startswith("fixture://"):
        return store.root / "published" / uri.removeprefix("fixture://")
    if uri.startswith("temp://"):
        return store.root / "temporary" / uri.removeprefix("temp://")
    raise AssertionError(uri)


def _publish(store: LocalAssetStore, data: bytes, *, spec: int = 2) -> str:
    stored = store.publish(product_id=_PRODUCT, spec_version=spec, sha256=_digest(data), data=data)
    return stored.storage_uri


def test_draft_mode_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="storage live"):
        LocalAssetStore(_root(tmp_path), mode="draft")


def test_live_mode_is_refused() -> None:
    with pytest.raises(ValueError, match="storage live"):
        SimS3AssetStore(mode="live")


def test_an_unknown_mode_is_refused() -> None:
    with pytest.raises(ValueError, match="storage mode"):
        SimS3AssetStore(mode="prod")


def test_a_boolean_spec_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match="storage spec"):
        store.publish(
            product_id=_PRODUCT,
            spec_version=True,  # type: ignore[arg-type]
            sha256=_digest(_PNG),
            data=_PNG,
        )


def test_a_zero_spec_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match="storage spec"):
        store.publish(product_id=_PRODUCT, spec_version=0, sha256=_digest(_PNG), data=_PNG)


def test_a_short_hash_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match="storage hash"):
        store.publish(product_id=_PRODUCT, spec_version=2, sha256="ab", data=_PNG)


def test_a_non_hex_hash_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match="storage hash"):
        store.publish(product_id=_PRODUCT, spec_version=2, sha256="g" * 64, data=_PNG)


def test_a_mismatched_digest_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match="storage digest"):
        store.publish(product_id=_PRODUCT, spec_version=2, sha256=_digest(_GIF), data=_PNG)
    assert not any(path.is_file() for path in store.root.rglob("*"))


def test_tampered_bytes_are_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    uri = _publish(store, _PNG)
    _uri_path(store, uri).write_bytes(_GIF)
    with pytest.raises(ValueError, match="storage bytes"):
        store.read(uri)


def test_a_relative_root_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    box = Path("box")
    box.mkdir()
    with pytest.raises(ValueError, match="storage root"):
        LocalAssetStore(box)


def test_a_symlink_root_is_not_followed(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="storage root"):
        LocalAssetStore(link)


def test_a_symlink_directory_is_not_followed(tmp_path: Path) -> None:
    store = _local(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    published = store.root / "published"
    published.mkdir()
    (published / str(_PRODUCT)).symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="storage symlink"):
        _publish(store, _PNG)
    assert list(outside.iterdir()) == []


def test_a_symlink_file_is_not_followed(tmp_path: Path) -> None:
    store = _local(tmp_path)
    outside = tmp_path / "victim"
    outside.write_bytes(_PNG)
    uri = _publish(store, _PNG)
    path = _uri_path(store, uri)
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="storage symlink"):
        _publish(store, _PNG)
    assert outside.read_bytes() == _PNG


def test_an_existing_file_is_not_truncated(tmp_path: Path) -> None:
    store = _local(tmp_path)
    uri = _publish(store, _PNG)
    _uri_path(store, uri).write_bytes(_GIF)
    with pytest.raises(ValueError):
        _publish(store, _PNG)
    assert _uri_path(store, uri).read_bytes() == _GIF
    assert uri.startswith("fixture://")


def test_the_same_bytes_are_idempotent(tmp_path: Path) -> None:
    store = _local(tmp_path)
    first = _publish(store, _PNG)
    second = _publish(store, _PNG)
    assert first == second
    assert store.read(first) == _PNG


def test_different_bytes_collide() -> None:
    with pytest.raises(ValueError, match="storage collision"):
        refuse_collision(_OLD, _PNG)


def test_a_spec_bump_keeps_both_objects(tmp_path: Path) -> None:
    store = _local(tmp_path)
    first = _publish(store, _PNG, spec=1)
    second = _publish(store, _PNG, spec=2)
    assert first != second
    assert "/1/" in first
    assert "/2/" in second
    assert store.read(first) == _PNG
    assert store.read(second) == _PNG


def test_discard_refuses_a_published_object(tmp_path: Path) -> None:
    store = _local(tmp_path)
    uri = _publish(store, _PNG)
    with pytest.raises(ValueError, match="storage published"):
        store.discard(uri)
    assert store.read(uri) == _PNG


def test_cleanup_keeps_the_current_temp(tmp_path: Path) -> None:
    store = _local(tmp_path)
    current = store.put_temporary(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    )
    store.cleanup_temporary(product_id=_PRODUCT, spec_version=2, keep_sha256=_digest(_PNG))
    assert store.read(current.storage_uri) == _PNG


def test_cleanup_removes_a_superseded_temp(tmp_path: Path) -> None:
    store = _local(tmp_path)
    old = store.put_temporary(product_id=_PRODUCT, spec_version=2, sha256=_digest(_OLD), data=_OLD)
    store.put_temporary(product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG)
    store.cleanup_temporary(product_id=_PRODUCT, spec_version=2, keep_sha256=_digest(_PNG))
    assert not _uri_path(store, old.storage_uri).exists()


def test_a_temp_symlink_is_not_removed(tmp_path: Path) -> None:
    store = _local(tmp_path)
    victim = tmp_path / "victim"
    victim.write_bytes(_OLD)
    uri = store.put_temporary(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    ).storage_uri
    path = _uri_path(store, uri)
    path.unlink()
    path.symlink_to(victim)
    with pytest.raises(ValueError, match="storage symlink"):
        store.discard(uri)
    assert path.is_symlink()
    assert victim.read_bytes() == _OLD


def test_cleanup_does_not_follow_a_temp_directory(tmp_path: Path) -> None:
    store = _local(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    kept = outside / "keep"
    kept.write_bytes(_OLD)
    link = store.root / "temporary" / str(_PRODUCT) / "2"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="storage symlink"):
        store.cleanup_temporary(product_id=_PRODUCT, spec_version=2, keep_sha256=_digest(_PNG))
    assert kept.read_bytes() == _OLD


def test_a_missing_local_object_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match="storage missing"):
        store.read(f"fixture://{_PRODUCT}/2/{_digest(_PNG)}")


def test_a_traversal_uri_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    secret = tmp_path / "secret"
    secret.write_bytes(_OLD)
    with pytest.raises(ValueError, match="storage path"):
        store.read("fixture://../../secret")
    assert secret.read_bytes() == _OLD


def test_a_foreign_uri_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match="storage role"):
        store.read("https://example.com/a/b/c")


def test_local_signed_retrieval_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    uri = _publish(store, _PNG)
    with pytest.raises(ValueError, match="storage signed"):
        store.signed_retrieval(uri)


def test_internal_retrieval_names_the_object(tmp_path: Path) -> None:
    store = _local(tmp_path)
    uri = _publish(store, _PNG)
    assert store.internal_retrieval(uri) == "internal:" + uri


def test_s3_internal_retrieval_is_refused() -> None:
    store = SimS3AssetStore()
    uri = store.publish(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    ).storage_uri
    with pytest.raises(ValueError, match="storage internal"):
        store.internal_retrieval(uri)


def test_a_missing_object_has_no_token() -> None:
    store = SimS3AssetStore()
    with pytest.raises(ValueError, match="storage missing"):
        store.signed_retrieval(f"s3://simulation/{_PRODUCT}/2/{_digest(_PNG)}")


def test_a_temporary_object_is_not_signed() -> None:
    store = SimS3AssetStore()
    uri = store.put_temporary(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    ).storage_uri
    with pytest.raises(ValueError, match="storage role"):
        store.signed_retrieval(uri)


def test_a_token_for_another_uri_is_refused() -> None:
    store = SimS3AssetStore()
    first = store.publish(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    ).storage_uri
    second = store.publish(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_GIF), data=_GIF
    ).storage_uri
    token = store.signed_retrieval(first)
    with pytest.raises(ValueError, match="storage signature"):
        store.read_signed(token, second)
    assert store.read_signed(token, first) == _PNG


def test_s3_discard_refuses_a_foreign_uri() -> None:
    store = SimS3AssetStore()
    with pytest.raises(ValueError, match="storage role"):
        store.discard("s3://other/a/1/ab")


def test_s3_discard_refuses_published() -> None:
    store = SimS3AssetStore()
    uri = store.publish(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    ).storage_uri
    with pytest.raises(ValueError, match="storage published"):
        store.discard(uri)
    assert store.read(uri) == _PNG


def test_s3_cleanup_keeps_published() -> None:
    store = SimS3AssetStore()
    published = store.publish(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_GIF), data=_GIF
    ).storage_uri
    store.put_temporary(product_id=_PRODUCT, spec_version=2, sha256=_digest(_OLD), data=_OLD)
    store.put_temporary(product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG)
    store.cleanup_temporary(product_id=_PRODUCT, spec_version=2, keep_sha256=_digest(_PNG))
    assert store.read(published) == _GIF


def test_s3_cleanup_removes_a_superseded_temp() -> None:
    store = SimS3AssetStore()
    store.put_temporary(product_id=_PRODUCT, spec_version=2, sha256=_digest(_OLD), data=_OLD)
    store.put_temporary(product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG)
    first = store.cleanup_temporary(product_id=_PRODUCT, spec_version=2, keep_sha256=_digest(_PNG))
    second = store.cleanup_temporary(product_id=_PRODUCT, spec_version=2, keep_sha256=_digest(_PNG))
    assert _digest(_OLD) in first
    assert second == ()


def test_a_missing_s3_object_is_refused() -> None:
    store = SimS3AssetStore()
    with pytest.raises(ValueError, match="storage missing"):
        store.read(f"s3://simulation/{_PRODUCT}/2/{_digest(_PNG)}")


def test_s3_cleanup_keeps_the_current_temp() -> None:
    store = SimS3AssetStore()
    kept = store.put_temporary(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    ).storage_uri
    store.cleanup_temporary(product_id=_PRODUCT, spec_version=2, keep_sha256=_digest(_PNG))
    assert store.read(kept) == _PNG


def test_s3_same_bytes_are_idempotent() -> None:
    store = SimS3AssetStore()
    first = store.publish(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    ).storage_uri
    second = store.publish(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    ).storage_uri
    assert first == second
    assert store.read(first) == _PNG
