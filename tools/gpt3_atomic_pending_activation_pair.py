"""GPT3 standalone identity activations publish two outputs exclusively and atomically.

Source-sealed/customer/identity-map inputs must never be overwritten by their
own activation CLI. A candidate map without a matching activation receipt is
NOT a released source identity. Stage both outputs before any publish, link
create-only, and roll back one if the other cannot be published.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any


FROZEN_ROOT = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/frozen_holdout/full_plan_v2"
)


def preflight_new_activation_pair(
    outputs: tuple[Path, Path],
    *,
    inputs: tuple[Path, ...],
) -> None:
    if len(outputs) != 2 or any(not isinstance(p, Path) for p in outputs):
        raise TypeError("two typed output paths required")
    if any(not isinstance(p, Path) for p in inputs):
        raise TypeError("typed input paths required")
    targets = tuple(path.resolve() for path in outputs)
    sources = {path.resolve() for path in inputs}
    frozen = FROZEN_ROOT.resolve()
    if targets[0] == targets[1]:
        raise ValueError("two independent activation output paths required")
    for path, target in zip(outputs, targets):
        if path.exists() or path.is_symlink():
            raise FileExistsError(
                "activation outputs must be new and never overwrite source or prior evidence"
            )
        if target in sources:
            raise ValueError(
                "activation output aliases original signed/source/customer input"
            )
        if target == frozen or target.is_relative_to(frozen):
            raise ValueError(
                "activation output cannot write into frozen benchmark evidence"
            )


def source_input_snapshot(
    inputs: tuple[Path, ...],
) -> tuple[tuple[Path, str], ...]:
    """Pin original source bytes before any parsed/verified source replay."""
    return tuple(
        (path, sha256(path.read_bytes()).hexdigest())
        for path in inputs
    )


def _assert_original_inputs_unchanged(
    originals: tuple[tuple[Path, str], ...],
) -> None:
    if any(sha256(path.read_bytes()).hexdigest() != digest
           for path, digest in originals):
        raise ValueError(
            "original source/sealed/customer/identity inputs changed before activation publish"
        )


ACTIVATION_COMMIT_MARKER_VERSION = "gpt3_identity_activation_commit.v1"


def _serialized(payload: dict[str, Any]) -> bytes:
    # The committed digest covers exact on-disk bytes rather than an
    # unverified normalized/rewritten JSON interpretation.
    return (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False)
            + "\n").encode("utf-8")


def _fsync_directory(path: Path) -> None:
    """Make a published hard link durable before the receipt marker appears."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    # A hand-crafted JSON object with duplicate keys can make two consumers
    # disagree about the same signed/map identity despite a stable file hash.
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("activation identity receipt/map contains duplicate JSON key")
        out[key] = value
    return out


def read_committed_active_identity_map(
    path: Path, *, receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Fail closed on orphaned/nonmatching committed maps.

    An EMPTY baseline can bootstrap without an activation; a nonempty map
    must have a matching receipt published last. The receipt is a commit
    marker, not producer/source or independent benchmark authorization.
    """
    if not isinstance(path, Path):
        raise TypeError("active identity map path must be typed")
    if receipt_path is not None and not isinstance(receipt_path, Path):
        raise TypeError("activation receipt path must be typed")
    first_receipt: bytes | None = None
    if receipt_path is not None:
        # The map must not be read as activated before seeing its marker.
        first_receipt = receipt_path.read_bytes()
    map_bytes = path.read_bytes()
    raw = json.loads(map_bytes, object_pairs_hook=_reject_duplicate_json_keys)
    if type(raw) is not dict:
        raise ValueError("active identity map must be an object")
    if first_receipt is None:
        if raw.get("bindings") != []:
            raise ValueError(
                "nonempty active identity map requires its committed activation receipt"
            )
        return raw

    marker = json.loads(first_receipt, object_pairs_hook=_reject_duplicate_json_keys)
    if type(marker) is not dict or (
        marker.get("activation_commit_marker_version")
        != ACTIVATION_COMMIT_MARKER_VERSION
    ):
        raise ValueError("active identity map has no valid activation commit marker")
    digest = sha256(map_bytes).hexdigest()
    if marker.get("identity_map_sha256") != digest:
        raise ValueError("active identity map does not match committed receipt digest")
    if (
        marker.get("identity_map_project_id") != raw.get("project_id")
        or marker.get("identity_map_source_sha256s")
        != raw.get("source_sha256s")
    ):
        raise ValueError("active identity map source envelope differs from receipt")
    # A concurrent replacement/mutation during a read cannot be committed.
    if (
        receipt_path.read_bytes() != first_receipt
        or path.read_bytes() != map_bytes
    ):
        raise ValueError("active identity map or receipt changed during verification")
    return raw


def publish_new_activation_pair(
    outputs: tuple[Path, Path],
    payloads: tuple[dict[str, Any], dict[str, Any]],
    *,
    inputs: tuple[Path, ...],
    source_snapshot: tuple[tuple[Path, str], ...],
) -> None:
    """All-or-none exclusive publish for a source-signed map plus receipt."""
    preflight_new_activation_pair(outputs, inputs=inputs)
    if tuple(path for path, _ in source_snapshot) != inputs:
        raise ValueError("activation source snapshot does not cover exact original inputs")
    _assert_original_inputs_unchanged(source_snapshot)
    staged: list[Path] = []
    published: list[tuple[Path, tuple[int, int]]] = []
    try:
        # The map is durable first; receipt is the only committed reader
        # marker. A crash after only the first link leaves an inert orphan.
        map_bytes = _serialized(payloads[0])
        committed_receipt = {
            **payloads[1],
            "activation_commit_marker_version": ACTIVATION_COMMIT_MARKER_VERSION,
            "identity_map_sha256": sha256(map_bytes).hexdigest(),
            "identity_map_project_id": payloads[0].get("project_id"),
            "identity_map_source_sha256s": payloads[0].get("source_sha256s"),
        }
        for target, payload in zip(outputs, (payloads[0], committed_receipt)):
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(
                prefix=".gpt3-identity-activation-",
                suffix=".tmp", dir=target.parent,
            )
            staged_path = Path(name)
            staged.append(staged_path)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(payload, output, sort_keys=True, indent=2, allow_nan=False)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
        # A concurrent contributor must not modify the original source
        # receipt while the two outputs are staged for visible publication.
        _assert_original_inputs_unchanged(source_snapshot)
        preflight_new_activation_pair(outputs, inputs=inputs)
        for staged_path, target in zip(staged, outputs):
            original_stat = staged_path.stat()
            os.link(staged_path, target)
            published.append((
                target, (original_stat.st_dev, original_stat.st_ino)
            ))
            _fsync_directory(target.parent)
            # At this point no reader may accept the map until the final
            # receipt link becomes visible. Reconfirm source before commit.
            if target == outputs[0]:
                _assert_original_inputs_unchanged(source_snapshot)
        _assert_original_inputs_unchanged(source_snapshot)
    except BaseException:
        # Rollback only paths still pointing to the inode we published;
        # never remove a competing writer's file if it replaced that path.
        for target, inode in reversed(published):
            try:
                current = target.stat(follow_symlinks=False)
                if (current.st_dev, current.st_ino) == inode:
                    target.unlink()
            except FileNotFoundError:
                pass
        raise
    finally:
        for staged_path in staged:
            try:
                staged_path.unlink()
            except FileNotFoundError:
                pass


__all__ = [
    "preflight_new_activation_pair",
    "source_input_snapshot",
    "publish_new_activation_pair",
    "read_committed_active_identity_map",
    "ACTIVATION_COMMIT_MARKER_VERSION",
]
