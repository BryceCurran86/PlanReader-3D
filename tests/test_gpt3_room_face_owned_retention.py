from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

import pb_source_room_face_authority as R
from pb_migration_contracts import EvidenceResolutionStatus
from tools.verify_gpt3_room_face_owned_retention import (
    LOT16_SOURCE_SHA,
    verify_room_face_owned_retention,
)


def _record(wall_id, first, second):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(centerline_pts=(first, second)),
    )


def _box(prefix, x0, y0, x1, y1):
    return [
        _record(f"{prefix}-top", (x0, y0), (x1, y0)),
        _record(f"{prefix}-right", (x1, y0), (x1, y1)),
        _record(f"{prefix}-bottom", (x1, y1), (x0, y1)),
        _record(f"{prefix}-left", (x0, y1), (x0, y0)),
    ]


def _scope(snapshot):
    records = _box("room", 0.0, 0.0, 20.0, 10.0) + [
        _record("partition", (10.0, 0.0), (10.0, 10.0))
    ]
    return SimpleNamespace(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=tuple(records),
        document_id="doc",
        revision_id="rev",
        source_sha256=LOT16_SOURCE_SHA,
        snapshot_id=snapshot,
        page_id="3",
        decision_scope_id="wall-source:page-3",
    )


def _report(snapshot):
    scope = _scope(snapshot)
    witnesses = list(R.audit_source_room_face_owned_witnesses(scope))
    evaluation = R._shadow_ownership_evaluation(scope)
    return {
        "source_sha256": LOT16_SOURCE_SHA,
        "snapshot_id": snapshot,
        "primitive_safety_cap": 20_000,
        "source_room_face_scopes": [{
            "selector": {
                "page_id": "3",
                "decision_scope_id": "wall-source:page-3",
            },
            "result": {
                "ownership_evaluation": {
                    "owned_face_ids": list(evaluation.owned_face_ids),
                }
            },
        }],
        "source_room_face_owned_witness_scopes": [{
            "selector": {
                "page_id": "3",
                "decision_scope_id": "wall-source:page-3",
            },
            "owned_face_witnesses": witnesses,
        }],
    }


def test_owned_witnesses_cover_every_evaluated_face_without_changing_authority():
    scope = _scope("snapshot-a")
    before = R._derive_scope(scope)
    witnesses = R.audit_source_room_face_owned_witnesses(scope)
    after = R._derive_scope(scope)

    assert before == after
    assert len(witnesses) == len(before.ownership_evaluation.owned_face_ids) == 2
    assert {row["face_id"] for row in witnesses} == set(
        before.ownership_evaluation.owned_face_ids
    )
    for row in witnesses:
        assert len(row["polygon_pdf_pts"]) == len(row["boundary_wall_edges"])
        assert set(row["bounding_wall_ids"]) == {
            wall_id for wall_id, _edge in row["boundary_wall_edges"]
        }
        assert row["area_page_pts2"] > 0


def test_snapshot_only_face_id_rekey_retains_exact_physical_propositions():
    baseline = _report("snapshot-before")
    candidate = _report("snapshot-after")
    assert {
        row["face_id"]
        for row in baseline["source_room_face_owned_witness_scopes"][0][
            "owned_face_witnesses"
        ]
    }.isdisjoint({
        row["face_id"]
        for row in candidate["source_room_face_owned_witness_scopes"][0][
            "owned_face_witnesses"
        ]
    })

    result = verify_room_face_owned_retention(baseline, candidate)
    assert result["verified_room_face_owned_bijection"] is True
    assert result["owned_face_proposition_count"] == 2
    assert result["room_publication_granted"] is False
    assert result["quantity_publication_granted"] is False
    assert result["benchmark_score_granted"] is False


@pytest.mark.parametrize("fault", ["polygon", "owner", "edge", "area"])
def test_changed_physical_room_face_proposition_fails_closed(fault):
    baseline = _report("snapshot-before")
    candidate = _report("snapshot-after")
    row = candidate["source_room_face_owned_witness_scopes"][0][
        "owned_face_witnesses"
    ][0]
    if fault == "polygon":
        polygon = [list(point) for point in row["polygon_pdf_pts"]]
        polygon[0][0] += 0.25
        row["polygon_pdf_pts"] = polygon
    elif fault == "owner":
        owners = list(row["bounding_wall_ids"])
        owners[0] = "different-wall"
        row["bounding_wall_ids"] = owners
    elif fault == "edge":
        boundary = [
            [owner, [list(edge[0]), list(edge[1])]]
            for owner, edge in row["boundary_wall_edges"]
        ]
        boundary[0][1][0][0] += 0.25
        row["boundary_wall_edges"] = boundary
    else:
        row["area_page_pts2"] += 1.0
    with pytest.raises(ValueError):
        verify_room_face_owned_retention(baseline, candidate)


def test_duplicate_physical_room_face_proposition_fails_closed():
    baseline = _report("snapshot-before")
    candidate = _report("snapshot-after")
    rows = candidate["source_room_face_owned_witness_scopes"][0][
        "owned_face_witnesses"
    ]
    duplicate = deepcopy(rows[0])
    duplicate["face_id"] = "different-snapshot-face-id"
    rows.append(duplicate)
    candidate["source_room_face_scopes"][0]["result"]["ownership_evaluation"][
        "owned_face_ids"
    ].append("different-snapshot-face-id")
    with pytest.raises(ValueError, match="not unique"):
        verify_room_face_owned_retention(baseline, candidate)


def test_missing_owned_witness_fails_against_evaluation_census():
    baseline = _report("snapshot-before")
    candidate = _report("snapshot-after")
    candidate["source_room_face_owned_witness_scopes"][0][
        "owned_face_witnesses"
    ].pop()
    with pytest.raises(ValueError, match="count does not match"):
        verify_room_face_owned_retention(baseline, candidate)


@pytest.mark.parametrize("field,value", [
    ("source_sha256", "f" * 64),
    ("primitive_safety_cap", 19_999),
])
def test_source_envelope_or_cap_change_fails_closed(field, value):
    baseline = _report("snapshot-before")
    candidate = _report("snapshot-after")
    candidate[field] = value
    with pytest.raises(ValueError):
        verify_room_face_owned_retention(baseline, candidate)


def test_same_snapshot_is_not_a_retention_proof():
    baseline = _report("snapshot-before")
    candidate = _report("snapshot-before")
    with pytest.raises(ValueError, match="distinct source snapshots"):
        verify_room_face_owned_retention(baseline, candidate)
