"""Opt-in finished-face gate: a ring face the original has not shown to be the exposed finished face is noncommercial."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from pb_layered_wall_doorway_room_face_scope_shadow import (
    LAYERED_RING_FINISHED_FACE_GATE_REASON,
    RING_FINISHED_FACE_REQUIRED_PREFIX,
    layered_ring_room_face_scope,
    layered_ring_scope_overrides,
)
from pb_layered_wall_doorway_room_ring_shadow import build_from_pdf_bytes
from pb_layered_wall_face_identity_shadow import (
    REASON_SCALE_UNAVAILABLE,
    REASON_STATEMENT_UNAVAILABLE,
    VERDICT_UNRESOLVED,
)
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_physical_net_wall_integration import (
    _collect_live_physical_net_wall_claim,
    collect_live_physical_net_wall_claim,
)
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_same_view_room_area_authority import SameViewRoomAreaProducer
from pb_source_room_area_bridge import build_source_room_area_bridge
from pb_source_room_face_authority import SourceRoomFaceSelector
from pb_source_visibility_authority import SourceVisibilityProducer

K = 0.5522847498
NOTE = (
    "THE INTERNAL WALLS TO BE 96mm PINE STUD FRAMES UNLESS OTHERWISE NOTED AND SHALL "
    "BE LINED WITH 10mm GYPROCK AND 6mm VILLA BOARD TO THE WET AREA'S AS REQUIRED"
)


POINTS_PER_METRE_AT_1_100 = 2834.645669 / 100.0


def layered_room_pdf(*, note: str | None = None, scale_bar: bool = False) -> bytes:
    """Room inner box (100,80)-(250,180); a swing doorway closes the ring; figured 3600 x 2400 (24 mm per pt)."""
    doc = fitz.open()
    page = doc.new_page(width=400.0, height=300.0)
    oc = doc.add_ocg("Enclosure_WallInternal", on=True)

    def rect(x0, y0, x1, y1):
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=None, fill=(0, 0, 0), oc=oc)

    rect(96, 76, 254, 80)
    rect(96, 180, 254, 184)
    rect(96, 80, 100, 180)
    rect(250, 80, 254, 110)
    rect(250, 134, 254, 180)
    c, o, t = (250, 110), (226, 110), (250, 134)
    p2 = (o[0] + K * (t[0] - c[0]), o[1] + K * (t[1] - c[1]))
    p3 = (t[0] + K * (o[0] - c[0]), t[1] + K * (o[1] - c[1]))
    page.draw_bezier(fitz.Point(*o), fitz.Point(*p2), fitz.Point(*p3), fitz.Point(*t), color=(0, 0, 0), width=0.34, oc=oc)
    page.draw_line(fitz.Point(*c), fitz.Point(*o), color=(0, 0, 0), width=0.34, oc=oc)
    page.draw_line((100.0, 70.0), (250.0, 70.0), color=(0, 0, 0), width=1.0)
    page.draw_line((100.0, 62.0), (100.0, 92.0), color=(0, 0, 0), width=1.0)
    page.draw_line((250.0, 62.0), (250.0, 92.0), color=(0, 0, 0), width=1.0)
    page.insert_text((164.0, 67.0), "3600", fontsize=9.0)
    page.draw_line((290.0, 80.0), (290.0, 180.0), color=(0, 0, 0), width=1.0)
    page.draw_line((250.0, 80.0), (298.0, 80.0), color=(0, 0, 0), width=1.0)
    page.draw_line((278.0, 180.0), (298.0, 180.0), color=(0, 0, 0), width=1.0)
    page.insert_text((287.0, 147.0), "2400", fontsize=9.0, rotate=90)
    page.insert_text((150.0, 130.0), "BED 2", fontsize=10.0)
    if scale_bar:  # one metre at 1:100 and its labels: the existing physical-scale authority can read it
        x0, x1, y = 60.0, 60.0 + POINTS_PER_METRE_AT_1_100 * (1.0 + 5.0e-6), 262.0
        shape = page.new_shape()
        shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
        shape.draw_line(fitz.Point(x0, y - 8.0), fitz.Point(x0, y + 8.0))
        shape.draw_line(fitz.Point(x1, y - 8.0), fitz.Point(x1, y + 8.0))
        shape.finish(width=1.0)
        shape.commit()
        page.insert_text(fitz.Point(x0 - 2.0, y + 24.0), "0")
        page.insert_text(fitz.Point(x1 - 4.0, y + 24.0), "1m")
        page.insert_text(fitz.Point(250.0, 275.0), "SCALE 1:100")
    if note:
        page.insert_textbox(fitz.Rect(100, 200, 390, 245), note, fontsize=9.0)
    return doc.tobytes()


def _chain(data: bytes, *, gate: bool):
    source = SourceVisibilityProducer(producer_method="finished-face-gate-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="finished-face-gate-doc", source_bytes=data,
        source_locator="memory://finished-face-gate.pdf", page_ids=("1",),
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id,
        page_ids=("1",), evidence_page_ids=(),
    )
    walls = compose_live_canonical_walls(source_visibility_producer=source, wall_opening_composition=wall_opening)
    rooms = compose_live_canonical_rooms(
        source_visibility_producer=source, wall_opening_composition=wall_opening,
        canonical_wall_ids_by_candidate=walls.candidate_to_canonical_wall_id,
        unresolved_wall_candidate_ids=walls.unresolved_wall_candidate_ids,
        layered_doorway_room_rings=True,
        **({"layered_finished_face_gate": True} if gate else {}),
    )
    return source, rooms


def _scope_of(rooms, room):
    return rooms.room_face_authority_binding_for(room).authority.resolve_scope(SourceRoomFaceSelector(
        document_id=room.document_id, revision_id=room.revision_id, source_sha256=room.source_sha256,
        snapshot_id=room.snapshot_id, page_id=room.page_id, decision_scope_id=room.decision_scope_id))


# ------------------------------------------------------------------------------------------ converter tokens


def test_the_gate_marks_every_admitted_ring_record_and_only_when_asked():
    data = layered_room_pdf()
    sha = hashlib.sha256(data).hexdigest()
    ring_result = build_from_pdf_bytes(data, source_sha256=sha, page_index=0)
    kw = dict(document_id="d", revision_id="r", source_sha256=sha, snapshot_id="s", page_id="1",
              decision_scope_id="wall-source:page-1")
    plain = layered_ring_room_face_scope(ring_result, **kw)
    assert not any(c.startswith(RING_FINISHED_FACE_REQUIRED_PREFIX) for c in plain.reason_codes)
    assert LAYERED_RING_FINISHED_FACE_GATE_REASON not in plain.reason_codes
    gated = layered_ring_room_face_scope(ring_result, finished_face_gate=True, **kw)
    assert LAYERED_RING_FINISHED_FACE_GATE_REASON in gated.reason_codes
    assert {c for c in gated.reason_codes if c.startswith(RING_FINISHED_FACE_REQUIRED_PREFIX)} == {
        f"{RING_FINISHED_FACE_REQUIRED_PREFIX}{r.record_id}" for r in gated.records}
    assert [r.record_id for r in gated.records] == [r.record_id for r in plain.records]  # identity unchanged
    with pytest.raises(ValueError):
        layered_ring_room_face_scope(ring_result, finished_face_gate=1, **kw)  # type: ignore[arg-type]


def test_gate_keywords_are_explicit_booleans_and_need_their_parents():
    source = SourceVisibilityProducer(producer_method="t", producer_version="1")
    with pytest.raises(ValueError):
        layered_ring_scope_overrides(source, revision_id="r", page_ids=("1",), finished_face_gate="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        compose_live_canonical_rooms(source_visibility_producer=source, wall_opening_composition=None,  # type: ignore[arg-type]
                                     layered_finished_face_gate=True)
    with pytest.raises(ValueError):
        compose_live_canonical_rooms(source_visibility_producer=source, wall_opening_composition=None,  # type: ignore[arg-type]
                                     layered_doorway_room_rings=True, layered_finished_face_gate=1)  # type: ignore[arg-type]
    for call in (collect_live_physical_net_wall_claim, _collect_live_physical_net_wall_claim):
        with pytest.raises(ValueError, match="finished face gate"):
            call("does-not-exist.pdf", layered_finished_face_gate=True)
        with pytest.raises(ValueError, match="finished face gate"):
            call("does-not-exist.pdf", layered_doorway_room_rings=True, layered_finished_face_gate="yes")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="statement pages"):
            call("does-not-exist.pdf", layered_finished_face_statement_pages=(0,))
    with pytest.raises(ValueError, match="finished face gate"):
        collect_live_physical_net_wall_claim(
            "does-not-exist.pdf", recover_additional_opening_areas=True, layered_finished_face_gate=True)
    # the wrapper refuses before it opens any source, also on the recovery path
    with pytest.raises(ValueError, match="statement pages"):
        collect_live_physical_net_wall_claim(
            "does-not-exist.pdf", recover_additional_opening_areas=True, layered_finished_face_statement_pages=(0,))


# ------------------------------------------------------------------------------------------ same-view issuer


def test_without_the_gate_the_documented_area_is_unchanged():
    source, rooms = _chain(layered_room_pdf(), gate=False)
    area = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish(layered_ring_box_selection_shadow=True)
    assert len(area.records) == 1 and area.records[0].area_evidence.normalized_value == pytest.approx(8.64)


def test_with_the_gate_the_documented_area_is_refused_for_a_ring_face():
    source, rooms = _chain(layered_room_pdf(), gate=True)
    room, = rooms.rooms
    assert f"{RING_FINISHED_FACE_REQUIRED_PREFIX}{room.source_room_face_record_id}" in _scope_of(rooms, room).reason_codes
    area = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish(layered_ring_box_selection_shadow=True)
    assert area.records == ()
    assert {c for _r, c in area.unresolved_first_failure_codes} == {"same_view_layered_ring_finished_face_not_established"}


# ------------------------------------------------------------------------------------------ room-area bridge


def _two_room_plan(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    for first, second in [((50, 50), (250, 50)), ((250, 50), (250, 150)), ((250, 150), (50, 150)),
                          ((50, 150), (50, 50)), ((150, 50), (150, 150))]:
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)
    doc.save(path)
    doc.close()


def _bridge_inputs(path: Path):
    from pb_migration_contracts import DocumentEvidence, ViewportEvidence, ViewportResolutionStatus
    from pb_migration_provider_envelope import ProviderContext
    from pb_page_scale_calibration_authority import ScaleSourceReading, ScaleSourceType, resolve_page_scale_calibration
    from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
    from pb_source_room_face_authority import build_source_room_face_authority

    source = SourceVisibilityProducer(producer_method="gate-bridge-test", producer_version="1.0")
    published = source.ingest_native_pdf_bytes(document_id="gate-bridge-doc", source_bytes=path.read_bytes(), source_locator=str(path))
    walls = PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=("1",)).authority()
    faces = build_source_room_face_authority(walls)
    selector = SourceRoomFaceSelector(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
        page_id="1", decision_scope_id="wall-source:page-1")
    return dict(
        room_face_authority=faces, selector=selector,
        context=ProviderContext(
            run_id="run-gate-bridge", workspace_id="w", project_id="p", document_id=published.revision.document_id,
            source_sha256=published.revision.source_sha256, revision_id=published.revision.revision_id,
            current_revision_id=published.revision.revision_id, selected_pages=(0,), owned_viewport_ids=("vp",),
            evidence_snapshot_id=published.snapshot.snapshot_id, owned_page_numbers=(1,),
            viewport_page_ownership=(("vp", 1),)),
        document=DocumentEvidence(
            document_id=published.revision.document_id, source_sha256=published.revision.source_sha256, page_count=1,
            page_ids=("1",), evidence_ids=(), producer="gate-bridge-test", producer_version="1.0"),
        viewport=ViewportEvidence(
            viewport_id="vp", document_id=published.revision.document_id, page_id="1", bbox=(0.0, 0.0, 300.0, 200.0),
            view_type="floor_plan", status=ViewportResolutionStatus.RESOLVED, evidence_ids=(), confidence=1.0),
        page_no=1,
        scale_calibration=resolve_page_scale_calibration(
            page_no=1, sheet_label="synthetic-plan", revision_id=published.revision.revision_id,
            readings=[ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:100", ratio=100.0, confidence=1.0)]),
    )


def test_the_bridge_withholds_exactly_the_named_rooms_and_never_adds_one(tmp_path):
    path = tmp_path / "two-rooms.pdf"
    _two_room_plan(path)
    inputs = _bridge_inputs(path)
    full = build_source_room_area_bridge(**inputs)
    assert len(full.quantities) == 2 and len(full.entities) == 2
    refs = sorted(room.room_ref for room in full.room_index.rooms())
    one = build_source_room_area_bridge(**inputs, withheld_room_refs=(refs[0],))
    assert len(one.quantities) == 1 and len(one.entities) == 2
    assert one.quantities[0].input_entity_ids != (refs[0],) and one.quantities[0] in full.quantities
    both = build_source_room_area_bridge(**inputs, withheld_room_refs=tuple(refs))
    assert both.quantities == () and len(both.entities) == 2
    unknown = build_source_room_area_bridge(**inputs, withheld_room_refs=("no-such-room",))
    assert unknown.quantities == full.quantities  # naming a room that is not there changes nothing
    for bad in ("room", b"room", (1,), [None]):
        with pytest.raises(TypeError):
            build_source_room_area_bridge(**inputs, withheld_room_refs=bad)  # type: ignore[arg-type]


# ------------------------------------------------------------------------------------------ whole claim


def _claim(tmp_path, *, gate: bool, statement_pages=None, note: str | None = None, scale_bar: bool = False):
    path = tmp_path / "gate.pdf"
    path.write_bytes(layered_room_pdf(note=note, scale_bar=scale_bar))
    return collect_live_physical_net_wall_claim(
        path, pages=(0,), topology_pages=(0,), surface_semantic_pages=(0,), layered_doorway_room_rings=True,
        **({"layered_finished_face_gate": True} if gate else {}),
        **({"layered_finished_face_statement_pages": statement_pages} if statement_pages is not None else {}),
    )


def test_whole_claim_without_the_gate_is_unchanged_and_carries_no_receipts(tmp_path):
    claim = _claim(tmp_path, gate=False)
    assert len(claim.room_area_quantity_evidence) == 1 and claim.layered_finished_face_receipts == ()
    assert [(q.family, q.status) for q in publish_live_floor_area_quantities(claim)] == [("floor_area", "firm")]


def test_whole_claim_with_the_gate_publishes_no_quantity_and_says_why(tmp_path):
    claim = _claim(tmp_path, gate=True)
    assert claim.room_area_quantity_evidence == () and publish_live_floor_area_quantities(claim) == ()
    assert claim.floor_finish_quantity_evidence == () and claim.ceiling_lining_quantity_evidence == ()
    receipt, = claim.layered_finished_face_receipts
    assert receipt.verdict == VERDICT_UNRESOLVED
    # no statement page was named and this page has no scale bar: both facts are reported, nothing is guessed
    assert {REASON_STATEMENT_UNAVAILABLE, REASON_SCALE_UNAVAILABLE} <= set(receipt.reason_codes)
    assert (receipt.takeoff_eligible, receipt.commercial_projection_allowed, receipt.metric_area_issued) == (False, False, False)
    assert {c for _r, c in claim.same_view_room_area_first_failure_codes} == {"same_view_layered_ring_finished_face_not_established"}


def test_whole_claim_reads_an_authenticated_statement_but_still_issues_nothing(tmp_path):
    claim = _claim(tmp_path, gate=True, statement_pages=(0,), note=NOTE)
    receipt, = claim.layered_finished_face_receipts
    assert REASON_STATEMENT_UNAVAILABLE not in receipt.reason_codes  # the statement was authenticated and read
    assert len(receipt.statement_text_sha256) == 1 and receipt.statement_text_sha256[0]
    # a statement is not a scale, an area or authority: the face is still noncommercial
    assert claim.room_area_quantity_evidence == () and publish_live_floor_area_quantities(claim) == ()


FRAME_141 = "THE INTERNAL WALLS TO BE 141mm PINE STUD FRAMES AND SHALL BE LINED WITH 10mm GYPROCK"
FRAME_96 = "THE INTERNAL WALLS TO BE 96mm PINE STUD FRAMES AND SHALL BE LINED WITH 10mm GYPROCK"


def test_with_a_page_scale_the_documented_area_is_still_the_unchanged_default(tmp_path):
    claim = _claim(tmp_path, gate=False, scale_bar=True)
    assert [(q.status, q.authority) for q in claim.room_area_quantity_evidence] == [("firm", "documented_dimension")]
    assert claim.physical_scale_first_failure_codes == () and claim.layered_finished_face_receipts == ()


def test_a_resolved_face_identity_alone_issues_nothing_until_a_finished_polygon_is_applied(tmp_path):
    from pb_layered_wall_face_identity_shadow import VERDICT_RESOLVED

    # the stated frame equals the drawn strip at the page scale, so every wall edge is a lined internal frame face...
    claim = _claim(tmp_path, gate=True, statement_pages=(0,), note=FRAME_141, scale_bar=True)
    receipt, = claim.layered_finished_face_receipts
    assert receipt.verdict == VERDICT_RESOLVED and receipt.reason_codes == ()
    assert {offset for _edge, offset in receipt.lined_edge_offsets_mm} == {10.0}
    # ...yet neither the documented route nor the scaled-polygon route may measure the frame-face polygon
    assert claim.room_area_quantity_evidence == () and publish_live_floor_area_quantities(claim) == ()
    assert claim.floor_finish_quantity_evidence == () and claim.ceiling_lining_quantity_evidence == ()


def test_the_scaled_polygon_route_is_withheld_for_an_unresolved_face_too(tmp_path):
    from pb_layered_wall_face_identity_shadow import CLASS_INTERNAL_THICKNESS_MISMATCH

    claim = _claim(tmp_path, gate=True, statement_pages=(0,), note=FRAME_96, scale_bar=True)
    receipt, = claim.layered_finished_face_receipts
    assert receipt.verdict == VERDICT_UNRESOLVED and CLASS_INTERNAL_THICKNESS_MISMATCH in receipt.reason_codes
    assert claim.room_area_quantity_evidence == () and publish_live_floor_area_quantities(claim) == ()


def test_documented_evidence_for_a_gated_face_never_reaches_the_issuers(tmp_path, monkeypatch):
    """Even evidence another documented producer supplies for a gated record is dropped before the bridge."""
    import pb_live_physical_net_wall_integration as integration

    path = tmp_path / "gate.pdf"
    path.write_bytes(layered_room_pdf())
    kwargs = dict(pages=(0,), topology_pages=(0,), surface_semantic_pages=(0,), layered_doorway_room_rings=True)
    seen: list[dict] = []

    def spy(*, source_face_records, canonical_rooms, evidence_by_source_record):
        seen.append({"records": [r.record_id for r in source_face_records], "evidence": dict(evidence_by_source_record)})
        return {}  # observe only: the stand-in evidence is never handed to a real issuer

    monkeypatch.setattr(integration, "_uniquely_owned_explicit_area_by_source_face", spy)
    collect_live_physical_net_wall_claim(path, **kwargs)  # learn the (deterministic) record id of the ring face
    record_ids = seen[-1]["records"]
    assert len(record_ids) == 1
    sentinel = object()
    monkeypatch.setattr(integration, "_merge_documented_room_area_evidence",
                        lambda **_kw: {record_ids[0]: sentinel})
    seen.clear()
    collect_live_physical_net_wall_claim(path, **kwargs)
    assert seen[-1]["evidence"] == {record_ids[0]: sentinel}  # without the gate the evidence is offered
    seen.clear()
    collect_live_physical_net_wall_claim(path, layered_finished_face_gate=True, **kwargs)
    assert seen[-1]["evidence"] == {}  # with the gate it is dropped before any issuer sees it


# ---- the veto must hold at each DIRECT consumer, not only through the collector (review of dcd6957)


def test_same_view_honors_the_gate_whether_box_selection_is_omitted_false_or_true():
    source, rooms = _chain(layered_room_pdf(), gate=True)
    producer = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms)
    for kwargs in ({}, {"layered_ring_box_selection_shadow": False}, {"layered_ring_box_selection_shadow": True}):
        area = producer.publish(**kwargs)
        assert area.records == (), kwargs
        assert {c for _r, c in area.unresolved_first_failure_codes} == {"same_view_layered_ring_finished_face_not_established"}
    # an ordinary ungated room keeps its default behavior under every setting
    ungated_source, ungated_rooms = _chain(layered_room_pdf(), gate=False)
    ungated = SameViewRoomAreaProducer.from_source(source=ungated_source, rooms=ungated_rooms)
    for kwargs in ({}, {"layered_ring_box_selection_shadow": True}):
        areas = [r.area_evidence.normalized_value for r in ungated.publish(**kwargs).records]
        assert areas == [pytest.approx(8.64)], kwargs


def _ring_bridge_inputs(data: bytes, *, gate: bool):
    from pb_migration_contracts import DocumentEvidence, ViewportEvidence, ViewportResolutionStatus
    from pb_migration_provider_envelope import ProviderContext
    from pb_page_scale_calibration_authority import ScaleSourceReading, ScaleSourceType, resolve_page_scale_calibration
    from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
    from pb_source_room_face_authority import build_source_room_face_authority

    source = SourceVisibilityProducer(producer_method="ring-bridge-test", producer_version="1.0")
    published = source.ingest_native_pdf_bytes(
        document_id="ring-bridge-doc", source_bytes=data, source_locator="memory://ring-bridge.pdf", page_ids=("1",))
    walls = PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=("1",)).authority()
    overrides = layered_ring_scope_overrides(
        source, revision_id=published.revision.revision_id, page_ids=("1",), finished_face_gate=gate)
    assert len(overrides) == 1
    faces = build_source_room_face_authority(walls, scope_overrides=overrides)
    selector = SourceRoomFaceSelector(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
        page_id="1", decision_scope_id="wall-source:page-1")
    return dict(
        room_face_authority=faces, selector=selector,
        context=ProviderContext(
            run_id="run-ring-bridge", workspace_id="w", project_id="p", document_id=published.revision.document_id,
            source_sha256=published.revision.source_sha256, revision_id=published.revision.revision_id,
            current_revision_id=published.revision.revision_id, selected_pages=(0,), owned_viewport_ids=("vp",),
            evidence_snapshot_id=published.snapshot.snapshot_id, owned_page_numbers=(1,),
            viewport_page_ownership=(("vp", 1),)),
        document=DocumentEvidence(
            document_id=published.revision.document_id, source_sha256=published.revision.source_sha256, page_count=1,
            page_ids=("1",), evidence_ids=(), producer="ring-bridge-test", producer_version="1.0"),
        viewport=ViewportEvidence(
            viewport_id="vp", document_id=published.revision.document_id, page_id="1", bbox=(0.0, 0.0, 400.0, 300.0),
            view_type="floor_plan", status=ViewportResolutionStatus.RESOLVED, evidence_ids=(), confidence=1.0),
        page_no=1,
        scale_calibration=resolve_page_scale_calibration(
            page_no=1, sheet_label="synthetic-plan", revision_id=published.revision.revision_id,
            readings=[ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:100", ratio=100.0, confidence=1.0)]),
    )


def test_the_bridge_withholds_a_gated_face_by_itself_without_any_caller_list():
    data = layered_room_pdf()
    open_inputs = _ring_bridge_inputs(data, gate=False)
    open_result = build_source_room_area_bridge(**open_inputs)
    assert [(q.status, q.abstained) for q in open_result.quantities] == [("firm", False)]  # the ungated default
    gated_inputs = _ring_bridge_inputs(data, gate=True)
    gated = build_source_room_area_bridge(**gated_inputs)  # no withheld_room_refs passed
    assert gated.quantities == () and len(gated.entities) == 1
    # a caller-supplied documented area for the gated face is dropped before it reaches the document or issuer
    face_id = gated_inputs["room_face_authority"].resolve_scope(gated_inputs["selector"]).records[0].face_id
    from pb_migration_contracts import EvidenceAtom

    documented = EvidenceAtom(
        evidence_id="documented-area-for-a-gated-face", document_id=gated_inputs["document"].document_id, page_id="1",
        kind="explicit_room_area", method="test", normalized_value=8.64, unit="m2")
    with_explicit = build_source_room_area_bridge(**gated_inputs, explicit_area_evidence_by_room_id={face_id: documented})
    assert with_explicit.quantities == ()
    assert "documented-area-for-a-gated-face" not in with_explicit.document.evidence_ids
    assert with_explicit.document.evidence_ids == gated.document.evidence_ids
    # caller-requested removals still apply on top of the scope's own veto and never undo it
    assert build_source_room_area_bridge(**gated_inputs, withheld_room_refs=(face_id,)).quantities == ()
    assert build_source_room_area_bridge(**gated_inputs, withheld_room_refs=("no-such-room",)).quantities == ()
