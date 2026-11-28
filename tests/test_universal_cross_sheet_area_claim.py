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


# Only real producer-registered physical correspondence can enter the
# generic cross-sheet pathway; a synthetic rectangle does not mint authority.
import hashlib
from itertools import count
from pb_source_cross_view_floor_correspondence_shadow import (
    SourceCrossViewFloorCorrespondenceRecord, CrossSheetWallEquivalenceRecord,
    DoorwayTransitionEvidence, _REGISTERED_FLOOR_CORRESPONDENCES_BY_SNAPSHOT,
    resolve_cross_sheet_floor_correspondence_for_claim,
)

_CASE = count(1)


def _issued_source_correspondence(job="unseen-retail", *, room_label="LAB", schedule_room="LAB"):
    suffix = next(_CASE)
    data = ("original construction source " + str(suffix)).encode()
    sha = hashlib.sha256(data).hexdigest()
    f = replace(_floor(job), source_sha256=sha, snapshot_id=f"snapshot:{job}:{suffix}")
    a = _area(f)
    a.room_label = room_label
    wall_eq = tuple(
        CrossSheetWallEquivalenceRecord(
            support_page_id="12", target_page_id="6", side_name=side,
            support_face_coord=10.0, target_face_coord=10.0,
            covered_interval_iou=1.0,
        ) for side in ("x0", "x1", "y0", "y1")
    )
    door = DoorwayTransitionEvidence(
        door_callout="D1", page_id="6", wall_side="y0",
        schedule_page_id="15", door_width_mm=900., scheduled_room_name=schedule_room,
    )
    rec = SourceCrossViewFloorCorrespondenceRecord(
        record_id=f"receipt:{job}:{suffix}",
        canonical_floor_id=f.canonical_floor_id,
        physical_room_id=a.physical_room_id,
        source_room_face_record_id=f.source_room_face_record_id,
        support_page_id="12", target_page_id="6",
        support_dimension_box_pdf_pts=(0., 0., 10., 10.),
        target_box_pdf_pts=(0., 0., 10., 10.),
        registration_orientation="identity", registration_scale=1.,
        registration_translation_pdf_pts=(0., 0.),
        registration_support_pt=100., registration_runner_up_support_pt=1.,
        registration_null_support_pt=0.,
        wall_bounded_on_both_sheets=True,
        wall_evidence_identical_on_both_sheets=True,
        side_kinds={"x0": "wall", "x1": "wall", "y0": "door", "y1": "wall"},
        finish_codes_in_box={"FT9": 1}, material_code="FT9",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(), authority_blockers=(),
        commercial_projection_allowed=True, takeoff_eligible=True,
        cross_sheet_wall_equivalences=wall_eq, doorway_transitions=(door,),
        document_id=f.document_id, revision_id=f.revision_id,
        source_sha256=sha, snapshot_id=f.snapshot_id,
    )
    _REGISTERED_FLOOR_CORRESPONDENCES_BY_SNAPSHOT.register_issued(
        ((f.snapshot_id, rec.record_id),), rec,
    )
    source = SimpleNamespace(
        _store=SimpleNamespace(source_bytes_by_revision={f.revision_id: data}),
    )
    return source, SimpleNamespace(records=(a,)), SimpleNamespace(floors=(f,)), rec


def _resolve(source, areas, floors, *receipts):
    return resolve_cross_sheet_floor_correspondence_for_claim(
        source=source, cross_view_area=areas, canonical_floors=floors,
        issued_records=receipts,
    )


@pytest.mark.parametrize("job", ["unknown-mall", "different-station", "new-villa"])
def test_generic_registered_source_correspondence_accepts_any_project(job):
    source, areas, floors, rec = _issued_source_correspondence(job)
    assert _resolve(source, areas, floors, rec) == (rec,)


def test_unregistered_copied_authority_cannot_enter_floor_finish():
    source, areas, floors, rec = _issued_source_correspondence()
    assert _resolve(source, areas, floors, replace(rec)) == ()
    assert _resolve(source, areas, floors, replace(rec, record_id="invented")) == ()


def test_source_correspondence_rejects_wrong_original_bytes_and_revision():
    source, areas, floors, rec = _issued_source_correspondence()
    source._store.source_bytes_by_revision[rec.revision_id] = b"foreign bytes"
    assert _resolve(source, areas, floors, rec) == ()
    del source._store.source_bytes_by_revision[rec.revision_id]
    assert _resolve(source, areas, floors, rec) == ()


@pytest.mark.parametrize("changed", [
    {"takeoff_eligible": False}, {"commercial_projection_allowed": False},
    {"wall_evidence_identical_on_both_sheets": False},
    {"authority_blockers": ("unverified",)},
    {"doorway_transitions": ()},
    {"finish_codes_in_box": {"FT9": 2}},
    {"target_page_id": "18"},
])
def test_producer_receipt_with_unresolved_authority_never_resolves(changed):
    source, areas, floors, rec = _issued_source_correspondence()
    assert _resolve(source, areas, floors, replace(rec, **changed)) == ()


def test_two_competing_issued_receipts_cannot_choose_a_winner():
    source, areas, floors, rec = _issued_source_correspondence()
    other = replace(rec, record_id="another-issuer")
    _REGISTERED_FLOOR_CORRESPONDENCES_BY_SNAPSHOT.register_issued(
        ((rec.snapshot_id, other.record_id),), other,
    )
    assert _resolve(source, areas, floors, rec, other) == ()
    assert _resolve(source, areas, floors, other, rec) == ()


def test_generic_cross_sheet_must_match_source_room_and_door_schedule():
    source, areas, floors, rec = _issued_source_correspondence(
        "new-project-2027", room_label="STORAGE", schedule_room="OFFICE",
    )
    assert _resolve(source, areas, floors, rec) == ()


@pytest.mark.parametrize("replace_kwargs", (
    {"geometry_complete": False},
    {"physical_floor_surface_identity_resolved": False},
    {"source_sha256": "not-an-original-digest"},
))
def test_cross_sheet_area_requires_real_physical_floor_and_source(replace_kwargs):
    f = _floor()
    incomplete = replace(f, **replace_kwargs)
    assert _apply([incomplete], [_area(incomplete)]) == (incomplete,)


def test_cross_sheet_area_needs_source_owned_physical_room_and_support_page():
    f = _floor()
    area = _area(f)
    area.physical_room_id = ""
    assert _apply([f], [area]) == (f,)
    area = _area(f)
    area.source_dimension_page_id = ""
    assert _apply([f], [area]) == (f,)


def test_producer_registered_door_must_belong_to_source_declared_door_wall():
    source, areas, floors, rec = _issued_source_correspondence("any-building")
    bad = replace(
        rec, record_id=rec.record_id + ":door-side-swapped",
        side_kinds={"x0": "wall", "x1": "wall", "y0": "wall", "y1": "door"},
    )
    _REGISTERED_FLOOR_CORRESPONDENCES_BY_SNAPSHOT.register_issued(
        ((bad.snapshot_id, bad.record_id),), bad,
    )
    assert _resolve(source, areas, floors, bad) == ()


def test_real_source_wall_vocabulary_with_openings_can_host_a_verified_door():
    source, areas, floors, original = _issued_source_correspondence("unseen-drawing")
    native = replace(
        original, record_id=original.record_id + ":native-wall-vocabulary",
        side_kinds={"x0": "full", "x1": "full",
                    "y0": "with_openings", "y1": "full"},
    )
    _REGISTERED_FLOOR_CORRESPONDENCES_BY_SNAPSHOT.register_issued(
        ((native.snapshot_id, native.record_id),), native,
    )
    assert _resolve(source, areas, floors, native) == (native,)


def test_full_continuous_wall_cannot_pass_as_doorway_source_side():
    source, areas, floors, original = _issued_source_correspondence("unseen-drawing")
    invalid = replace(
        original, record_id=original.record_id + ":full-wall-door-mismatch",
        side_kinds={"x0": "full", "x1": "full", "y0": "full", "y1": "full"},
    )
    _REGISTERED_FLOOR_CORRESPONDENCES_BY_SNAPSHOT.register_issued(
        ((invalid.snapshot_id, invalid.record_id),), invalid,
    )
    assert _resolve(source, areas, floors, invalid) == ()


def test_live_resolver_autodiscovers_source_registered_correspondence_for_unseen_job():
    source, area, floors, receipt = _issued_source_correspondence(
        "completely-new-building-2027",
    )
    assert resolve_cross_sheet_floor_correspondence_for_claim(
        source=source, cross_view_area=area, canonical_floors=floors,
    ) == (receipt,)


def test_live_resolver_rejects_registered_receipt_after_original_pdf_bytes_change():
    source, area, floors, receipt = _issued_source_correspondence(
        "independent-building-2027",
    )
    source._store.source_bytes_by_revision[receipt.revision_id] = b"wrong-original-source"
    assert resolve_cross_sheet_floor_correspondence_for_claim(
        source=source, cross_view_area=area, canonical_floors=floors,
    ) == ()


def test_unknown_job_without_independently_registered_correspondence_abstains():
    floor = _floor("unseen-2028")
    area = _area(floor)
    source = SimpleNamespace(
        _store=SimpleNamespace(source_bytes_by_revision={floor.revision_id: b"unrelated"}),
    )
    assert resolve_cross_sheet_floor_correspondence_for_claim(
        source=source,
        cross_view_area=SimpleNamespace(records=(area,)),
        canonical_floors=SimpleNamespace(floors=(floor,)),
    ) == ()


def test_registered_only_accepts_existing_generic_producer_receipt():
    source, areas, floors, receipt = _issued_source_correspondence("new-building")
    assert resolve_cross_sheet_floor_correspondence_for_claim(
        source=source, cross_view_area=areas, canonical_floors=floors,
        registered_only=True,
    ) == (receipt,)


@pytest.mark.parametrize("room_label", ["OFFICE", "FOOD PREP", "PWD"])
def test_registered_only_never_invokes_legacy_room_dispatch(monkeypatch, room_label):
    import pb_source_cross_view_floor_correspondence_shadow as bridge

    data = b"synthetic source bytes"
    floor = replace(_floor(), page_id="7", source_sha256=hashlib.sha256(data).hexdigest())
    area = _area(floor)
    area.room_label = room_label
    area.source_dimension_page_id = "11"
    source = SimpleNamespace(
        _store=SimpleNamespace(source_bytes_by_revision={floor.revision_id: data}),
    )

    def forbidden(**kwargs):
        pytest.fail("Legacy room dispatch invoked in registered-only mode")

    for name in (
        "authenticate_maryborough_office_cross_sheet_correspondence",
        "authenticate_maryborough_food_prep_cross_sheet_correspondence",
        "authenticate_maryborough_pwd_cross_sheet_correspondence",
    ):
        monkeypatch.setattr(bridge, name, forbidden)
    assert bridge.resolve_cross_sheet_floor_correspondence_for_claim(
        source=source, cross_view_area=SimpleNamespace(records=(area,)),
        canonical_floors=SimpleNamespace(floors=(floor,)), registered_only=True,
    ) == ()


def test_registered_only_rejects_foreign_source_without_fallback():
    source, areas, floors, receipt = _issued_source_correspondence("another-building")
    source._store.source_bytes_by_revision[receipt.revision_id] = b"foreign"
    assert resolve_cross_sheet_floor_correspondence_for_claim(
        source=source, cross_view_area=areas, canonical_floors=floors,
        registered_only=True,
    ) == ()


def test_live_claim_forwards_registered_only_switch_without_default_change(monkeypatch):
    import pb_live_physical_net_wall_integration as live

    calls = []
    sentinel = object()

    def fake_claim(*args, **kwargs):
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(live, "_collect_live_physical_net_wall_claim", fake_claim)
    assert live.collect_live_physical_net_wall_claim("unused.pdf") is sentinel
    assert "cross_sheet_registered_only" not in calls[-1]
    assert live.collect_live_physical_net_wall_claim(
        "unused.pdf", cross_sheet_registered_only=True,
    ) is sentinel
    assert calls[-1]["cross_sheet_registered_only"] is True
    with pytest.raises(ValueError, match="explicit boolean"):
        live.collect_live_physical_net_wall_claim(
            "unused.pdf", cross_sheet_registered_only=1,
        )
