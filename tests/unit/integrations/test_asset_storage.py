"""Fixture asset storage. Each refusal has its own kill."""

from __future__ import annotations

import errno
import hashlib
import os
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


def test_publish_does_not_follow_a_symlinked_parent(tmp_path: Path) -> None:
    store = _local(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    role = store.root / "published"
    role.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="storage symlink"):
        _publish(store, _PNG)
    assert list(outside.iterdir()) == []


def test_discard_does_not_follow_a_symlinked_product(tmp_path: Path) -> None:
    store = _local(tmp_path)
    outside = tmp_path / "outside"
    spec = outside / "2"
    spec.mkdir(parents=True)
    digest = _digest(_PNG)
    victim = spec / digest
    victim.write_bytes(_PNG)
    product = store.root / "temporary" / str(_PRODUCT)
    product.parent.mkdir(parents=True)
    product.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="storage symlink"):
        store.discard(f"temp://{_PRODUCT}/2/{digest}")
    assert victim.read_bytes() == _PNG


def test_cleanup_does_not_follow_a_symlinked_role(tmp_path: Path) -> None:
    store = _local(tmp_path)
    outside = tmp_path / "outside" / str(_PRODUCT) / "2"
    outside.mkdir(parents=True)
    digest = _digest(_OLD)
    victim = outside / digest
    victim.write_bytes(_OLD)
    role = store.root / "temporary"
    role.symlink_to(tmp_path / "outside", target_is_directory=True)
    with pytest.raises(ValueError, match="storage symlink"):
        store.cleanup_temporary(product_id=_PRODUCT, spec_version=2, keep_sha256=_digest(_PNG))
    assert victim.read_bytes() == _OLD


def test_a_symlink_swapped_during_the_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _local(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    digest = _digest(_PNG)
    (outside / digest).write_bytes(_OLD)
    spec = store.root / "published" / str(_PRODUCT) / "2"
    spec.mkdir(parents=True)
    real_open = os.open

    def swapping_open(
        path: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if path == "2" and dir_fd is not None and spec.is_dir() and not spec.is_symlink():
            spec.rmdir()
            spec.symlink_to(outside, target_is_directory=True)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swapping_open)
    with pytest.raises(ValueError, match="storage symlink"):
        store.read(f"fixture://{_PRODUCT}/2/{digest}")
    assert (outside / digest).read_bytes() == _OLD


def test_a_dotdot_key_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    secret = tmp_path / "secret"
    secret.write_bytes(_OLD)
    with pytest.raises(ValueError, match="storage path"):
        store.read(f"fixture://{_PRODUCT}/../{_digest(_PNG)}")
    assert secret.read_bytes() == _OLD


def test_a_symlinked_parent_read_stays_inside(tmp_path: Path) -> None:
    store = _local(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    digest = _digest(_PNG)
    (outside / digest).write_bytes(_OLD)
    spec = store.root / "published" / str(_PRODUCT) / "2"
    spec.parent.mkdir(parents=True)
    spec.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="storage symlink"):
        store.read(f"fixture://{_PRODUCT}/2/{digest}")
    assert (outside / digest).read_bytes() == _OLD


def test_internal_retrieval_refuses_a_missing_object(tmp_path: Path) -> None:
    store = _local(tmp_path)
    _publish(store, _GIF)
    with pytest.raises(ValueError, match="storage missing"):
        store.internal_retrieval(f"fixture://{_PRODUCT}/2/{_digest(_PNG)}")


def test_internal_retrieval_refuses_tampered_bytes(tmp_path: Path) -> None:
    store = _local(tmp_path)
    uri = _publish(store, _PNG)
    _uri_path(store, uri).write_bytes(_GIF)
    with pytest.raises(ValueError, match="storage bytes"):
        store.internal_retrieval(uri)


def test_a_crash_mid_write_can_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _local(tmp_path)
    real_write = os.write

    def boom(_descriptor: int, _data: bytes | bytearray | memoryview) -> int:
        raise OSError(errno.EIO, "disk")

    monkeypatch.setattr(os, "write", boom)
    with pytest.raises(OSError, match="disk"):
        _publish(store, _PNG)
    monkeypatch.setattr(os, "write", real_write)
    final = store.root / "published" / str(_PRODUCT) / "2" / _digest(_PNG)
    assert not final.exists()
    uri = _publish(store, _PNG)
    assert store.read(uri) == _PNG


def test_publish_fsyncs_the_file_before_linking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    real_open = os.open
    real_fsync = os.fsync
    real_link = os.link
    created: set[int] = set()

    def open_hook(
        path: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        if flags & os.O_CREAT:
            created.add(descriptor)
        return descriptor

    def fsync(descriptor: int) -> None:
        order.append("file" if descriptor in created else "dir")
        real_fsync(descriptor)

    def link(src: str, dst: str, **kwargs: int | bool | None) -> None:
        order.append("link")
        real_link(src, dst, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", open_hook)
    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "link", link)
    _publish(_local(tmp_path), _PNG)
    assert order == ["file", "link", "dir"]


def test_the_temp_file_is_created_exclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[int] = []
    real_open = os.open

    def open_hook(
        path: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if isinstance(path, str) and path.startswith("."):
            seen.append(flags)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", open_hook)
    _publish(_local(tmp_path), _PNG)
    assert seen
    assert seen[0] & os.O_EXCL


def test_the_temp_file_is_created_without_following(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[int] = []
    real_open = os.open

    def open_hook(
        path: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if isinstance(path, str) and path.startswith("."):
            seen.append(flags)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", open_hook)
    _publish(_local(tmp_path), _PNG)
    assert seen
    assert seen[0] & os.O_NOFOLLOW


def test_s3_mismatched_digest_is_refused() -> None:
    store = SimS3AssetStore()
    with pytest.raises(ValueError, match="storage digest"):
        store.publish(product_id=_PRODUCT, spec_version=2, sha256=_digest(_GIF), data=_PNG)
    with pytest.raises(ValueError, match="storage missing"):
        store.read(f"s3://simulation/{_PRODUCT}/2/{_digest(_GIF)}")


def test_s3_tampered_bytes_collide() -> None:
    store = SimS3AssetStore()
    uri = store.publish(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    ).storage_uri
    store._objects[uri] = _GIF  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ValueError, match="storage collision"):
        store.publish(product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG)
    assert store._objects[uri] == _GIF  # pyright: ignore[reportPrivateUsage]


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


def test_a_uuid_with_a_suffix_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match=r"^storage path$"):
        store.read(f"fixture://{str(_PRODUCT)}x/2/{_digest(_PNG)}")


def test_a_65_hex_digest_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match=r"^storage path$"):
        store.read(f"fixture://{_PRODUCT}/2/{'a' * 65}")


def test_a_non_uuid_key_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match=r"^storage path$"):
        store.read(f"fixture://not-a-uuid/2/{_digest(_PNG)}")


@pytest.mark.parametrize("spec", ["0", "01", "-1", "x"])
def test_a_bad_spec_key_is_refused(tmp_path: Path, spec: str) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match=r"^storage path$"):
        store.read(f"fixture://{_PRODUCT}/{spec}/{_digest(_PNG)}")


def test_a_fullwidth_spec_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match=r"^storage path$"):
        store.read(f"fixture://{_PRODUCT}/\uff11/{_digest(_PNG)}")


def test_a_non_hex_digest_key_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match=r"^storage path$"):
        store.read(f"fixture://{_PRODUCT}/2/{'g' * 64}")


def test_a_leading_slash_key_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    secret = tmp_path / "secret"
    secret.write_bytes(_OLD)
    with pytest.raises(ValueError, match=r"^storage path slash$"):
        store.read(f"fixture:///{_PRODUCT}/2/{_digest(_PNG)}")
    assert secret.read_bytes() == _OLD


def test_a_backslash_key_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match=r"^storage path backslash$"):
        store.read(f"fixture://{_PRODUCT}\\2/{_digest(_PNG)}")


def test_a_four_part_key_is_refused(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match=r"^storage path length$"):
        store.read(f"fixture://{_PRODUCT}/2/{_digest(_PNG)}/extra")


def test_a_dot_segment_is_refused_on_its_own(tmp_path: Path) -> None:
    store = _local(tmp_path)
    with pytest.raises(ValueError, match=r"^storage path dots$"):
        store.read(f"fixture://{_PRODUCT}/../{_digest(_PNG)}")


def test_the_directory_walk_refuses_a_dot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _local(tmp_path)
    (store.root / "published").mkdir()
    secret = tmp_path / "secret"
    secret.write_bytes(_OLD)

    def dotted(_uri: str) -> tuple[str, str, str, str]:
        return ("published", "..", "2", _digest(_PNG))

    monkeypatch.setattr("money_machine.integrations.storage.local._key", dotted)
    with pytest.raises(ValueError, match=r"^storage path$"):
        store.read("fixture://ignored")
    assert secret.read_bytes() == _OLD


def test_a_raced_link_with_other_bytes_collides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _local(tmp_path)

    def racing_link(
        _src: str,
        dst: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        del src_dir_fd, follow_symlinks
        assert dst_dir_fd is not None
        descriptor = os.open(dst, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644, dir_fd=dst_dir_fd)
        os.write(descriptor, _GIF)
        os.close(descriptor)
        raise FileExistsError(errno.EEXIST, "exists", dst)

    monkeypatch.setattr(os, "link", racing_link)
    with pytest.raises(ValueError, match=r"^storage collision$"):
        _publish(store, _PNG)
    final = store.root / "published" / str(_PRODUCT) / "2" / _digest(_PNG)
    assert final.read_bytes() == _GIF


def test_a_vanished_link_target_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _local(tmp_path)
    empty = b""
    digest = _digest(empty)

    def vanished_link(
        _src: str,
        dst: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        del _src, src_dir_fd, dst_dir_fd, follow_symlinks
        raise FileExistsError(errno.EEXIST, "exists", dst)

    monkeypatch.setattr(os, "link", vanished_link)
    with pytest.raises(ValueError, match=r"^storage missing$"):
        store.publish(product_id=_PRODUCT, spec_version=2, sha256=digest, data=empty)
    final = store.root / "published" / str(_PRODUCT) / "2" / digest
    assert not final.exists()


def test_a_failed_write_leaves_no_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _local(tmp_path)

    def boom(_descriptor: int, _data: bytes | bytearray | memoryview) -> int:
        raise OSError(errno.EIO, "disk")

    monkeypatch.setattr(os, "write", boom)
    with pytest.raises(OSError, match="disk"):
        _publish(store, _PNG)
    spec_dir = store.root / "published" / str(_PRODUCT) / "2"
    assert spec_dir.is_dir()
    assert list(spec_dir.iterdir()) == []


def test_cleanup_keeps_an_orphan_temp_name(tmp_path: Path) -> None:
    store = _local(tmp_path)
    current = store.put_temporary(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    )
    orphan = _uri_path(store, current.storage_uri).parent / ".orphan"
    orphan.write_bytes(b"leak")
    removed = store.cleanup_temporary(
        product_id=_PRODUCT, spec_version=2, keep_sha256=_digest(_PNG)
    )
    assert orphan.read_bytes() == b"leak"
    assert removed == ()
    assert store.read(current.storage_uri) == _PNG


def test_cleanup_refuses_a_bad_keep_hash(tmp_path: Path) -> None:
    store = _local(tmp_path)
    uri = store.put_temporary(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    ).storage_uri
    with pytest.raises(ValueError, match=r"^storage hash$"):
        store.cleanup_temporary(product_id=_PRODUCT, spec_version=2, keep_sha256="nope")
    assert store.read(uri) == _PNG


def test_s3_cleanup_refuses_a_bad_keep_hash() -> None:
    store = SimS3AssetStore()
    uri = store.put_temporary(
        product_id=_PRODUCT, spec_version=2, sha256=_digest(_PNG), data=_PNG
    ).storage_uri
    with pytest.raises(ValueError, match=r"^storage hash$"):
        store.cleanup_temporary(product_id=_PRODUCT, spec_version=2, keep_sha256="nope")
    assert store.read(uri) == _PNG
