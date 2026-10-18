"""Refuse *new* owner/customer original-source payloads in a public Git tree.

This is a diff-only guard, not a source manifest rewrite, security scanner,
Git history purge or measurement issuer. Deletions are intentionally excluded
by the caller's git diff filter. Existing tracked files require PR #2920 and
separate coordinated history remediation.

Besides the protected path roots, the guard reads the pinned original source
documents (name, size_bytes, sha256) from the frozen Full Plan V2 source
manifests, read-only, and also refuses a changed path whose basename is a
pinned original name, or whose checked-out bytes are a pinned original
(equal size, then equal SHA-256) at any path with any name. Only size-equal
files are hashed. A modified or re-saved copy is not an exact copy and is out
of reach of this check. The manifests are read from the checked-out tree; their
own integrity is enforced by the frozen-integrity gate, not here. When the
manifests cannot be read, or pin nothing, the guard fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import NamedTuple


PRIVATE_SOURCE_ROOTS = ("documents/sources/", "benchmarks/sources/")
PRIVATE_SOURCE_COMPONENTS = frozenset((".private-sources", "source-originals"))
SECRET_FILE_SUFFIXES = (".pem", ".p12", ".pfx", ".p8", ".jks")
SECRET_FILE_NAMES = frozenset(("id_rsa", "id_ed25519", ".npmrc"))
PINNED_MANIFEST_GLOB = (
    "benchmarks/frozen_holdout/full_plan_v2/projects/*/source_manifest.json"
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_HASH_CHUNK_BYTES = 1 << 20


class PinnedOriginals(NamedTuple):
    names: frozenset[str]  # casefolded basenames
    sha256_by_size: dict[int, frozenset[str]]


def _normalized_git_path(raw: str) -> str:
    if type(raw) is not str or not raw or "\x00" in raw:
        raise ValueError("Invalid changed-path record")
    path = raw.replace("\\", "/")
    if (
        path.startswith("/")
        or ":" in path.split("/", 1)[0]
        or any(part in ("", ".", "..") for part in path.split("/"))
    ):
        raise ValueError("Unsafe original-source changed-path scope")
    return path


def _canonical_git_path(raw: str) -> str:
    return _normalized_git_path(raw).casefold()


def load_pinned_originals(root: Path) -> PinnedOriginals:
    """Read the pinned original documents from the frozen source manifests.

    Fails closed (ValueError) when no manifest is readable, an entry is
    malformed, or nothing is pinned. Nothing is written.
    """
    manifests = sorted(Path(root).glob(PINNED_MANIFEST_GLOB))
    if not manifests:
        raise ValueError("No frozen source manifests found to pin original sources")
    names: set[str] = set()
    sha_by_size: dict[int, set[str]] = {}
    for manifest in manifests:
        try:
            documents = json.loads(manifest.read_text(encoding="utf-8"))["source_documents"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"Unreadable frozen source manifest: {manifest.name}") from exc
        if not isinstance(documents, list):
            raise ValueError(f"Malformed source_documents in {manifest.parent.name}")
        for entry in documents:
            if not isinstance(entry, dict):
                raise ValueError(f"Malformed source document in {manifest.parent.name}")
            name, size, digest = (
                entry.get("name"), entry.get("size_bytes"), entry.get("sha256"),
            )
            if (
                type(name) is not str or not name or "/" in name or "\\" in name
                or type(size) is not int or size <= 0
                or type(digest) is not str or not _SHA256_RE.fullmatch(digest)
            ):
                raise ValueError(f"Malformed pinned source document in {manifest.parent.name}")
            names.add(name.casefold())
            sha_by_size.setdefault(size, set()).add(digest)
    if not names:
        raise ValueError("Frozen source manifests pin no original sources")
    return PinnedOriginals(
        frozenset(names),
        {size: frozenset(digests) for size, digests in sha_by_size.items()},
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_pinned_original_bytes(path: Path, pinned: PinnedOriginals) -> bool:
    # A symlink's Git blob is its target text, not file bytes, so it is not
    # followed; a path absent from the working tree cannot be hashed.
    if path.is_symlink() or not path.is_file():
        return False
    digests = pinned.sha256_by_size.get(path.stat().st_size)
    return bool(digests) and _file_sha256(path) in digests


def source_addition_findings(
    paths: list[str] | tuple[str, ...],
    *,
    pinned: PinnedOriginals | None = None,
    root: Path | None = None,
) -> tuple[tuple[str, str], ...]:
    """Return sorted (changed path, reason) pairs for protected payloads.

    Without ``pinned`` only the path rules apply. With ``pinned`` the basename
    and exact-bytes rules also apply, resolving paths below ``root``.
    """
    found: dict[str, str] = {}
    for raw in paths:
        normalized = _normalized_git_path(raw)
        path = normalized.casefold()
        name = path.rsplit("/", 1)[-1]
        parts = path.split("/")
        reason = None
        if (
            path.startswith(PRIVATE_SOURCE_ROOTS)
            or any(part in PRIVATE_SOURCE_COMPONENTS for part in parts)
            or name in SECRET_FILE_NAMES
            or name.endswith(SECRET_FILE_SUFFIXES)
            or name == ".env"
            or (name.startswith(".env.") and name != ".env.example")
        ):
            reason = "protected source or secret path"
        elif pinned is not None and name in pinned.names:
            reason = "name of a pinned original source document"
        elif (
            pinned is not None
            and root is not None
            and _is_pinned_original_bytes(Path(root) / PurePosixPath(normalized), pinned)
        ):
            reason = "bytes of a pinned original source document"
        if reason is not None:
            found[raw] = reason
    return tuple(sorted(found.items()))


def blocked_source_additions(
    paths: list[str] | tuple[str, ...],
    *,
    pinned: PinnedOriginals | None = None,
    root: Path | None = None,
) -> tuple[str, ...]:
    """Report changed protected source payloads, never delete files."""
    return tuple(raw for raw, _ in source_addition_findings(paths, pinned=pinned, root=root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1],
        help="checked-out tree holding the changed files and frozen manifests",
    )
    args = parser.parse_args(argv)
    payload = sys.stdin.buffer.read()
    if not payload:
        print("Private original-source additions check: no changed paths.")
        return 0
    # -z is used by our caller to retain spaces and original Git paths. A
    # newline-stream fallback supports manual audits, not CI's source proof.
    if b"\x00" in payload:
        paths = [
            item.decode("utf-8", errors="strict")
            for item in payload.split(b"\x00") if item
        ]
    else:
        paths = [
            line for line in payload.decode("utf-8", errors="strict").splitlines()
            if line
        ]
    try:
        pinned = load_pinned_originals(args.root)
        findings = source_addition_findings(paths, pinned=pinned, root=args.root)
    except ValueError as exc:
        print(f"Private original-source addition gate failed: {exc}", file=sys.stderr)
        return 1
    if findings:
        print(
            "Private original-source addition gate blocked these changed files. "
            "Use a private local/authorized source package and keep frozen SHA "
            "manifests (metadata) committed:",
            file=sys.stderr,
        )
        for file, reason in findings:
            print(f"  - {file} ({reason})", file=sys.stderr)
        return 1
    print("Private original-source additions check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
