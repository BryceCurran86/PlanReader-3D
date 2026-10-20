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
        for target, payload in zip(outputs, payloads):
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
]
