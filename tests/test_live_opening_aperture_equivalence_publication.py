"""Default-off publication consumer for one-aperture opening-area classes."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from pb_live_opening_aperture_equivalence_publication import (
    apply_aperture_equivalence_publication,
)
from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_opening_aperture_equivalence_shadow import ApertureRecord, PairVerdict
from types import MappingProxyType


def rec(rid, figure=("lbl-a",), area=1.5, host="wall-1", scope="doc|rev|snap|p3", receipts=None):
    return ApertureRecord(
        rid,
        scope,
        tuple(figure),
        area,
        host,
        tuple(receipts if receipts is not None else (f"r-{rid}",)),
    )


def verdict(a, b, v):
    return PairVerdict(a, b, v)


def qty(opening_id, value=1.5, evidence=None):
    return QuantityEvidence(
        quantity_id=f"q-{opening_id}",
        family="opening_area",
        semantic_key=f"window_area:{opening_id}",
        value=value,
        unit="m2",
        input_entity_ids=(opening_id,),
        formula="authenticated figured opening-label dimension product",
        formula_version="1.0.0",
        evidence_ids=tuple(evidence if evidence is not None else (f"e-{opening_id}",)),
        authority="pb_opening_label_dimension_authority.figured_opening_label_area",
        status="corroborated",
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        metadata={
            "canonical_opening_id": opening_id,
            "area_basis": "figured_opening_label",
        },
    )


def test_default_off_returns_the_same_quantities():
    quantities = (qty("a"), qty("b"))
    assert apply_aperture_equivalence_publication(quantities, (), ()) is quantities
    assert apply_aperture_equivalence_publication(
        quantities, (rec("a"), rec("b")), (verdict("a", "b", "overlapping")), enabled=False
    ) is quantities


def test_enabled_flag_must_be_a_strict_bool():
    for bad in (1, "yes", None):
        with pytest.raises(TypeError):
            apply_aperture_equivalence_publication((), (), (), enabled=bad)


def test_overlapping_same_figure_area_host_publishes_one_quantity_with_every_member():
    quantities = (qty("b"), qty("a"))
    published = apply_aperture_equivalence_publication(
        quantities,
        (rec("a"), rec("b")),
        (verdict("a", "b", "overlapping"),),
        enabled=True,
    )
    assert len(published) == 1
    row = published[0]
    assert row.input_entity_ids == ("a", "b")
    assert row.value == 1.5
    assert set(row.evidence_ids) == {"e-a", "e-b", "r-a", "r-b"}
    assert row.metadata["aperture_member_ids"] == ("a", "b")
    assert row.metadata["can_issue_firm_quantity"] is False
    assert row.metadata["aperture_equivalence_status"] == EvidenceResolutionStatus.CANDIDATE.value
    assert row.status == "corroborated"
    assert row.authority != "firm"


def test_input_order_does_not_choose_a_member():
    records = (rec("a"), rec("b"))
    verdicts = (verdict("b", "a", "overlapping"),)
    first = apply_aperture_equivalence_publication(
        (qty("a"), qty("b")), records, verdicts, enabled=True
    )
    second = apply_aperture_equivalence_publication(
        (qty("b"), qty("a")), records[::-1], (verdict("a", "b", "overlapping"),), enabled=True
    )
    assert first == second
    assert first[0].input_entity_ids == ("a", "b")


def test_authority_distinct_pair_keeps_both_quantities():
    published = apply_aperture_equivalence_publication(
        (qty("a"), qty("b")),
        (rec("a"), rec("b")),
        (verdict("a", "b", "distinct"),),
        enabled=True,
    )
    assert {row.input_entity_ids for row in published} == {("a",), ("b",)}
    assert all("aperture_class_id" not in row.metadata for row in published)


def test_ambiguous_overlap_unpublishes_both_members():
    published = apply_aperture_equivalence_publication(
        (qty("a"), qty("b")),
        (rec("a"), rec("b", host="wall-2")),
        (verdict("a", "b", "overlapping"),),
        enabled=True,
    )
    assert published == ()


def test_unproven_pair_unpublishes_both_members():
    published = apply_aperture_equivalence_publication(
        (qty("a"), qty("b")),
        (rec("a"), rec("b")),
        (verdict("a", "b", "unproven"),),
        enabled=True,
    )
    assert published == ()


def test_shared_printed_figure_without_a_pair_verdict_unpublishes():
    published = apply_aperture_equivalence_publication(
        (qty("a"), qty("b")),
        (rec("a"), rec("b")),
        (),
        enabled=True,
    )
    assert published == ()


def test_partial_member_coverage_does_not_publish_the_class():
    published = apply_aperture_equivalence_publication(
        (qty("a"),),
        (rec("a"), rec("b")),
        (verdict("a", "b", "overlapping"),),
        enabled=True,
    )
    assert published == ()


def test_conflicting_issued_values_do_not_publish_the_class():
    published = apply_aperture_equivalence_publication(
        (qty("a", value=1.5), qty("b", value=1.6)),
        (rec("a"), rec("b")),
        (verdict("a", "b", "overlapping"),),
        enabled=True,
    )
    assert published == ()


def test_unlisted_opening_is_not_published_when_enabled():
    published = apply_aperture_equivalence_publication(
        (qty("solo"), qty("a")),
        (rec("a"), rec("b")),
        (verdict("a", "b", "distinct"),),
        enabled=True,
    )
    assert [row.input_entity_ids for row in published] == [("a",)]


SHA = "a" * 64


def _opening(*, canonical_id: str, figured_area_record_id: str = "lbl-a") -> LiveCanonicalOpeningObject:
    evidence_ids = (
        canonical_id,
        "source-observation-1",
        "host-binding-1",
        "host-frame-1",
        figured_area_record_id,
    )
    return LiveCanonicalOpeningObject(
        canonical_opening_id=canonical_id,
        physical_opening_id=canonical_id,
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        snapshot_id="snap-1",
        page_id="3",
        viewport_id="vp-floor-1",
        semantic_class="physical_opening",
        structural_pattern="gap_corroborated_window_jamb_pair",
        representative_observation_id="source-observation-1",
        source_observation_ids=("source-observation-1",),
        source_lineage_root_ids=("source-root-1",),
        source_geometries=((0.0, 0.0, 1.0, 0.0),),
        host_wall_id="wall-1",
        host_binding_record_id="host-binding-1",
        host_frame_record_id="host-frame-1",
        wall_local_frame_id=None,
        profile_kind=None,
        coordinate_unit=None,
        u0=None,
        u1=None,
        z0=None,
        z1=None,
        width_m=None,
        height_m=None,
        area_m2=1.5,
        area_basis="figured_opening_label",
        figured_area_record_id=figured_area_record_id,
        opening_void_record_id=None,
        opening_universe_record_id=None,
        width_record_id=None,
        height_record_id=None,
        vertical_placement_record_id=None,
        scale_record_id=None,
        schedule_binding_record_id=None,
        opening_kind="window",
        type_mark=None,
        schedule_page_id=None,
        schedule_declared_width_mm=None,
        schedule_declared_height_mm=None,
        schedule_declared_count=None,
        schedule_count_explicit=False,
        schedule_row_observation_ids=(),
        tag_observation_id=None,
        evidence_ids=evidence_ids,
        geometry_complete=False,
    )


def _composition(*openings: LiveCanonicalOpeningObject):
    return LivePhysicalOpeningVoidComposition(
        revision_id="rev-1",
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("partial",),
        traces=(),
        physical_opening_void_authorities=MappingProxyType({}),
        void_selectors=MappingProxyType({}),
        canonical_openings=tuple(openings),
    )


def test_publish_default_off_keeps_one_quantity_per_opening():
    composition = _composition(_opening(canonical_id="opening-a"), _opening(canonical_id="opening-b"))
    default = publish_live_opening_area_quantities(composition)
    explicit_off = publish_live_opening_area_quantities(
        composition,
        aperture_equivalence_publication_shadow=False,
        aperture_records=(rec("opening-a"), rec("opening-b")),
        aperture_verdicts=(verdict("opening-a", "opening-b", "overlapping"),),
    )
    assert len(default) == 2
    assert default == explicit_off


def test_publish_enabled_collapses_equivalent_openings_and_keeps_member_ids():
    composition = _composition(_opening(canonical_id="opening-a"), _opening(canonical_id="opening-b"))
    published = publish_live_opening_area_quantities(
        composition,
        aperture_equivalence_publication_shadow=True,
        aperture_records=(rec("opening-a"), rec("opening-b")),
        aperture_verdicts=(verdict("opening-a", "opening-b", "overlapping"),),
    )
    assert len(published) == 1
    assert published[0].input_entity_ids == ("opening-a", "opening-b")
    assert published[0].metadata["can_issue_firm_quantity"] is False


def test_live_collect_does_not_expose_or_enable_aperture_publication():
    assert "aperture_equivalence_publication_shadow" not in inspect.signature(
        collect_live_physical_net_wall_claim
    ).parameters
    text = Path(collect_live_physical_net_wall_claim.__code__.co_filename).read_text(
        encoding="utf-8"
    )
    assert "aperture_equivalence_publication_shadow" not in text
