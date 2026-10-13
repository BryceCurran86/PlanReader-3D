"""Verify exact original room-face ownership propositions across source snapshots.

This tool compares read-only owned-face witness sidecars emitted by
diag_gptmax_source_authority_stages. Snapshot-scoped face IDs are intentionally
ignored. A face is the same proposition only when page/scope, canonical polygon,
area, bounding wall identities and per-edge owner topology are all exactly
equal. Multiplicity must be one-to-one.

No room, quantity, customer output, benchmark identity or score is granted.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from typing import Any, Mapping

LOT16_SOURCE_SHA = (
    "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _tuple_point(value: object) -> tuple[float, float]:
    if type(value) not in (list, tuple) or len(value) != 2:
        raise ValueError("room-face point must contain two coordinates")
    if any(type(v) not in (int, float) for v in value):
        raise ValueError("room-face point coordinates must be numeric")
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(v) for v in point):
        raise ValueError("room-face point coordinates must be finite")
    return point


def _edge(value: object) -> tuple[tuple[float, float], tuple[float, float]]:
    if type(value) not in (list, tuple) or len(value) != 2:
        raise ValueError("room-face edge must contain two points")
    return (_tuple_point(value[0]), _tuple_point(value[1]))


def _witness_signature(row: Mapping[str, Any]) -> tuple[object, ...]:
    page_id = row.get("page_id")
    scope_id = row.get("decision_scope_id")
    polygon_raw = row.get("polygon_pdf_pts")
    wall_ids_raw = row.get("bounding_wall_ids")
    boundary_raw = row.get("boundary_wall_edges")
    area = row.get("area_page_pts2")
    if type(page_id) is not str or not page_id:
        raise ValueError("room-face witness page_id is malformed")
    if type(scope_id) is not str or not scope_id:
        raise ValueError("room-face witness decision scope is malformed")
    if type(polygon_raw) not in (list, tuple) or len(polygon_raw) < 3:
        raise ValueError("room-face witness polygon is malformed")
    polygon = tuple(_tuple_point(point) for point in polygon_raw)
    if type(wall_ids_raw) not in (list, tuple) or not wall_ids_raw:
        raise ValueError("room-face witness wall owners are missing")
    wall_ids = tuple(str(value) for value in wall_ids_raw)
    if (
        any(not value or value != value.strip() for value in wall_ids)
        or len(wall_ids) != len(set(wall_ids))
    ):
        raise ValueError("room-face witness wall owners are malformed")
    if type(boundary_raw) not in (list, tuple) or len(boundary_raw) != len(polygon):
        raise ValueError("room-face witness boundary ownership is incomplete")
    boundary: list[tuple[str, tuple[tuple[float, float], tuple[float, float]]]] = []
    for item in boundary_raw:
        if type(item) not in (list, tuple) or len(item) != 2:
            raise ValueError("room-face boundary owner entry is malformed")
        owner = item[0]
        if type(owner) is not str or not owner or owner != owner.strip():
            raise ValueError("room-face boundary owner identity is malformed")
        boundary.append((owner, _edge(item[1])))
    if {owner for owner, _edge_value in boundary} != set(wall_ids):
        raise ValueError("room-face boundary owners contradict bounding wall ids")
    if type(area) not in (int, float) or not math.isfinite(float(area)) or float(area) <= 0:
        raise ValueError("room-face witness area is invalid")
    return (
        page_id,
        scope_id,
        polygon,
        wall_ids,
        tuple(boundary),
        float(area),
    )


def _witnesses(report: Mapping[str, Any]) -> tuple[tuple[object, ...], ...]:
    scopes = report.get("source_room_face_owned_witness_scopes")
    if not isinstance(scopes, list) or not scopes:
        raise ValueError("source room-face owned witness sidecar unavailable")

    expected_owned: Counter[tuple[str, str]] = Counter()
    for scope in report.get("source_room_face_scopes") or ():
        if not isinstance(scope, Mapping):
            raise ValueError("source room-face scope is malformed")
        selector = scope.get("selector")
        result = scope.get("result")
        if not isinstance(selector, Mapping) or not isinstance(result, Mapping):
            raise ValueError("source room-face scope selector/result missing")
        evaluation = result.get("ownership_evaluation")
        if not isinstance(evaluation, Mapping):
            raise ValueError("source room-face ownership evaluation missing")
        page_id = str(selector.get("page_id") or "")
        scope_id = str(selector.get("decision_scope_id") or "")
        owned = evaluation.get("owned_face_ids")
        if type(owned) not in (list, tuple):
            raise ValueError("owned face ID census missing")
        expected_owned[(page_id, scope_id)] += len(owned)

    signatures: list[tuple[object, ...]] = []
    actual_owned: Counter[tuple[str, str]] = Counter()
    seen_ids: set[str] = set()
    for scope in scopes:
        if not isinstance(scope, Mapping):
            raise ValueError("owned witness scope is malformed")
        selector = scope.get("selector")
        rows = scope.get("owned_face_witnesses")
        if not isinstance(selector, Mapping) or not isinstance(rows, list):
            raise ValueError("owned witness scope selector/rows missing")
        page_id = str(selector.get("page_id") or "")
        scope_id = str(selector.get("decision_scope_id") or "")
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("owned face witness row must be an object")
            face_id = row.get("face_id")
            if type(face_id) is not str or not face_id or face_id in seen_ids:
                raise ValueError("owned face witness IDs must be unique and typed")
            seen_ids.add(face_id)
            signature = _witness_signature(row)
            if signature[0] != page_id or signature[1] != scope_id:
                raise ValueError("owned witness row contradicts scope ownership")
            signatures.append(signature)
            actual_owned[(page_id, scope_id)] += 1

    if actual_owned != expected_owned:
        raise ValueError("owned face witness count does not match ownership evaluation")
    counts = Counter(signatures)
    if any(count != 1 for count in counts.values()):
        raise ValueError("owned face physical proposition is not unique")
    return tuple(sorted(signatures, key=repr))


def verify_room_face_owned_retention(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    for report in (baseline, candidate):
        if report.get("source_sha256") != LOT16_SOURCE_SHA:
            raise ValueError("room-face retention source SHA mismatch")
        if report.get("primitive_safety_cap") != 20_000:
            raise ValueError("room-face retention primitive cap changed")
    if baseline.get("snapshot_id") == candidate.get("snapshot_id"):
        raise ValueError("room-face retention requires distinct source snapshots")

    before = _witnesses(baseline)
    after = _witnesses(candidate)
    if before != after:
        before_set = set(before)
        after_set = set(after)
        raise ValueError(
            "room-face owned physical propositions changed: "
            f"lost={len(before_set-after_set)} gained={len(after_set-before_set)}"
        )
    return {
        "source_sha256": LOT16_SOURCE_SHA,
        "baseline_snapshot_id": baseline.get("snapshot_id"),
        "candidate_snapshot_id": candidate.get("snapshot_id"),
        "owned_face_proposition_count": len(before),
        "verified_room_face_owned_bijection": True,
        "room_publication_granted": False,
        "quantity_publication_granted": False,
        "benchmark_score_granted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify_room_face_owned_retention(
        _load(args.baseline), _load(args.candidate)
    )
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
