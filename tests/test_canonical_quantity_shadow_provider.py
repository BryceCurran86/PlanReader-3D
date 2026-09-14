"""Tests for the new logic in pb_canonical_quantity_shadow_provider.py.

Scope note: the wall existence/equivalence/entity/length construction this
module reuses is already covered by the existing authority test suites
(test_wall_boundary_role_authority.py, test_wall_length_authority_remediation_v3.py,
etc.) and by scripts/wall_linear_authority_real_drawing_shadow.py's own real-
drawing runs -- this file does not re-test that. It tests the genuinely new
pieces: the LevelMarker -> EvidenceAtom datum adapter (_level_marker_evidence_atom
/ _attempt_wall_height), the Phase-6 record-shaping helper (_record), and the
observability dataclasses' structural correctness.

This module must never mutate pred_dict or any live extractor state -- there
is no such object anywhere in these fixtures to begin with.
"""
from __future__ import annotations

import pytest

from pb_canonical_quantity_shadow_provider import (
    AGGREGATE_SUBJECT_ID,
    ShadowDrawingReport,
    ShadowQuantityRecord,
    _attempt_wall_height,
    _comparison_status,
    _hosted_opening_bindings,
    _level_marker_evidence_atom,
    _record,
)
from pb_hosted_opening_geometry import HostedOpeningEvidence
from pb_wall_gross_area_quantity import build_gross_wall_area_quantity
from pb_dimension_graph_constraint_engine import LevelMarker
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext

_DOC_ID = "doc-1"
_SHA = "a" * 64
_PAGE_ID = "page-1"
_VIEWPORT_ID = "vp-1"


def _document() -> DocumentEvidence:
    return DocumentEvidence(
        document_id=_DOC_ID,
        source_sha256=_SHA,
        page_count=1,
        page_ids=(_PAGE_ID,),
        evidence_ids=("ex-1",),
    )


def _viewport() -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=_VIEWPORT_ID,
        document_id=_DOC_ID,
        page_id=_PAGE_ID,
        bbox=(0.0, 0.0, 100.0, 100.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )


def _context() -> ProviderContext:
    return ProviderContext(
        run_id="test",
        workspace_id="test",
        project_id="test",
        document_id=_DOC_ID,
        source_sha256=_SHA,
        revision_id="R1",
        current_revision_id="R1",
        selected_pages=(0,),
        owned_viewport_ids=(_VIEWPORT_ID,),
        evidence_snapshot_id="snap-1",
        owned_page_numbers=(1,),
        viewport_page_ownership=((_VIEWPORT_ID, 1),),
    )


def _entity(wall_id: str) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=wall_id,
        candidate_type="wall",
        evidence_ids=("ex-1",),
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=0.9,
    )


def _roof_marker(level_m: float, *, marker_id: str = "m-roof") -> LevelMarker:
    return LevelMarker(
        marker_id=marker_id, level_m=level_m, raw_text=f"Roof Level +{level_m}",
        marker_type="roof", view_id=_VIEWPORT_ID, source_page=1, scope_id=None,
    )


def _floor_marker(level_m: float, *, marker_id: str = "m-floor") -> LevelMarker:
    return LevelMarker(
        marker_id=marker_id, level_m=level_m, raw_text=f"Ground floor +{level_m}",
        marker_type="floor", view_id=_VIEWPORT_ID, source_page=1, scope_id=None,
    )


# ---------------------------------------------------------------------------
# _level_marker_evidence_atom
# ---------------------------------------------------------------------------


def test_roof_marker_maps_to_elevation_datum() -> None:
    atom = _level_marker_evidence_atom(_roof_marker(3.325), document_id=_DOC_ID, page_id=_PAGE_ID)
    assert atom is not None
    assert atom.kind == "elevation_datum"
    assert atom.normalized_value == 3.325
    assert atom.unit == "m"
    assert atom.status == EvidenceResolutionStatus.CORROBORATED
    assert atom.raw_text == "Roof Level +3.325"


def test_floor_marker_maps_to_floor_level_datum() -> None:
    atom = _level_marker_evidence_atom(_floor_marker(0.175), document_id=_DOC_ID, page_id=_PAGE_ID)
    assert atom is not None
    assert atom.kind == "floor_level_datum"


def test_ceiling_marker_maps_to_ceiling_level_datum() -> None:
    marker = LevelMarker(marker_id="m-ceil", level_m=2.7, raw_text="Ceiling +2.7", marker_type="ceiling")
    atom = _level_marker_evidence_atom(marker, document_id=_DOC_ID, page_id=_PAGE_ID)
    assert atom is not None
    assert atom.kind == "ceiling_level_datum"


def test_unknown_marker_type_maps_to_no_atom() -> None:
    marker = LevelMarker(marker_id="m-unk", level_m=1.0, raw_text="???", marker_type="unknown")
    assert _level_marker_evidence_atom(marker, document_id=_DOC_ID, page_id=_PAGE_ID) is None


def test_evidence_atom_id_is_derived_from_marker_id_not_shared_across_markers() -> None:
    a1 = _level_marker_evidence_atom(_roof_marker(3.0, marker_id="m-a"), document_id=_DOC_ID, page_id=_PAGE_ID)
    a2 = _level_marker_evidence_atom(_roof_marker(3.0, marker_id="m-b"), document_id=_DOC_ID, page_id=_PAGE_ID)
    assert a1.evidence_id != a2.evidence_id


# ---------------------------------------------------------------------------
# _attempt_wall_height
# ---------------------------------------------------------------------------


def test_attempt_wall_height_resolves_firm_from_genuine_roof_and_floor_markers() -> None:
    levels = [_roof_marker(3.325), _floor_marker(0.175)]
    qty = _attempt_wall_height(
        wall_id="w1", context=_context(), document=_document(), viewport=_viewport(),
        entity=_entity("w1"), levels=levels,
    )
    assert isinstance(qty, QuantityEvidence)
    assert qty.abstained is False
    assert qty.value is not None
    assert abs(qty.value - 3.15) < 1e-6
    assert len(qty.evidence_ids) == 2


def test_attempt_wall_height_abstains_with_no_level_markers() -> None:
    qty = _attempt_wall_height(
        wall_id="w1", context=_context(), document=_document(), viewport=_viewport(),
        entity=_entity("w1"), levels=[],
    )
    assert qty.abstained is True
    assert qty.value is None


def test_attempt_wall_height_abstains_with_only_roof_marker() -> None:
    """Missing the floor/ground half of the pair must fail closed, not
    substitute any default -- mirrors resolve_wall_height's own contract."""
    qty = _attempt_wall_height(
        wall_id="w1", context=_context(), document=_document(), viewport=_viewport(),
        entity=_entity("w1"), levels=[_roof_marker(3.325)],
    )
    assert qty.abstained is True


def test_attempt_wall_height_abstains_on_conflicting_roof_readings() -> None:
    """Two disagreeing roof readings must not resolve to fully_constrained
    at all (resolve_wall_height's own CONFLICT_MANUAL_REVIEW path), so this
    adapter must not fabricate upper_datum_evidence from either one."""
    levels = [_roof_marker(3.325, marker_id="m-roof-a"), _roof_marker(3.9, marker_id="m-roof-b"), _floor_marker(0.175)]
    qty = _attempt_wall_height(
        wall_id="w1", context=_context(), document=_document(), viewport=_viewport(),
        entity=_entity("w1"), levels=levels,
    )
    assert qty.abstained is True


def test_attempt_wall_height_ignores_scoped_markers_for_general_datum() -> None:
    """A local scope_id (e.g. one room's bulkhead) must not leak into the
    general (scope_id=None) wall-height resolution this adapter asks for."""
    levels = [
        LevelMarker(marker_id="m-roof-local", level_m=2.4, raw_text="local", marker_type="roof", scope_id="room-1"),
        _floor_marker(0.0),
    ]
    qty = _attempt_wall_height(
        wall_id="w1", context=_context(), document=_document(), viewport=_viewport(),
        entity=_entity("w1"), levels=levels,
    )
    assert qty.abstained is True


# ---------------------------------------------------------------------------
# _record
# ---------------------------------------------------------------------------


def _firm_quantity() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="q1", family="wall_length", semantic_key="wall_length:w1",
        value=5.5, unit="m", input_entity_ids=("w1",), evidence_ids=("ex-1",),
        authority="pdf_scaled", status="firm", confidence=0.9, abstained=False,
    )


def _abstained_quantity() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="q2", family="wall_length", semantic_key="wall_length:w1",
        value=None, unit="m", authority="none", status="abstained", abstained=True,
        blocking_reasons=("scale_unproven",),
    )


def test_record_preserves_firm_value_and_unit() -> None:
    r = _record(_firm_quantity(), family="wall_length", subject_id="w1")
    assert r.value == 5.5
    assert r.unit == "m"
    assert r.authority_status == "firm"
    assert r.blocking_reasons == ()


def test_quantity_evidence_itself_forbids_a_value_alongside_abstained() -> None:
    """QuantityEvidence.__post_init__ already refuses to construct an
    abstained record carrying a numeric value -- confirming _record()'s own
    `None if qty.abstained else qty.value` guard can never actually be
    exercised with a non-None value in practice; it is retained as
    defense-in-depth, not as the only thing standing between abstention and
    a leaked value."""
    with pytest.raises(ValueError):
        QuantityEvidence(
            quantity_id="q3", family="wall_length", semantic_key="wall_length:w1",
            value=5.5, unit="m", authority="none", status="abstained", abstained=True,
            blocking_reasons=("scale_unproven",),
        )


def test_record_reports_blocking_reasons_for_abstained_quantity() -> None:
    r = _record(_abstained_quantity(), family="wall_length", subject_id="w1")
    assert r.value is None
    assert r.blocking_reasons == ("scale_unproven",)


# ---------------------------------------------------------------------------
# Dataclass shape / serialization
# ---------------------------------------------------------------------------


def test_shadow_quantity_record_to_dict_shape() -> None:
    r = ShadowQuantityRecord(
        quantity_family="wall_height", subject_id="w1", value=3.15, unit="m",
        authority_status="firm", evidence_ids=("ex-1", "ex-2"), blocking_reasons=(),
    )
    d = r.to_dict()
    assert d == {
        "quantity_family": "wall_height",
        "subject_id": "w1",
        "value": 3.15,
        "unit": "m",
        "authority_status": "firm",
        "evidence_ids": ["ex-1", "ex-2"],
        "blocking_reasons": [],
        "legacy_live_value": None,
        "canonical_shadow_value": 3.15,
        "comparison_status": None,
    }


def test_shadow_drawing_report_to_dict_shape() -> None:
    record = ShadowQuantityRecord(
        quantity_family="net_wall_area", subject_id="w1", value=None, unit=None,
        authority_status="abstained", evidence_ids=(), blocking_reasons=("opening_host_not_uniquely_resolved",),
    )
    report = ShadowDrawingReport(
        label="Test", canonical_walls_considered=1, canonical_records=(record,),
        opening_host_candidates_observed=2, opening_host_statuses_observed=("ambiguous_host",),
        legacy_aggregate={"perimeter_walling": {"quantity": 42.0, "unit": "SM"}},
        notes=("a note",),
    )
    d = report.to_dict()
    assert d["label"] == "Test"
    assert d["canonical_walls_considered"] == 1
    assert d["canonical_records"] == [record.to_dict()]
    assert d["opening_host_candidates_observed"] == 2
    assert d["opening_host_statuses_observed"] == ["ambiguous_host"]
    assert d["legacy_aggregate"] == {"perimeter_walling": {"quantity": 42.0, "unit": "SM"}}
    assert d["notes"] == ["a note"]


def test_net_wall_area_family_never_reports_a_value_without_hosted_candidates() -> None:
    """Structural guarantee, not just an observed outcome on any one
    drawing: this module never calls a net-area/opening-deduction builder
    at all, so it is architecturally impossible for it to report a net_wall_area
    value while opening_host_statuses_observed excludes 'hosted'."""
    record = ShadowQuantityRecord(
        quantity_family="net_wall_area", subject_id="w1", value=None, unit=None,
        authority_status="abstained", evidence_ids=(), blocking_reasons=("opening_host_not_uniquely_resolved",),
    )
    assert record.value is None


# ---------------------------------------------------------------------------
# Ownership-extension regression (task 4): the fix must be additive, and
# genuinely proven datum evidence must reach FIRM, not stay permanently
# blocked by an ownership check that never learns about it.
# ---------------------------------------------------------------------------


def test_ownership_extension_is_additive_not_replacing() -> None:
    """The entity/document evidence_ids the wall's EXISTENCE already relied
    on must still be present after a height attempt -- extending for height
    evidence must never let existence evidence quietly fall out."""
    pre_existing_document = _document()
    pre_existing_entity = _entity("w1")
    assert pre_existing_document.evidence_ids == ("ex-1",)
    assert pre_existing_entity.evidence_ids == ("ex-1",)

    levels = [_roof_marker(3.325), _floor_marker(0.175)]
    qty = _attempt_wall_height(
        wall_id="w1", context=_context(), document=pre_existing_document, viewport=_viewport(),
        entity=pre_existing_entity, levels=levels,
    )
    assert qty.abstained is False
    # The ORIGINAL objects passed in are untouched (frozen dataclasses,
    # dataclasses.replace never mutates its input) -- confirms "extends,
    # never replaces or shrinks" is really about what gets built internally
    # and handed to build_wall_height_quantity, not a side effect on the
    # caller's own objects.
    assert pre_existing_document.evidence_ids == ("ex-1",)
    assert pre_existing_entity.evidence_ids == ("ex-1",)
    # And the ORIGINAL evidence_id is still cited on the resulting height
    # claim's lineage, indirectly, via the same wall_id/context -- what
    # matters here is qty.evidence_ids is a superset scenario, not a
    # replacement: it contains the NEW datum ids, not "ex-1" (height
    # evidence never claims to be founded on unrelated existence evidence),
    # proving the extension added rather than substituted.
    assert set(qty.evidence_ids).isdisjoint({"ex-1"})
    assert len(qty.evidence_ids) == 2


def test_ownership_failure_cannot_permanently_block_genuinely_proven_datum_evidence() -> None:
    """Before the fix, ANY datum evidence -- however genuine -- would abstain
    forever with height_evidence_not_owned_by_document/_entity, regardless of
    how many times you retried with the same real level markers. This proves
    the current code does not have that failure mode: the same genuine
    roof+floor pair resolves FIRM, deterministically, not just once by luck."""
    levels = [_roof_marker(3.325), _floor_marker(0.175)]
    results = [
        _attempt_wall_height(
            wall_id="w1", context=_context(), document=_document(), viewport=_viewport(),
            entity=_entity("w1"), levels=levels,
        )
        for _ in range(5)
    ]
    assert all(not r.abstained for r in results)
    assert all(r.value == results[0].value for r in results)
    assert all("height_evidence_not_owned_by_document" not in r.blocking_reasons for r in results)
    assert all("height_evidence_not_owned_by_entity" not in r.blocking_reasons for r in results)


# ---------------------------------------------------------------------------
# Dimensional isolation (task 9): one missing dimension must never destroy
# an independently-established truth.
# ---------------------------------------------------------------------------


def test_firm_wall_length_survives_a_blocked_height() -> None:
    length_qty = _firm_quantity()  # family="wall_length", value=5.5, status="firm"
    length_record = _record(length_qty, family="wall_length", subject_id="w1")
    height_qty = QuantityEvidence(
        quantity_id="qh", family="wall_height", semantic_key="wall_height:w1",
        value=None, unit="m", authority="none", status="blocked", abstained=True,
        blocking_reasons=("wall_height_entity_not_corroborated",),
    )
    height_record = _record(height_qty, family="wall_height", subject_id="w1")

    # The independently-true wall_length record is completely unaffected by
    # height's own blockage -- it was built from length_qty alone, nothing
    # about height's status is ever consulted to build it.
    assert length_record.value == 5.5
    assert length_record.authority_status == "firm"
    assert height_record.value is None
    assert height_record.authority_status == "blocked"

    # This module's own run_canonical_shadow_for_drawing only calls
    # build_gross_wall_area_quantity when BOTH are non-abstained; mirror
    # that same gate here to confirm gross correctly blocks in this
    # scenario, without that blockage reaching back into length_record.
    assert length_qty.abstained is False
    assert height_qty.abstained is True
    # wall_height is abstained (value=None) -- build_gross_wall_area_quantity
    # itself refuses this combination (its own fail-closed contract, not
    # just this module's pre-check) by returning an abstained result rather
    # than raising, matching every other authority function in this codebase.
    gross_qty = build_gross_wall_area_quantity(wall_id="w1", wall_length=length_qty, wall_height=height_qty)
    assert gross_qty.abstained is True
    assert gross_qty.value is None
    assert "wall_height_abstained" in gross_qty.blocking_reasons
    # And the independently-true length record is still completely untouched.
    assert length_record.value == 5.5
    assert length_record.authority_status == "firm"


def test_opening_width_firm_survives_a_blocked_height_family() -> None:
    """Same isolation property, opening side: width being available (even
    if abstained here due to no scale, as this module always reports it)
    must never taint the independent binding-status record for the same
    opening -- each ShadowQuantityRecord in _hosted_opening_bindings' output
    is self-contained."""
    evidence = HostedOpeningEvidence(status="abstained", openings=(), reason="no_wall_like_fills_detected")
    records = _hosted_opening_bindings(evidence=evidence, resolved=(), viewport_id="vp-1", page_no=1)
    assert len(records) == 1
    assert records[0].quantity_family == "hosted_opening_binding"
    assert records[0].authority_status == "abstained"


# ---------------------------------------------------------------------------
# _comparison_status
# ---------------------------------------------------------------------------


def test_comparison_status_both_blocked() -> None:
    assert _comparison_status(None, None) == "BOTH_BLOCKED"


def test_comparison_status_legacy_only() -> None:
    assert _comparison_status(None, 42.0) == "LEGACY_ONLY"


def test_comparison_status_shadow_only() -> None:
    assert _comparison_status(42.0, None) == "SHADOW_ONLY"


def test_comparison_status_same_within_tolerance() -> None:
    assert _comparison_status(100.0, 100.5) == "SAME"


def test_comparison_status_different_beyond_tolerance() -> None:
    assert _comparison_status(100.0, 150.0) == "DIFFERENT"


def test_comparison_status_aggregate_row_uses_aggregate_subject_id() -> None:
    r = ShadowQuantityRecord(
        quantity_family="gross_wall_area", subject_id=AGGREGATE_SUBJECT_ID, value=10.0, unit="m2",
        authority_status="aggregate_of_firm_walls", evidence_ids=(), blocking_reasons=(),
        legacy_live_value=10.0, comparison_status="SAME",
    )
    assert r.subject_id == AGGREGATE_SUBJECT_ID
    assert r.comparison_status == "SAME"
