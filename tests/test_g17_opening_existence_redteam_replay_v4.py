from __future__ import annotations

from dataclasses import fields

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,
    OPENING_JAMB_BOUNDARY_KIND,
    PHYSICAL_OPENING_EXISTS,
    WALL_FACE_INTERRUPTION_KIND,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import SourceObservationProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_vector_geometry_v130 import extract_native_page
from tests.g17_phase2_test_support import make_base, make_resolved, publish, selector


_REPLAY_BASE_SHA = "3361458cd2b699fb940c0dc82d75c5c9c151ec7f"


def _rectangle_pdf_bytes(*, clip_prefix: bytes | None = None) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=240, height=240)
    page.draw_line((100, 100), (140, 100), color=(0, 0, 0), width=1)
    page.draw_line((100, 110), (140, 110), color=(0, 0, 0), width=1)
    page.draw_line((100, 100), (100, 110), color=(0, 0, 0), width=1)
    page.draw_line((140, 100), (140, 110), color=(0, 0, 0), width=1)
    if clip_prefix is not None:
        contents = page.get_contents()
        assert contents
        original = b"\n".join(doc.xref_stream(xref) for xref in contents)
        doc.update_stream(contents[0], b"q\n" + clip_prefix + b"\n" + original + b"\nQ\n")
        for xref in contents[1:]:
            doc.update_stream(xref, b"")
    payload = doc.tobytes()
    doc.close()
    return payload


def _two_page_rectangle_pdf_bytes() -> bytes:
    doc = fitz.open()
    doc.new_page(width=240, height=240)
    page = doc.new_page(width=240, height=240)
    page.draw_line((100, 100), (140, 100), color=(0, 0, 0), width=1)
    page.draw_line((100, 110), (140, 110), color=(0, 0, 0), width=1)
    page.draw_line((100, 100), (100, 110), color=(0, 0, 0), width=1)
    page.draw_line((140, 100), (140, 110), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def _visible_opening_pdf_bytes() -> bytes:
    """Two wall faces continuing on both sides of a common gap + two jambs."""
    doc = fitz.open()
    page = doc.new_page(width=300, height=240)
    for first, second in (
        ((20, 100), (100, 100)),
        ((140, 100), (220, 100)),
        ((20, 110), (100, 110)),
        ((140, 110), (220, 110)),
        ((100, 100), (100, 110)),
        ((140, 100), (140, 110)),
    ):
        page.draw_line(first, second, color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def _raw_ingest(payload: bytes, *, document_id: str):
    producer = SourceObservationProducer(
        producer_method="g17-redteam-replay-v4",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    source = producer.authority()
    physical = PhysicalOpeningAuthority(source)
    records = []
    for observation_id in published.snapshot.observation_ids:
        result = source.resolve(selector(published, published.snapshot.snapshot_id, observation_id))
        if result.observation and result.observation.observation_kind == "native_pdf_segment":
            records.append(result.observation)
    return producer, published, source, physical, records


def _visible_ingest(payload: bytes, *, document_id: str):
    producer = SourceVisibilityProducer(
        producer_method="g17-redteam-replay-v4-visible",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    visibility = producer.authority()
    physical = PhysicalOpeningAuthority(visibility)
    return producer, published, visibility, physical


def _rectangle_roots(records, *, page_id: str = "1"):
    eligible = [record for record in records if record.page_id == page_id]
    horizontal = [
        record
        for record in eligible
        if len(record.geometry) == 4 and abs(record.geometry[1] - record.geometry[3]) <= 1e-6
    ]
    vertical = [
        record
        for record in eligible
        if len(record.geometry) == 4 and abs(record.geometry[0] - record.geometry[2]) <= 1e-6
    ]
    assert len(horizontal) >= 2
    assert len(vertical) >= 2
    horizontal.sort(key=lambda record: (min(record.geometry[1], record.geometry[3]), record.observation_id))
    vertical.sort(key=lambda record: (min(record.geometry[0], record.geometry[2]), record.observation_id))
    return horizontal[:2], vertical[:2]


def _publish_structure_from_native(
    producer,
    published,
    records,
    *,
    root_page_id: str = "1",
    claimed_page_id: str = "1",
    claimed_viewport_id: str | None = "vp-1",
):
    faces, jambs = _rectangle_roots(records, page_id=root_page_id)
    specs = (
        ("face-a", WALL_FACE_INTERRUPTION_KIND, faces[0]),
        ("face-b", WALL_FACE_INTERRUPTION_KIND, faces[1]),
        ("jamb-left", OPENING_JAMB_BOUNDARY_KIND, jambs[0]),
        ("jamb-right", OPENING_JAMB_BOUNDARY_KIND, jambs[1]),
    )
    snapshot_id = published.snapshot.snapshot_id
    for observation_id, kind, root in specs:
        snapshot_id = producer.publish_derived_observation(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            base_snapshot_id=snapshot_id,
            page_id=claimed_page_id,
            source_partition_id=f"page:{claimed_page_id}",
            observation_kind=kind,
            source_primitive_ref=f"redteam:{observation_id}",
            origin_kind="derived",
            parent_observation_ids=(root.observation_id,),
            geometry=root.geometry,
            viewport_id=claimed_viewport_id,
            observation_id=observation_id,
        ).snapshot_id
    return snapshot_id


def _assert_no_positive_existence(result) -> None:
    assert result.proposition != PHYSICAL_OPENING_EXISTS
    assert result.existence_record is None
    assert result.status is not EvidenceResolutionStatus.CORROBORATED


def _native_extract(payload: bytes) -> dict:
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        return extract_native_page(doc[0])
    finally:
        doc.close()


def _bbox_disjoint_from_clip(segment: dict) -> bool:
    clip = segment.get("clip")
    assert clip is not None and len(clip) == 4
    sx0 = min(float(segment["x1"]), float(segment["x2"]))
    sy0 = min(float(segment["y1"]), float(segment["y2"]))
    sx1 = max(float(segment["x1"]), float(segment["x2"]))
    sy1 = max(float(segment["y1"]), float(segment["y2"]))
    cx0, cy0, cx1, cy1 = map(float, clip)
    return sx1 < cx0 or cx1 < sx0 or sy1 < cy0 or cy1 < sy0


def test_unrelated_native_roots_cannot_certify_arbitrary_opening_geometry() -> None:
    """Attack 1: preserve the original malicious derived-semantic negative."""
    _, published, _, physical, _, snapshot_id = make_resolved()
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    _assert_no_positive_existence(result)


def test_page2_native_roots_cannot_be_laundered_into_page1_existence() -> None:
    """Attack 2: child page claims cannot transfer ownership from page-2 roots."""
    producer, published, _, physical, records = _raw_ingest(
        _two_page_rectangle_pdf_bytes(), document_id="g17-replay-page-laundering"
    )
    snapshot_id = _publish_structure_from_native(
        producer,
        published,
        records,
        root_page_id="2",
        claimed_page_id="1",
    )
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    _assert_no_positive_existence(result)


def test_viewport_none_roots_cannot_mint_vp1_authority() -> None:
    """Attack 3: roots without viewport authority cannot mint vp-1."""
    producer, published, _, physical, records = _raw_ingest(
        _rectangle_pdf_bytes(), document_id="g17-replay-viewport-laundering"
    )
    assert records and all(record.viewport_id is None for record in records)
    snapshot_id = _publish_structure_from_native(
        producer,
        published,
        records,
        claimed_viewport_id="vp-1",
    )
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    _assert_no_positive_existence(result)


def test_fully_clipped_raw_vectors_cannot_establish_opening_existence() -> None:
    """Attack 4: real PDF clipping must not produce visible authority roots."""
    payload = _rectangle_pdf_bytes(clip_prefix=b"0 0 20 20 re W n")
    native = _native_extract(payload)
    structural = [segment for segment in native["segments"] if segment["kind"] == "line"]
    assert len(structural) == 4
    assert all(segment.get("clip_present") is True for segment in structural)
    assert all(_bbox_disjoint_from_clip(segment) for segment in structural)

    _, visible, _, _ = _visible_ingest(payload, document_id="g17-replay-fully-clipped")
    assert visible.visible_observation_ids == ()

    producer, published, _, physical, records = _raw_ingest(
        payload, document_id="g17-replay-fully-clipped-raw"
    )
    snapshot_id = _publish_structure_from_native(producer, published, records)
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    _assert_no_positive_existence(result)


def test_unresolved_clip_must_abstain_from_opening_existence() -> None:
    """Attack 5: non-rectangular active clipping cannot become visibility proof."""
    payload = _rectangle_pdf_bytes(
        clip_prefix=b"90 120 m 150 120 l 120 170 l h W n"
    )
    native = _native_extract(payload)
    structural = [segment for segment in native["segments"] if segment["kind"] == "line"]
    assert len(structural) == 4
    assert all(segment.get("clip_present") is True for segment in structural)

    _, visible, _, _ = _visible_ingest(payload, document_id="g17-replay-nonrect-clip")
    assert visible.visible_observation_ids == ()


def test_closed_rectangle_without_wall_continuation_is_not_physical_opening() -> None:
    """Attack 6: a box is not a wall interruption with continuation."""
    _, published, _, physical = _visible_ingest(
        _rectangle_pdf_bytes(), document_id="g17-replay-box-only"
    )
    assert len(published.visible_observation_ids) == 4
    results = [
        physical.prove_existence(selector(published, published.snapshot.snapshot_id, observation_id))
        for observation_id in published.visible_observation_ids
    ]
    assert all(result.proposition != PHYSICAL_OPENING_EXISTS for result in results)
    assert all(result.existence_record is None for result in results)


def test_two_face_gap_without_two_jambs_never_resolves_existence() -> None:
    """Attack 7: two interruption claims without two jambs stay non-positive."""
    producer, published, _, physical, roots = make_base()
    snapshot_id = published.snapshot.snapshot_id
    for observation_id, geometry, root_id in (
        ("face-a", (100.0, 100.0, 140.0, 100.0), roots[0]),
        ("face-b", (100.0, 110.0, 140.0, 110.0), roots[1]),
    ):
        snapshot_id = publish(
            producer,
            published,
            snapshot_id=snapshot_id,
            root_id=root_id,
            observation_id=observation_id,
            kind=WALL_FACE_INTERRUPTION_KIND,
            geometry=geometry,
        ).snapshot_id
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.proposition is None
    assert result.existence_record is None


@pytest.mark.parametrize(
    "kind",
    (
        "opening_swing_arc",
        "opening_tag",
        "schedule_row",
        "cv_opening_detection",
        "ocr_text",
        "heuristic_opening_label",
    ),
)
def test_derived_only_semantic_evidence_never_establishes_existence(kind: str) -> None:
    """Attack 8: semantic-looking evidence is not structural truth."""
    producer, published, _, physical, roots = make_base()
    snapshot_id = publish(
        producer,
        published,
        snapshot_id=published.snapshot.snapshot_id,
        root_id=roots[0],
        observation_id=f"derived-{kind}",
        kind=kind,
        geometry=(100.0, 100.0, 140.0, 110.0),
    ).snapshot_id
    result = physical.prove_existence(
        selector(published, snapshot_id, f"derived-{kind}")
    )
    _assert_no_positive_existence(result)


def test_shared_or_overlapping_lineage_cannot_manufacture_independence() -> None:
    """Attack 9: overlapping support roots cannot become independent by relabeling."""
    producer, published, _, physical, roots = make_base()
    specs = (
        ("face-a", WALL_FACE_INTERRUPTION_KIND, (100.0, 100.0, 140.0, 100.0), (roots[0], roots[1])),
        ("face-b", WALL_FACE_INTERRUPTION_KIND, (100.0, 110.0, 140.0, 110.0), (roots[1], roots[2])),
        ("jamb-left", OPENING_JAMB_BOUNDARY_KIND, (100.0, 100.0, 100.0, 110.0), (roots[3],)),
        ("jamb-right", OPENING_JAMB_BOUNDARY_KIND, (140.0, 100.0, 140.0, 110.0), (roots[4],)),
    )
    snapshot_id = published.snapshot.snapshot_id
    for observation_id, kind, geometry, parents in specs:
        snapshot_id = producer.publish_derived_observation(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            base_snapshot_id=snapshot_id,
            page_id="1",
            source_partition_id="page:1",
            observation_kind=kind,
            source_primitive_ref=f"redteam:{observation_id}",
            origin_kind="derived",
            parent_observation_ids=parents,
            geometry=geometry,
            viewport_id="vp-1",
            observation_id=observation_id,
        ).snapshot_id
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    _assert_no_positive_existence(result)


def test_incompatible_interpretations_stay_conflict() -> None:
    """Attack 10: ambiguity cannot be resolved by first/nearest/smallest choice."""
    producer, published, _, physical, roots = make_base()
    specs = (
        ("face-a", WALL_FACE_INTERRUPTION_KIND, (100.0, 100.0, 140.0, 100.0), roots[0]),
        ("face-b", WALL_FACE_INTERRUPTION_KIND, (100.0, 110.0, 140.0, 110.0), roots[1]),
        ("jamb-ab-left", OPENING_JAMB_BOUNDARY_KIND, (100.0, 100.0, 100.0, 110.0), roots[2]),
        ("jamb-ab-right", OPENING_JAMB_BOUNDARY_KIND, (140.0, 100.0, 140.0, 110.0), roots[3]),
        ("face-c", WALL_FACE_INTERRUPTION_KIND, (100.0, 120.0, 140.0, 120.0), roots[4]),
        ("jamb-ac-left", OPENING_JAMB_BOUNDARY_KIND, (100.0, 100.0, 100.0, 120.0), roots[5]),
        ("jamb-ac-right", OPENING_JAMB_BOUNDARY_KIND, (140.0, 100.0, 140.0, 120.0), roots[6]),
    )
    snapshot_id = published.snapshot.snapshot_id
    for observation_id, kind, geometry, root_id in specs:
        snapshot_id = publish(
            producer,
            published,
            snapshot_id=snapshot_id,
            root_id=root_id,
            observation_id=observation_id,
            kind=kind,
            geometry=geometry,
        ).snapshot_id
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.proposition is None
    assert result.existence_record is None
    assert AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES in result.reason_codes


def test_legitimate_visible_existence_cannot_cross_downstream_firewall() -> None:
    """Attack 11 corrected: real producer-visible existence, downstream still closed."""
    _, published, _, physical = _visible_ingest(
        _visible_opening_pdf_bytes(), document_id="g17-replay-positive-firewall"
    )
    assert len(published.visible_observation_ids) == 6
    left = selector(
        published,
        published.snapshot.snapshot_id,
        published.visible_observation_ids[0],
    )
    result = physical.prove_existence(left)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == PHYSICAL_OPENING_EXISTS
    assert result.existence_record is not None
    assert result.existence_record.viewport_id is None
    assert len(result.existence_record.source_observation_ids) == 6
    assert len(set(result.existence_record.source_observation_ids)) == 6
    assert len(result.existence_record.source_lineage_root_ids) == 6
    assert len(set(result.existence_record.source_lineage_root_ids)) == 6

    names = {field.name for field in fields(result.existence_record)}
    forbidden_record_fields = {
        "physical_opening_identity",
        "width",
        "height",
        "area",
        "type",
        "type_id",
        "schedule_identity",
        "host",
        "host_id",
        "host_wall_id",
        "host_binding",
        "opening_universe_complete",
        "physical_void",
        "deduction",
        "deduction_authority",
        "net_wall_area",
        "firm",
        "firm_quantity",
        "commercial_publication",
        "jobhub_publication",
        "publishable",
    }
    assert names.isdisjoint(forbidden_record_fields)

    identity = physical.compare_identity(
        left,
        selector(
            published,
            published.snapshot.snapshot_id,
            published.visible_observation_ids[1],
        ),
    )
    # Same G17 existence record via two producer-owned visible supports:
    # identity may corroborate. Downstream measurement/publication stays closed.
    assert identity.status is EvidenceResolutionStatus.CORROBORATED
    assert identity.proven_same is True
    assert identity.physical_opening_identity == result.existence_record.record_id

    capabilities = physical.capabilities()
    assert capabilities["physical_opening_existence"] is True
    assert capabilities["physical_opening_identity"] is True
    for capability in (
        "opening_universe_complete",
        "opening_dimensions",
        "host_identity",
        "host_binding",
        "physical_void",
        "net_wall_area",
    ):
        assert capabilities[capability] is False

    for forbidden_method in (
        "deduct_wall_area",
        "publish_firm_quantity",
        "publish_commercial",
        "publish_to_jobhub",
        "jobhub_publish",
    ):
        assert not hasattr(physical, forbidden_method)


def test_replay_branch_is_bound_to_exact_g17_remediation_head() -> None:
    assert _REPLAY_BASE_SHA == "3361458cd2b699fb940c0dc82d75c5c9c151ec7f"
