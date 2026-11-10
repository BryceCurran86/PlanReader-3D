"""Default-off corner-leg existence and owner CRNR STACK pairing of both leaves."""
from __future__ import annotations

from dataclasses import replace

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_opening_label_dimension_authority import (
    OpeningLabelDimensionEvidence,
    OpeningLabelDimensionProducer,
    _TrustedTextLine,
    _gap_span_for_opening,
    _label_matches_gap,
    parse_opening_label_dimensions,
)
from pb_raster_corner_framed_opening_shadow import (
    detect_raster_corner_framed_openings_shadow,
)
from pb_opening_label_semantic_authority import (
    OpeningLabelSemanticProducer,
    _explicit_word_kind,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_CORNER_FRAMED_OPENING_LEG,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from test_raster_corner_framed_opening_shadow import (
    ROOT,
    _existence_records,
    _pdf,
    _png,
    _selector,
    _sheet,
)


def _prepare(*, corner_shadow: bool, **sheet):
    producer = SourceVisibilityProducer(
        producer_method="raster-corner-optin-contract",
        producer_version="1",
        raster_corner_framed_opening_shadow=corner_shadow,
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="corner-optin-contract",
        source_bytes=_pdf(_sheet(**sheet)),
        source_locator="memory://raster-corner-optin-contract.pdf",
        page_ids=("1",),
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=("1",))
    return producer, published


def test_default_off_issues_no_corner_existence() -> None:
    producer, published = _prepare(corner_shadow=False)
    assert _existence_records(producer, published) == ()


def test_opt_in_issues_one_existence_record_per_leg() -> None:
    producer, published = _prepare(corner_shadow=True)
    records = _existence_records(producer, published)
    assert len(records) == 2
    assert {record.structural_pattern for record in records} == {RASTER_CORNER_FRAMED_OPENING_LEG}
    assert all(record.proposition == PHYSICAL_OPENING_EXISTS for record in records)
    assert all(record.aperture_bbox_pt is not None for record in records)
    supports = [frozenset(record.source_observation_ids) for record in records]
    assert supports[0].isdisjoint(supports[1])
    boxes = [record.aperture_bbox_pt for record in records]
    assert boxes[0] != boxes[1]


def test_opt_in_does_not_change_an_unrelated_straight_opening() -> None:
    off_producer, off_published = _prepare(corner_shadow=False, unrelated_opening=True)
    on_producer, on_published = _prepare(corner_shadow=True, unrelated_opening=True)
    off_records = _existence_records(off_producer, off_published)
    on_records = _existence_records(on_producer, on_published)
    assert len(off_records) == 1
    assert off_records[0].structural_pattern == RASTER_FRAMED_WALL_BAND_INTERRUPTION
    framed = [record for record in on_records
              if record.structural_pattern == RASTER_FRAMED_WALL_BAND_INTERRUPTION]
    corner = [record for record in on_records
              if record.structural_pattern == RASTER_CORNER_FRAMED_OPENING_LEG]
    assert len(framed) == 1
    assert len(corner) == 2
    assert framed[0].aperture_bbox_pt == off_records[0].aperture_bbox_pt


def test_opt_in_look_alikes_issue_no_corner_existence() -> None:
    for sheet in (
        dict(frames=0),
        dict(frames=1),
        dict(face_lines=True),
        dict(solid_corner=True),
        dict(second_corner_post=True),
    ):
        producer, published = _prepare(corner_shadow=True, **sheet)
        assert not [
            record for record in _existence_records(producer, published)
            if record.structural_pattern == RASTER_CORNER_FRAMED_OPENING_LEG
        ]

    # A collinear partner is a straight framed opening, not a corner.
    producer, published = _prepare(corner_shadow=True, straight_partner=True)
    records = _existence_records(producer, published)
    assert not [
        record for record in records
        if record.structural_pattern == RASTER_CORNER_FRAMED_OPENING_LEG
    ]


def test_crnr_stack_is_the_existing_stacker_door_phrase_not_a_raw_millimetre() -> None:
    parsed = parse_opening_label_dimensions("2124 CRNR STACK")
    assert parsed is not None
    assert parsed.dimension_tokens == ("21", "24")
    assert parsed.compact_hundreds_present is True
    assert parsed.dimension_values_mm == ()
    assert _explicit_word_kind("2124 CRNR STACK") == ("door", False)
    assert _explicit_word_kind("STACK OF BRICKS") == (None, False)


def _labelled_pdf(
    *labels: tuple[tuple[float, float], str],
    unrelated_opening: bool = False,
) -> bytes:
    gray = _sheet(unrelated_opening=unrelated_opening)
    doc = fitz.open()
    try:
        page = doc.new_page(width=gray.shape[1] / 2.0, height=gray.shape[0] / 2.0)
        page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
        for (x, y), text in labels:
            page.insert_text(fitz.Point(x, y), text, fontsize=7.0)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _prepare_labelled(
    *labels: tuple[tuple[float, float], str],
    unrelated_opening: bool = False,
):
    producer = SourceVisibilityProducer(
        producer_method="raster-corner-optin-contract",
        producer_version="1",
        raster_corner_framed_opening_shadow=True,
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="corner-optin-contract",
        source_bytes=_labelled_pdf(*labels, unrelated_opening=unrelated_opening),
        source_locator="memory://raster-corner-optin-labelled.pdf",
        page_ids=("1",),
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=("1",))
    return producer, published


def _existence_pairs(producer, published):
    authority = producer.physical_opening_authority()
    found = {}
    for observation_id in published.raster_opening_primitive_observation_ids:
        selector = _selector(published, observation_id)
        result = authority.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            found[result.existence_record.record_id] = (selector, result.existence_record)
    return tuple(found[key] for key in sorted(found))


def _corner_pairs(producer, published):
    return tuple(
        (selector, record)
        for selector, record in _existence_pairs(producer, published)
        if record.structural_pattern == RASTER_CORNER_FRAMED_OPENING_LEG
    )


def test_opt_in_pairs_the_two_nominated_corner_leg_apertures() -> None:
    producer, published = _prepare(corner_shadow=True)
    records = _existence_records(producer, published)
    assert len(records) == 2
    authority = producer.physical_opening_authority()
    first, second = records
    assert authority.raster_corner_leg_sibling_aperture(first) == second.aperture_bbox_pt
    assert authority.raster_corner_leg_sibling_aperture(second) == first.aperture_bbox_pt


def test_opt_in_does_not_pair_an_unrelated_straight_opening_as_a_sibling() -> None:
    producer, published = _prepare(corner_shadow=True, unrelated_opening=True)
    authority = producer.physical_opening_authority()
    framed = [
        record for record in _existence_records(producer, published)
        if record.structural_pattern == RASTER_FRAMED_WALL_BAND_INTERRUPTION
    ]
    assert len(framed) == 1
    assert authority.raster_corner_leg_sibling_aperture(framed[0]) is None


def test_one_crnr_stack_callout_names_both_meeting_leaves() -> None:
    producer, published = _prepare_labelled(
        ((130.0, 96.0), "2124 CRNR STACK"),
        ((110.0, 168.0), "2142 BIFOLD"),
        unrelated_opening=True,
    )
    pairs = _corner_pairs(producer, published)
    assert len(pairs) == 2
    boxes = [record.aperture_bbox_pt for _selector, record in pairs]
    assert boxes[0] != boxes[1]

    semantic_producer = OpeningLabelSemanticProducer.from_source_visibility_producer(producer)
    dimension_producer = OpeningLabelDimensionProducer.from_source_visibility_producer(producer)
    owned = []
    for selector, record in pairs:
        semantic = semantic_producer.publish_scope(selector)
        assert semantic.status is EvidenceResolutionStatus.CORROBORATED
        assert semantic.evidence is not None
        assert semantic.evidence.semantic_kind == "door"
        assert any("CRNR STACK" in text.upper() for text in semantic.evidence.raw_texts)
        assert all("2142" not in text for text in semantic.evidence.raw_texts)

        dimension = dimension_producer.publish_scope(selector)
        assert dimension.status is EvidenceResolutionStatus.CORROBORATED
        assert dimension.evidence is not None
        assert dimension.evidence.semantic_kind == "door"
        assert dimension.evidence.dimension_values_mm == (2100.0, 2400.0)
        # Compact HHWW product on the label evidence only. Not host/frame area.
        assert type(dimension.evidence) is OpeningLabelDimensionEvidence
        assert not isinstance(dimension.evidence, QuantityEvidence)
        owned.append((record, dimension.evidence.raw_text, dimension.evidence.area_m2))

    assert all("2124" in text for _record, text, _area in owned)

    # The printed callout sits on one leaf. Sibling ownership, not nearest
    # label, is what names the other leaf.
    horizontal = max(pairs, key=lambda item: item[1].aperture_bbox_pt[2] - item[1].aperture_bbox_pt[0])
    vertical = min(pairs, key=lambda item: item[1].aperture_bbox_pt[2] - item[1].aperture_bbox_pt[0])
    label = _TrustedTextLine(
        observation_ids=("synthetic",),
        text="2124 CRNR STACK",
        bbox=(130.0, 89.0, 210.0, 96.0),
    )
    assert _label_matches_gap(label, _gap_span_for_opening(producer, horizontal[1]))
    assert not _label_matches_gap(label, _gap_span_for_opening(producer, vertical[1]))


def test_sibling_lookup_rejects_foreign_source_scope_with_the_same_bbox() -> None:
    producer, published = _prepare(corner_shadow=True)
    records = _existence_records(producer, published)
    assert len(records) == 2
    authority = producer.physical_opening_authority()
    first, second = records
    assert authority.raster_corner_leg_sibling_aperture(first) == second.aperture_bbox_pt
    for foreign in (
        replace(first, document_id="foreign-document"),
        replace(first, revision_id="foreign-revision"),
        replace(first, source_sha256="0" * 64),
        replace(first, snapshot_id="foreign-snapshot"),
        replace(first, page_id="99"),
    ):
        assert authority.raster_corner_leg_sibling_aperture(foreign) is None


def _two_page_pdf(first, second) -> bytes:
    doc = fitz.open()
    try:
        for gray in (first, second):
            page = doc.new_page(width=gray.shape[1] / 2.0, height=gray.shape[0] / 2.0)
            page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _prepare_two_page(payload: bytes, page_ids=("1", "2")):
    producer = SourceVisibilityProducer(
        producer_method="raster-corner-optin-contract",
        producer_version="1",
        raster_corner_framed_opening_shadow=True,
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="corner-optin-two-page",
        source_bytes=payload,
        source_locator="memory://raster-corner-optin-two-page.pdf",
        page_ids=page_ids,
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=page_ids)
    return producer, published


def _primitive_ids_by_page(producer, published):
    visibility = producer.authority()
    grouped: dict[str, list[str]] = {}
    for observation_id in published.raster_opening_primitive_observation_ids:
        resolved = visibility.resolve_raster_opening_primitive(
            _selector(published, observation_id))
        observation = resolved.observation
        if observation is None:
            continue
        grouped.setdefault(str(observation.page_id), []).append(observation_id)
    return grouped


def _prove_ids(producer, published, observation_ids):
    authority = producer.physical_opening_authority()
    found = {}
    for observation_id in observation_ids:
        result = authority.prove_existence(_selector(published, observation_id))
        record = result.existence_record
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and record is not None
            and record.structural_pattern == RASTER_CORNER_FRAMED_OPENING_LEG
        ):
            found[record.record_id] = record
    return tuple(found[key] for key in sorted(found))


def test_two_page_same_bbox_collision_does_not_steal_a_sibling() -> None:
    payload = _two_page_pdf(_sheet(), _sheet(v_band_high=80))
    for page_order in (("2", "1"), ("1", "2")):
        producer, published = _prepare_two_page(payload)
        grouped = _primitive_ids_by_page(producer, published)
        ordered_ids = [oid for page_id in page_order for oid in grouped.get(page_id, ())]
        records = _prove_ids(producer, published, ordered_ids)
        by_page = {}
        for record in records:
            by_page.setdefault(record.page_id, []).append(record)
        assert set(by_page) == {"1", "2"}
        assert all(len(legs) == 2 for legs in by_page.values())
        authority = producer.physical_opening_authority()
        page1_vertical = min(
            by_page["1"],
            key=lambda record: record.aperture_bbox_pt[2] - record.aperture_bbox_pt[0],
        )
        page2_vertical = min(
            by_page["2"],
            key=lambda record: record.aperture_bbox_pt[2] - record.aperture_bbox_pt[0],
        )
        assert page1_vertical.aperture_bbox_pt != page2_vertical.aperture_bbox_pt
        for page_id, legs in by_page.items():
            first, second = legs
            assert authority.raster_corner_leg_sibling_aperture(first) == second.aperture_bbox_pt
            assert authority.raster_corner_leg_sibling_aperture(second) == first.aperture_bbox_pt
            foreign = replace(first, page_id="1" if page_id == "2" else "2")
            assert authority.raster_corner_leg_sibling_aperture(foreign) is None


def test_opt_in_label_product_stays_out_of_firm_customer_and_sealed_quantities() -> None:
    producer, published = _prepare_labelled(((130.0, 96.0), "2124 CRNR STACK"))
    pairs = _corner_pairs(producer, published)
    assert len(pairs) == 2
    dimension_producer = OpeningLabelDimensionProducer.from_source_visibility_producer(producer)
    shadow = detect_raster_corner_framed_openings_shadow(
        producer, revision_id=published.revision.revision_id, page_id="1")
    assert shadow.takeoff_eligible is False
    assert shadow.candidates
    assert all(
        candidate.takeoff_eligible is False
        and candidate.deduction_authority is False
        and candidate.physical_opening_authority is False
        for candidate in shadow.candidates
    )
    for selector, _record in pairs:
        dimension = dimension_producer.publish_scope(selector)
        assert dimension.status is EvidenceResolutionStatus.CORROBORATED
        assert type(dimension.evidence) is OpeningLabelDimensionEvidence
        assert not isinstance(dimension.evidence, QuantityEvidence)
        assert getattr(dimension.evidence, "status", None) != "FIRM"
        assert getattr(dimension.evidence, "authority", None) not in {"FIRM", "firm"}
    blocked = (
        ROOT / "pb_live_physical_net_wall_integration.py",
        ROOT / "pb_live_append_only_opening_area_composition.py",
        ROOT / "pb_live_physical_opening_void_composition.py",
        ROOT / "tools" / "run_gpt3_lot16_original_sealed_score_input.py",
        ROOT / "tools" / "run_source_closed_project_handoff.py",
    )
    for path in blocked:
        text = path.read_text(encoding="utf-8")
        assert "raster_corner_framed_opening_shadow" not in text
        assert "RASTER_CORNER_FRAMED_OPENING_LEG" not in text


def _horizontal_vertical(pairs):
    horizontal = max(pairs, key=lambda item: item[1].aperture_bbox_pt[2] - item[1].aperture_bbox_pt[0])
    vertical = min(pairs, key=lambda item: item[1].aperture_bbox_pt[2] - item[1].aperture_bbox_pt[0])
    return horizontal, vertical


def test_plain_door_callout_on_one_leaf_does_not_name_the_sibling() -> None:
    producer, published = _prepare_labelled(((130.0, 96.0), "2118 DOOR"))
    pairs = _corner_pairs(producer, published)
    assert len(pairs) == 2
    horizontal, vertical = _horizontal_vertical(pairs)
    semantic_producer = OpeningLabelSemanticProducer.from_source_visibility_producer(producer)
    dimension_producer = OpeningLabelDimensionProducer.from_source_visibility_producer(producer)

    h_semantic = semantic_producer.publish_scope(horizontal[0])
    h_dimension = dimension_producer.publish_scope(horizontal[0])
    assert h_semantic.status is EvidenceResolutionStatus.CORROBORATED
    assert h_semantic.evidence is not None
    assert h_semantic.evidence.semantic_kind == "door"
    assert h_dimension.status is EvidenceResolutionStatus.CORROBORATED
    assert h_dimension.evidence is not None
    assert h_dimension.evidence.dimension_values_mm == (2100.0, 1800.0)

    v_semantic = semantic_producer.publish_scope(vertical[0])
    v_dimension = dimension_producer.publish_scope(vertical[0])
    assert v_semantic.status is EvidenceResolutionStatus.ABSTAINED
    assert v_dimension.status is EvidenceResolutionStatus.ABSTAINED


def test_direct_sibling_door_callout_conflicts_instead_of_inheriting_crnr_stack() -> None:
    producer, published = _prepare_labelled(
        ((130.0, 96.0), "2124 CRNR STACK"),
        ((8.0, 62.0), "2118 DOOR"),
    )
    pairs = _corner_pairs(producer, published)
    assert len(pairs) == 2
    horizontal, vertical = _horizontal_vertical(pairs)
    semantic_producer = OpeningLabelSemanticProducer.from_source_visibility_producer(producer)
    dimension_producer = OpeningLabelDimensionProducer.from_source_visibility_producer(producer)

    h_semantic = semantic_producer.publish_scope(horizontal[0])
    h_dimension = dimension_producer.publish_scope(horizontal[0])
    assert h_semantic.status is EvidenceResolutionStatus.CORROBORATED
    assert h_dimension.status is EvidenceResolutionStatus.CORROBORATED
    assert h_dimension.evidence is not None
    assert h_dimension.evidence.dimension_values_mm == (2100.0, 2400.0)
    assert "2118" not in h_dimension.evidence.raw_text

    v_dimension = dimension_producer.publish_scope(vertical[0])
    assert v_dimension.status is EvidenceResolutionStatus.CONFLICT
