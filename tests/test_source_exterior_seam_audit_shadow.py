"""Contract tests for the non-authoritative exterior seam audit."""
from types import SimpleNamespace

import pytest
from shapely.geometry import box

import pb_source_exterior_seam_audit_shadow as audit


class Bar:
    polygon = box(0, 0, 2, 2)

    def native_path_indices(self):
        return (12,)


def test_missing_path_is_explicit_and_never_joins(monkeypatch):
    monkeypatch.setattr(audit, "walk_source_unbounded_building_face", lambda *a, **k:
                        SimpleNamespace(status="ABSTAINED", reason="open",
                                        unclosed_dwelling_sides=("left", "right"),
                                        internal_party_wall_native_path_ids=()))
    monkeypatch.setattr(audit, "diagnose_source_outside_face_neighbors", lambda *a, **k: {
        "canonical_walk_reason": "open", "neighbors": [],
        "grey_seam_pairs": [],
    })
    result = audit.audit_exterior_seams(
        [Bar()], [99, 12, 99], source_sha256="a" * 64, page_index=2,
    )
    assert [r["native_path_id"] for r in result["receipts"]] == [12, 99]
    assert result["source_missing_path_ids"] == [99]
    assert result["receipts"][1]["status"] == "ABSTAINED"
    assert result["unclosed_dwelling_sides"] == ["left", "right"]
    assert result["measurement_authorized"] is False
    assert result["building_footprint_authenticated"] is False
    assert result["snap_join_applied"] is False
    assert result["official_frozen120_score_change"] == 0
    assert result["audit_id"] == audit.audit_exterior_seams(
        [Bar()], [12, 99], source_sha256="a" * 64, page_index=2,
    )["audit_id"]


@pytest.mark.parametrize("kwargs", [
    {"source_sha256": "bad", "page_index": 2},
    {"source_sha256": "A" * 64, "page_index": 2},
    {"source_sha256": "a" * 64, "page_index": -1},
    {"source_sha256": "a" * 64, "page_index": True},
])
def test_invalid_source_scope_rejected(kwargs):
    with pytest.raises(ValueError):
        audit.audit_exterior_seams([], [12], **kwargs)


@pytest.mark.parametrize("paths", [[], [-1], [True], list(range(65))])
def test_unbounded_or_invalid_paths_rejected(paths):
    with pytest.raises(ValueError):
        audit.audit_exterior_seams([], paths, source_sha256="a" * 64, page_index=2)
