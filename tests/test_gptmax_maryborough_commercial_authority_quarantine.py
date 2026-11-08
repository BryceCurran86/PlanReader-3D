"""Source-neutral regressions for authored physical/material authority bypasses."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
from types import SimpleNamespace

import fitz
import pytest

import pb_maryborough_customer_authority as customer
import pb_maryborough_floor_area_customer as subset
import pb_source_cross_view_floor_correspondence_shadow as correspondence
from pb_cross_view_floor_finish_authority import (
    CrossViewFloorFinishProducer,
    _source_owned_mark_eligible_for_existing_physical_floor,
)
from pb_migration_contracts import EvidenceResolutionStatus as Status
from tests.test_cross_view_floor_finish_authority_v1 import (
    _patch_material_viewports,
    _payload,
    _source_room_area_and_floor,
)
from tests.test_maryborough_customer_authority import _assert_empty_abstain
from tests.test_source_cross_view_floor_correspondence_shadow import (
    TARGET_SHEET,
    support_sheet,
)


def _authored_correspondence(areas, floors, code="FT999"):
    return SimpleNamespace(
        status=Status.CORROBORATED,
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        canonical_floor_id=floors.floors[0].canonical_floor_id,
        physical_room_id="unrelated-room",
        source_sha256="0" * 64,
        wall_bounded_on_both_sheets=True,
        wall_evidence_identical_on_both_sheets=True,
        cross_sheet_wall_equivalences=tuple(
            SimpleNamespace(status=Status.CORROBORATED) for _ in range(4)
        ),
        doorway_transitions=(SimpleNamespace(status=Status.CORROBORATED),),
        material_code=code,
        support_dimension_box_pdf_pts=(
            areas.records[0].area_evidence.metadata["source_dimension_box_pdf_pts"]
        ),
        authority_blockers=(),
    )


@pytest.mark.parametrize("codes", [(), ("FT999",)])
@pytest.mark.parametrize("pages", [None, ("1", "2")])
def test_authored_correspondence_cannot_supply_absent_material_authority(
    monkeypatch, codes, pages,
):
    _patch_material_viewports(monkeypatch)
    source, areas, floors = _source_room_area_and_floor(
        _payload(detail_codes=codes, schedule_lines=()),
    )
    result = CrossViewFloorFinishProducer.from_source(
        source=source, room_areas=areas, floors=floors,
        correspondence_records=(_authored_correspondence(areas, floors),),
        page_ids=pages,
    ).publish()
    assert result.quantities == ()
    assert result.status is not Status.CORROBORATED


def test_correspondence_cannot_hide_competing_authenticated_finishes(monkeypatch):
    _patch_material_viewports(monkeypatch)
    source, areas, floors = _source_room_area_and_floor(_payload(
        detail_codes=("FT1", "FT2"),
        schedule_lines=("FT1 Porcelain floor tile", "FT2 Ceramic floor tile"),
    ))
    result = CrossViewFloorFinishProducer.from_source(
        source=source, room_areas=areas, floors=floors,
        correspondence_records=(_authored_correspondence(areas, floors),),
    ).publish()
    assert result.status is Status.CONFLICT
    assert result.quantities == ()


def test_default_genuine_finish_receipts_survive_untrusted_correspondence(monkeypatch):
    _patch_material_viewports(monkeypatch)
    source, areas, floors = _source_room_area_and_floor(_payload())
    ordinary = CrossViewFloorFinishProducer.from_source(
        source=source, room_areas=areas, floors=floors,
    ).publish()
    attempted_override = CrossViewFloorFinishProducer.from_source(
        source=source, room_areas=areas, floors=floors,
        correspondence_records=(_authored_correspondence(areas, floors),),
    ).publish()
    assert ordinary.status is Status.CORROBORATED
    assert ordinary.quantities
    assert attempted_override == ordinary


def test_caller_flags_cannot_authenticate_a_cross_sheet_physical_floor():
    _source, areas, floors = _source_room_area_and_floor(_payload())
    occurrence = SimpleNamespace(page_id="2", code="FT1")
    assert not _source_owned_mark_eligible_for_existing_physical_floor(
        floor=floors.floors[0], occurrence=occurrence,
        source_owned_shadow=True,
        correspondence_records=(_authored_correspondence(areas, floors, "FT1"),),
    )
    assert _source_owned_mark_eligible_for_existing_physical_floor(
        floor=floors.floors[0],
        occurrence=SimpleNamespace(page_id="1", code="FT1"),
        source_owned_shadow=True,
    )


def _geometric_inputs():
    return dict(
        document_id="synthetic-doc", revision_id="synthetic-revision",
        source_sha256="a" * 64, snapshot_id="synthetic-snapshot",
        canonical_floor_id="synthetic-floor", physical_room_id="synthetic-room",
        source_room_face_record_id="synthetic-face",
        support_segments=support_sheet(), target_segments=deepcopy(TARGET_SHEET),
        marks=[dict(code="FT3", x=300.0, y=1450.0, registered_region=True)],
        door_observations=[dict(callout="D15")],
        schedule_observations=[dict(door_callout="D15", door_width_mm=920)],
        dimension_witness_observations=[dict(code="3570"), dict(code="2536")],
        room_label_observations=[dict(label="OFFICE")],
    )


@pytest.mark.parametrize("changes", [
    {},
    {"schedule_observations": [dict(door_callout="D15", door_width_mm=1)]},
    {"dimension_witness_observations": [
        dict(code="3570", trusted=False), dict(code="2536", trusted=False),
    ]},
    {"marks": [dict(code="FT3", x=300.0, y=1450.0, registered_region=False)]},
])
def test_word_and_geometry_observations_never_authenticate_a_threshold(changes):
    inputs = _geometric_inputs() | changes
    original = deepcopy(inputs)
    result = correspondence.authenticate_maryborough_office_cross_sheet_correspondence(
        **inputs,
    )
    assert result.status is Status.CANDIDATE
    assert not result.commercial_projection_allowed
    assert not result.takeoff_eligible
    assert correspondence.DOORWAY_TRANSITION_UNAVAILABLE in result.authority_blockers
    assert correspondence.DIMENSION_WITNESS_UNAVAILABLE in result.authority_blockers
    assert result.doorway_transitions
    assert all(d.status is Status.ABSTAINED and d.door_width_mm is None
               and d.threshold_aligned_with_internal_face is False
               for d in result.doorway_transitions)
    assert all(w.status is Status.CANDIDATE for w in result.cross_sheet_wall_equivalences)
    assert inputs == original
    replay = correspondence.authenticate_maryborough_office_cross_sheet_correspondence(
        **inputs,
    )
    assert replay == result


def _disconnected_dimension_pdf():
    document = fitz.open()
    try:
        for number in range(31):
            document.new_page(
                width=1600 if number in (6, 10) else 595,
                height=2300 if number in (6, 10) else 842,
            )
        for index, segments in ((6, TARGET_SHEET), (10, support_sheet())):
            shape = document[index].new_shape()
            for segment in segments:
                shape.draw_line(
                    (segment["x1"], segment["y1"]),
                    (segment["x2"], segment["y2"]),
                )
            shape.finish(color=(0, 0, 0), width=0.5)
            shape.commit()
        for index, position, text in (
            (6, (180, 1450), "OFFICE"), (6, (200, 1390), "D15"),
            (10, (300, 1430), "OFFICE"), (10, (300, 1450), "FT3"),
            (10, (140, 1490), "3570"), (10, (310, 2020), "2536"),
            (27, (40, 60), "D15"),
        ):
            document[index].insert_text(position, text, fontsize=9)
        # No dimension witnesses at the numeric labels, material definition,
        # door schedule width, door leaf or physical finished threshold.
        return document.tobytes()
    finally:
        document.close()


def test_pdf_words_and_geometric_agreement_cannot_issue_a_sealed_customer_row(
    tmp_path, monkeypatch,
):
    payload = _disconnected_dimension_pdf()
    source_path = tmp_path / "disconnected-dimension-source.pdf"
    source_path.write_bytes(payload)
    monkeypatch.setattr(customer, "MARYBOROUGH_SOURCE_SHA256",
                        hashlib.sha256(payload).hexdigest())
    for issuer in (
        customer.issue_all_original_maryborough_customer_quantities,
        subset.issue_original_maryborough_floor_customer_areas,
    ):
        _assert_empty_abstain(issuer(source_path))
    with fitz.open(stream=payload, filetype="pdf") as document:
        result = correspondence.authenticate_maryborough_office_cross_sheet_correspondence(
            document_id="synthetic-doc", revision_id="synthetic-revision",
            source_sha256=hashlib.sha256(payload).hexdigest(),
            snapshot_id="synthetic-snapshot", canonical_floor_id="synthetic-floor",
            physical_room_id="synthetic-room", source_room_face_record_id="synthetic-face",
            doc=document,
        )
    assert result.status is Status.CANDIDATE
    assert not result.commercial_projection_allowed
    assert not result.takeoff_eligible


def test_a_claimed_firm_upstream_cannot_bypass_subset_seal_validation(monkeypatch):
    _patch_material_viewports(monkeypatch)
    source, areas, floors = _source_room_area_and_floor(_payload())
    genuine = CrossViewFloorFinishProducer.from_source(
        source=source, room_areas=areas, floors=floors,
    ).publish().quantities[0]
    authored = replace(genuine, input_entity_ids=(customer.OFFICE_PHYSICAL_FLOOR_ID,))
    upstream = customer.MaryboroughCustomerResult(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        reason_codes=("source_owned_physical_quantity_resolved",),
        quantities=(authored,), traces=(object(),), sealed_run=object(),
        customer_rows=({"quantity_id": authored.quantity_id},),
    )
    monkeypatch.setattr(subset, "issue_all_original_maryborough_customer_quantities",
                        lambda *_args, **_kwargs: upstream)
    _assert_empty_abstain(subset.issue_original_maryborough_floor_customer_areas("unused.pdf"))
    assert upstream.quantities == (authored,)
    assert upstream.sealed_run is not None


@pytest.mark.parametrize("store_kind", ["missing", "foreign", "changed", "text", "mutable", "malformed"])
def test_exact_owned_revision_denial_survives_the_safety_repair(monkeypatch, store_kind):
    payload = b"%PDF-source-neutral-owned-revision"
    stores = {
        "missing": {}, "foreign": {"other-revision": payload},
        "changed": {"owned-revision": payload + b"changed"},
        "text": {"owned-revision": payload.decode()},
        "mutable": {"owned-revision": bytearray(payload)}, "malformed": [],
    }
    def unexpected_authentication(**_kwargs):
        raise AssertionError("unowned or malformed source bytes reached correspondence")
    monkeypatch.setattr(correspondence,
                        "authenticate_maryborough_office_cross_sheet_correspondence",
                        unexpected_authentication)
    source = SimpleNamespace(_store=SimpleNamespace(source_bytes_by_revision=stores[store_kind]))
    area = SimpleNamespace(source_room_face_record_id="face", physical_room_id="room",
                           source_dimension_page_id="11", room_label="OFFICE")
    floor = SimpleNamespace(
        source_room_face_record_id="face", room_entity_id="room", page_id="7",
        revision_id="owned-revision", source_sha256=hashlib.sha256(payload).hexdigest(),
    )
    assert correspondence.resolve_cross_sheet_floor_correspondence_for_claim(
        source=source, cross_view_area=SimpleNamespace(records=(area,)),
        canonical_floors=SimpleNamespace(floors=(floor,)),
    ) == ()


def test_owned_source_bytes_reach_diagnostics_without_granting_commercial_authority(monkeypatch):
    payload = b"%PDF-source-neutral-owned-revision"
    observed = []
    def candidate_only(**kwargs):
        observed.append(kwargs)
        return SimpleNamespace(status=Status.CANDIDATE, commercial_projection_allowed=False)
    monkeypatch.setattr(correspondence,
                        "authenticate_maryborough_office_cross_sheet_correspondence",
                        candidate_only)
    source = SimpleNamespace(_store=SimpleNamespace(
        source_bytes_by_revision={"owned-revision": payload},
    ))
    area = SimpleNamespace(source_room_face_record_id="face", physical_room_id="room",
                           source_dimension_page_id="11", room_label="OFFICE")
    digest = hashlib.sha256(payload).hexdigest()
    floor = SimpleNamespace(
        source_room_face_record_id="face", room_entity_id="room", page_id="7",
        revision_id="owned-revision", source_sha256=digest,
        document_id="source-doc", snapshot_id="source-snapshot", canonical_floor_id="floor",
    )
    assert correspondence.resolve_cross_sheet_floor_correspondence_for_claim(
        source=source, cross_view_area=SimpleNamespace(records=(area,)),
        canonical_floors=SimpleNamespace(floors=(floor,)),
    ) == ()
    assert len(observed) == 1
    assert observed[0]["source_bytes"] is payload
    assert observed[0]["source_sha256"] == digest
    assert observed[0]["revision_id"] == floor.revision_id
    assert observed[0]["snapshot_id"] == floor.snapshot_id
