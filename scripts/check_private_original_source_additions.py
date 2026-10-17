"""Refuse *new* owner/customer original-source payloads in a public Git tree.

This is a diff-only guard, not a source manifest rewrite, security scanner,
Git history purge or measurement issuer. Deletions are intentionally excluded
by the caller's git diff filter. Existing tracked files require PR #2920 and
separate coordinated history remediation.
"""
from __future__ import annotations

from pathlib import PurePosixPath
import sys


PRIVATE_SOURCE_ROOTS = ("documents/sources/", "benchmarks/sources/")


def _canonical_git_path(raw: str) -> str:
    if type(raw) is not str or not raw or "\x00" in raw:
        raise ValueError("Invalid changed-path record")
    path = raw.replace("\\", "/")
    if (
        path.startswith("/")
        or ":" in path.split("/", 1)[0]
        or any(part in ("", ".", "..") for part in path.split("/"))
    ):
        raise ValueError("Unsafe original-source changed-path scope")
    return path.casefold()


def blocked_source_additions(paths: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Report changed protected source payloads, never delete files."""
    denied = set()
    for raw in paths:
        path = _canonical_git_path(raw)
        if path.startswith(PRIVATE_SOURCE_ROOTS):
            denied.add(raw)
    return tuple(sorted(denied))


def main() -> int:
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
        denied = blocked_source_additions(paths)
    except ValueError as exc:
        print(f"Private original-source addition gate failed: {exc}", file=sys.stderr)
        return 1
    if denied:
        print(
            "Private original-source addition gate blocked these changed files. "
            "Use a private local/authorized source package and keep frozen SHA "
            "manifests (metadata) committed:",
            file=sys.stderr,
        )
        for file in denied:
            print(f"  - {file}", file=sys.stderr)
        return 1
    print("Private original-source additions check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
