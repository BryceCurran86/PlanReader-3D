"""Classify only clearly isolated VR browser changes for development feedback.

Not a merge/release gate and never a replacement for the required full CI.
Use a NUL-delimited git diff --no-renames --name-only against the merge base.
Unknown, empty, non-UTF-8, or mixed change sets require full validation.
"""
from __future__ import annotations

import sys
from pathlib import PurePosixPath

_ALLOWED = {".ts", ".tsx", ".mjs", ".css", ".js", ".html"}


def vr_only_paths(raw: bytes) -> bool:
    if not raw or not raw.endswith(b"\0"):
        return False
    try:
        paths = raw[:-1].decode("utf-8", errors="strict").split("\0")
    except UnicodeDecodeError:
        return False
    for path in paths:
        parts = path.split("/")
        if (len(parts) < 3 or parts[0] != "vr-editor"
                or parts[1] not in {"src", "tests"}
                or any(part in {"", ".", ".."} for part in parts)
                or "\\" in path or any(ord(ch) < 32 for ch in path)
                or PurePosixPath(path).suffix not in _ALLOWED):
            return False
    return bool(paths)


if __name__ == "__main__":
    print("vr-only" if vr_only_paths(sys.stdin.buffer.read()) else "full-required")
