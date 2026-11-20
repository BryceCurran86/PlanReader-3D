"""Source-neutral cross-sheet area attribution and duplicate-owner veto tests."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from pb_live_canonical_floor_surface import (
    LiveCanonicalFloorSurfaceObject, LiveCanonicalFloorSurfaceComposition,
)
from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus
from pb_source_cross_view_floor_correspondence_shadow import (
    enrich_cross_sheet_floor_with_documented_area,
)


def _floor(job="unknown-building", face="face-a"):
    return LiveCanonicalFloorSurfaceObject(
        canonical_floor_id=f"floor:{job}:{face}",
        physical_floor_surface_id=f"physical:{job}:{face}",
        room_entity_id=f"room:{job}:{face}",
        document_id=f"document:{job}", revision_id=f"revision:{job}",
        source_sha256="a" * 64, snapshot_id=f"snapshot:{job}",
        page_id="6", viewport_id=None,
        polygon_pdf_pts=((0., 0.), (10., 0.), (10., 10.), (0., 10.)),
        area_page_pts2=100., bounding_wall_ids=(), canonical_bounding_wall_ids=(),
        source_room_face_record_id=face, evidence_ids=(f"wall:{face}",),
        geometry_complete=True, metric_geometry_complete=False,
        metric_area_m2=None, metric_area_quantity_id=None,
        metric_area_authority=None, finish_descriptor=None,
        structural_slab_id=None, physical_floor_surface_identity_resolved=True,
        commercial_quantity_authority=False,
    )


def _area(f, *, evidence_id="area-source-a", value=12.25, **changes):
    meta = dict(
        room_revision_id=f.revision_id, room_snapshot_id=f.snapshot_id,
        source_sha256=f.source_sha256,
        source_room_face_record_id=f.source_room_face_record_id,
        physical_room_id=f"physical-room:{f.source_room_face_record_id}",
        source_dimension_page_id="12",
    )
    meta.update(changes)
    return SimpleNamespace(
        source_room_face_record_id=f.source_room_face_record_id,
        physical_room_id=meta["physical_room_id"],
        source_dimension_page_id="12",
        area_evidence=EvidenceAtom(
            evidence_id=evidence_id, document_id=f.document_id,
            page_id=f.page_id, kind="explicit_room_area",
            method="authenticated_cross_view_figured_dimensions",
            normalized_value=value, unit="m2",
            status=EvidenceResolutionStatus.CORROBORATED, metadata=meta,
        ),
    )


def _apply(floors, areas):
    return enrich_cross_sheet_floor_with_documented_area(
        floors=LiveCanonicalFloorSurfaceComposition(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(), floors=tuple(floors), source_pages=(6, 12),
        ),
        room_areas=SimpleNamespace(
            status=EvidenceResolutionStatus.CORROBORATED,
            records=tuple(areas),
        ),
    ).floors


@pytest.mark.parametrize("job", ["unseen-hospital", "new-residence", "retail-2027"])
def test_unfamiliar_source_uses_exact_same_cross_sheet_area_rules(job):
    f = _floor(job)
    (result,) = _apply([f], [_area(f)])
    assert result.metric_area_m2 == 12.25
    assert result.metric_area_authority == "documented_dimension"
    assert "area-source-a" in result.evidence_ids
    assert result.commercial_quantity_authority is False


@pytest.mark.parametrize("change", [
    {"room_revision_id": "old-revision"},
    {"room_snapshot_id": "other-snapshot"},
    {"source_sha256": "b" * 64},
    {"source_room_face_record_id": "other-face"},
    {"source_dimension_page_id": "other-page"},
])
def test_foreign_source_or_revision_cannot_fill_floor(change):
    f = _floor()
    assert _apply([f], [_area(f, **change)]) == (f,)


@pytest.mark.parametrize("value", [0.0, -3.0])
def test_nonpositive_original_area_remains_unmeasured(value):
    f = _floor()
    assert _apply([f], [_area(f, value=value)]) == (f,)


def test_duplicate_face_cannot_choose_last_writer_or_first_writer():
    f = _floor()
    a, b = _area(f, evidence_id="one"), _area(f, evidence_id="two")
    assert _apply([f], [a, b]) == (f,)
    assert _apply([f], [b, a]) == (f,)


def test_reused_source_area_id_does_not_measure_two_rooms():
    a, b = _floor(face="face-a"), _floor(face="face-b")
    assert _apply([a, b], [
        _area(a, evidence_id="shared"), _area(b, evidence_id="shared"),
    ]) == (a, b)


def test_existing_measured_area_cannot_be_overwritten():
    f = _floor()
    fixed = replace(f, metric_area_m2=20., metric_area_quantity_id="existing")
    assert _apply([fixed], [_area(f)]) == (fixed,)


def test_duplicate_physical_face_floor_owners_stay_unmeasured():
    f = _floor()
    rival = replace(f, canonical_floor_id="different-canonical")
    assert _apply([f, rival], [_area(f)]) == (f, rival)
