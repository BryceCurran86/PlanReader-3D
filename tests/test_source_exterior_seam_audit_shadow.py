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


def test_many_paths_compute_one_walk_and_one_source_topology(monkeypatch):
    class OtherBar(Bar):
        def native_path_indices(self):
            return (13,)

    source_walk = SimpleNamespace(
        status="ABSTAINED", reason="source_dwelling_region_still_open_to_outside",
        unclosed_dwelling_sides=("left", "right"),
        internal_party_wall_native_path_ids=(),
    )
    calls = {"walk": 0, "topology": 0, "neighbor": 0}

    def walk_once(*args, **kwargs):
        calls["walk"] += 1
        assert kwargs["source_wall_union"] is not None
        return source_walk

    def topology_once(*args, **kwargs):
        calls["topology"] += 1
        return ()

    def neighbor_receipt(*args, **kwargs):
        calls["neighbor"] += 1
        assert kwargs["canonical_walk"] is source_walk
        assert kwargs["topology_host_pairs"] == ()
        assert kwargs["source_wall_union"] is not None
        assert len(kwargs["owned_bars"]) == 2
        return {
            "canonical_walk_reason": source_walk.reason,
            "neighbors": [], "grey_seam_pairs": [],
        }

    monkeypatch.setattr(audit, "walk_source_unbounded_building_face", walk_once)
    monkeypatch.setattr(audit, "_topology_host_pairs", topology_once)
    monkeypatch.setattr(audit, "diagnose_source_outside_face_neighbors", neighbor_receipt)
    result = audit.audit_exterior_seams(
        [Bar(), OtherBar()], [13, 12],
        source_sha256="a" * 64, page_index=2,
    )
    assert calls == {"walk": 1, "topology": 1, "neighbor": 2}
    assert result["canonical_walk_status"] == "ABSTAINED"
    assert result["measurement_authorized"] is False


def test_neighbor_diagnostic_reuses_supplied_walk_and_topology(monkeypatch):
    import pb_source_unbounded_building_face_walk_shadow as core

    def unexpected(*args, **kwargs):
        raise AssertionError("recomputed expensive original-source walk or topology")

    monkeypatch.setattr(core, "walk_source_unbounded_building_face", unexpected)
    monkeypatch.setattr(core, "_topology_host_pairs", unexpected)
    walk = SimpleNamespace(
        status="ABSTAINED", reason="open",
        outer_wall_native_path_ids=(),
        internal_party_wall_native_path_ids=(),
    )
    bar = Bar()
    result = core.diagnose_source_outside_face_neighbors(
        [bar], 12, canonical_walk=walk, topology_host_pairs=(),
        source_wall_union=bar.polygon,
        owned_bars=((bar.polygon, (12,), bar),),
    )
    assert result["canonical_walk_reason"] == "open"
    assert result["native_path_id"] == 12
    assert result["measurement_authorized"] is False


def test_audit_identity_changes_with_source_geometry_not_only_path_ids():
    class Enlarged(Bar):
        polygon = box(0, 0, 3, 2)

    kwargs = {"source_sha256": "a" * 64, "page_index": 2}
    base = audit.audit_exterior_seams([Bar()], [12], **kwargs)
    changed = audit.audit_exterior_seams([Enlarged()], [12], **kwargs)
    assert base["audit_id"] != changed["audit_id"]
    assert base["schema_version"] == "shadow_exterior_seam_audit_v2"
    assert base["source_hash_authenticated"] is False
    assert base["source_hash_validation"] == "caller_supplied_format_only"
    assert base["measurement_authorized"] is False


def test_audit_identity_independent_of_native_bar_order():
    class Other(Bar):
        polygon = box(3, 0, 5, 2)

        def native_path_indices(self):
            return (13,)

    kwargs = {"source_sha256": "a" * 64, "page_index": 2}
    first = audit.audit_exterior_seams([Bar(), Other()], [12, 13], **kwargs)
    permuted = audit.audit_exterior_seams([Other(), Bar()], [13, 12], **kwargs)
    assert first["audit_id"] == permuted["audit_id"]
