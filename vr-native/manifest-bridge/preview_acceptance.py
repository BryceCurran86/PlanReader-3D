"""Offline acceptance gate for untrusted native manifest-bridge preview packets.

Never authenticates a drawing, Unity binary, headset, or commercial quantity.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

SHA = re.compile(r"^[a-f0-9]{64}$")
MAX_BYTES = 16 * 1024 * 1024
MAX_WALLS = 20_000


def validate(packet, expected_source_sha=None):
    errors = []
    if not isinstance(packet, dict):
        return ["preview packet must be an object"]
    for key, value in (
        ("schemaVersion", "1.0.0"),
        ("renderState", "review"),
        ("localEvidenceTrusted", False),
        ("measurementAuthorized", False),
        ("commercialQuantityPublicationAllowed", False),
        ("canEdit", False),
    ):
        if type(packet.get(key)) is not type(value) or packet.get(key) != value:
            errors.append(f"invalid or missing {key}")
    scope = packet.get("sourceScope")
    if not isinstance(scope, dict):
        return errors + ["sourceScope must be an object"]
    for key in ("workspaceId", "projectId", "documentId", "revisionId", "snapshotId"):
        v = scope.get(key)
        if not isinstance(v, str) or not v.strip() or len(v) > 256:
            errors.append(f"invalid sourceScope.{key}")
    sha = scope.get("sourceSha256")
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        errors.append("invalid sourceScope.sourceSha256")
    if expected_source_sha is not None:
        if not isinstance(expected_source_sha, str) or not SHA.fullmatch(expected_source_sha):
            errors.append("invalid expected source SHA")
        elif sha != expected_source_sha:
            errors.append("source SHA mismatch")
    revision = scope.get("modelRevision")
    if type(revision) is not int or revision < 0:
        errors.append("invalid model revision")
    coords = packet.get("coordinateSystem")
    if not isinstance(coords, dict) or coords.get("unit") != "metres":
        errors.append("unsupported coordinate system")
    else:
        if not _point(coords.get("renderOrigin"), 3):
            errors.append("invalid render origin")
    walls = packet.get("walls")
    if not isinstance(walls, list) or len(walls) > MAX_WALLS:
        return errors + ["walls must be a bounded array"]
    count = packet.get("inputObjectCount")
    if type(count) is not int or count < len(walls) or count > MAX_WALLS:
        errors.append("invalid input object count")
    seen = set()
    for i, wall in enumerate(walls):
        if not isinstance(wall, dict):
            errors.append(f"wall {i} must be an object")
            continue
        ident = wall.get("objectId")
        if not isinstance(ident, str) or not ident.strip() or len(ident) > 256 or ident in seen:
            errors.append(f"invalid or duplicate wall {i} ID")
        else:
            seen.add(ident)
        for flag, expected in (("renderState", "review"), ("locallyAuthenticated", False),
                               ("canEdit", False), ("commercialQuantityPublicationAllowed", False)):
            if type(wall.get(flag)) is not type(expected) or wall.get(flag) != expected:
                errors.append(f"wall {i} invalid {flag}")
        kind = wall.get("kind")
        if kind not in ("wallLine", "wallFace"):
            errors.append(f"wall {i} invalid kind")
        start, end = wall.get("start"), wall.get("end")
        if not _point(start, 2) or not _point(end, 2) or start == end:
            errors.append(f"wall {i} invalid endpoints")
        height = wall.get("heightM")
        if kind == "wallFace":
            if not _finite(height) or height <= 0:
                errors.append(f"wall {i} invalid height")
        elif height is not None:
            errors.append(f"wall {i} unexpected height")
    return errors


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _point(value, length):
    return isinstance(value, list) and len(value) == length and all(_finite(x) for x in value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--expected-source-sha", default=None)
    args = parser.parse_args()
    try:
        if args.packet.stat().st_size > MAX_BYTES:
            raise ValueError("preview packet exceeds 16 MiB")
        raw = args.packet.read_bytes()
        packet = json.loads(raw.decode("utf-8"))
        errors = validate(packet, args.expected_source_sha)
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        errors = [f"unreadable preview packet: {type(exc).__name__}"]
        raw = b""
    print(json.dumps({"status": "PASS_REVIEW_ONLY" if not errors else "ABSTAIN",
                      "errors": errors, "packetSha256": hashlib.sha256(raw).hexdigest()},
                     sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
