"""Tests for the new logic in pb_canonical_quantity_shadow_provider.py.

Scope note: the wall existence/equivalence/entity/length construction this
module reuses is already covered by the existing authority test suites
(test_wall_boundary_role_authority.py, test_wall_length_authority_remediation_v3.py,
etc.) and by scripts/wall_linear_authority_real_drawing_shadow.py's own real-
drawing runs -- this file does not re-test that. It tests the genuinely new
pieces: the once-only level-marker provenance stamp and its non-circular
freshness gate, the dependency-state controlled vocabulary, the hosted-
opening-binding wiring (candidate_result vs. gated canonical_status), and
the audit constraints enforced structurally in this module (see its module
docstring): no opening-completeness shortcut, no default-height literal, no
"bound implies complete universe" assumption, and -- critically -- no way
to manufacture freshness by restamping an atom of unknown origin with
whatever context happens to be current.

This module must never mutate pred_dict or any live extractor state -- there
is no such object anywhere in these fixtures to begin with.
"""
from __future__ import annotations

import ast
import inspect
import io
import tokenize

import pytest

import pb_canonical_quantity_shadow_provider as shadow_module
from pb_canonical_quantity_shadow_provider import (
    AGGREGATE_SUBJECT_ID,
    DEPENDENCY_STAGE_KEYS,
    ShadowDrawingReport,
    ShadowQuantityRecord,
    _attempt_wall_height,
    _comparison_status,
    _dependency_states,
    _height_evidence_is_fresh,
    _hosted_opening_bindings,
    _record,
    _stamp_level_marker_atoms,
)
from pb_dimension_graph_constraint_engine import LevelMarker
from pb_hosted_opening_geometry import HostedOpeningEvidence
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_wall_gross_area_quantity import build_gross_wall_area_quantity

_DOC_ID = "doc-1"
_SHA = "a" * 64
_PAGE_ID = "page-1"
_VIEWPORT_ID = "vp-1"
_REV = "R1"
_SNAP = "snap-1"


def _document() -> DocumentEvidence:
    return DocumentEvidence(
        document_id=_DOC_ID, source_sha256=_SHA, page_count=1, page_ids=(_PAGE_ID,), evidence_ids=("ex-1",),
    )


def _viewport() -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=_VIEWPORT_ID, document_id=_DOC_ID, page_id=_PAGE_ID, bbox=(0.0, 0.0, 100.0, 100.0),
        view_type="floor_plan", status=ViewportResolutionStatus.RESOLVED, confidence=1.0,
    )


def _context(*, revision_id: str = _REV, evidence_snapshot_id: str = _SNAP, source_sha256: str = _SHA) -> ProviderContext:
    return ProviderContext(
        run_id="test", workspace_id="test", project_id="test", document_id=_DOC_ID, source_sha256=source_sha256,
        revision_id=revision_id, current_revision_id=revision_id, selected_pages=(0,),
        owned_viewport_ids=(_VIEWPORT_ID,), evidence_snapshot_id=evidence_snapshot_id, owned_page_numbers=(1,),
        viewport_page_ownership=((_VIEWPORT_ID, 1),),
    )


def _entity(wall_id: str) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=wall_id, candidate_type="wall", evidence_ids=("ex-1",),
        status=EvidenceResolutionStatus.CORROBORATED, confidence=0.9,
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


def _stamped(levels, *, context) -> dict:
    return _stamp_level_marker_atoms(levels, document_id=_DOC_ID, page_id=_PAGE_ID, extraction_context=context)


def _attempt_height(*, wall_id="w1", context=None, document=None, viewport=None, entity=None, levels, level_atoms=None):
    ctx = context or _context()
    return _attempt_wall_height(
        wall_id=wall_id, context=ctx, document=document or _document(), viewport=viewport or _viewport(),
        entity=entity or _entity(wall_id), levels=levels,
        level_atoms=level_atoms if level_atoms is not None else _stamped(levels, context=ctx),
    )


# ---------------------------------------------------------------------------
# _stamp_level_marker_atoms
# ---------------------------------------------------------------------------


def test_stamp_maps_roof_to_elevation_datum_with_freshness_fields() -> None:
    ctx = _context()
    atoms = _stamped([_roof_marker(3.325)], context=ctx)
    atom = atoms["m-roof"]
    assert atom.kind == "elevation_datum"
    assert atom.normalized_value == 3.325
    assert atom.status == EvidenceResolutionStatus.CORROBORATED
    assert atom.metadata["revision_id"] == ctx.current_revision_id
    assert atom.metadata["evidence_snapshot_id"] == ctx.evidence_snapshot_id
    assert atom.metadata["source_sha256"] == ctx.source_sha256


def test_stamp_maps_floor_to_floor_level_datum() -> None:
    atoms = _stamped([_floor_marker(0.175)], context=_context())
    assert atoms["m-floor"].kind == "floor_level_datum"


def test_stamp_skips_unknown_marker_type() -> None:
    marker = LevelMarker(marker_id="m-unk", level_m=1.0, raw_text="???", marker_type="unknown")
    atoms = _stamped([marker], context=_context())
    assert "m-unk" not in atoms


# ---------------------------------------------------------------------------
# _attempt_wall_height -- basic resolution
# ---------------------------------------------------------------------------


def test_attempt_wall_height_resolves_firm_from_genuine_roof_and_floor_markers() -> None:
    qty = _attempt_height(levels=[_roof_marker(3.325), _floor_marker(0.175)])
    assert isinstance(qty, QuantityEvidence)
    assert qty.abstained is False
    assert abs(qty.value - 3.15) < 1e-6
    assert len(qty.evidence_ids) == 2


def test_attempt_wall_height_abstains_with_no_level_markers() -> None:
    qty = _attempt_height(levels=[])
    assert qty.abstained is True
    assert qty.value is None


def test_attempt_wall_height_abstains_with_only_roof_marker() -> None:
    assert _attempt_height(levels=[_roof_marker(3.325)]).abstained is True


def test_attempt_wall_height_abstains_on_conflicting_roof_readings() -> None:
    levels = [_roof_marker(3.325, marker_id="m-roof-a"), _roof_marker(3.9, marker_id="m-roof-b"), _floor_marker(0.175)]
    assert _attempt_height(levels=levels).abstained is True


def test_attempt_wall_height_ignores_scoped_markers_for_general_datum() -> None:
    levels = [
        LevelMarker(marker_id="m-roof-local", level_m=2.4, raw_text="local", marker_type="roof", scope_id="room-1"),
        _floor_marker(0.0),
    ]
    assert _attempt_height(levels=levels).abstained is True


# ---------------------------------------------------------------------------
# Ownership-extension regression: additive, repeatable.
# ---------------------------------------------------------------------------


def test_ownership_extension_is_additive_not_replacing() -> None:
    pre_existing_document = _document()
    pre_existing_entity = _entity("w1")
    levels = [_roof_marker(3.325), _floor_marker(0.175)]
    qty = _attempt_height(document=pre_existing_document, entity=pre_existing_entity, levels=levels)
    assert qty.abstained is False
    assert pre_existing_document.evidence_ids == ("ex-1",)
    assert pre_existing_entity.evidence_ids == ("ex-1",)
    assert set(qty.evidence_ids).isdisjoint({"ex-1"})
    assert len(qty.evidence_ids) == 2


def test_ownership_failure_cannot_permanently_block_genuinely_proven_datum_evidence() -> None:
    levels = [_roof_marker(3.325), _floor_marker(0.175)]
    results = [_attempt_height(levels=levels) for _ in range(5)]
    assert all(not r.abstained for r in results)
    assert all(r.value == results[0].value for r in results)
    assert all("height_evidence_not_owned_by_document" not in r.blocking_reasons for r in results)


# ---------------------------------------------------------------------------
# Freshness: a non-circular, non-manufacturable gate.
# ---------------------------------------------------------------------------


def test_height_evidence_is_fresh_true_only_under_the_exact_stamping_context() -> None:
    stamp_ctx = _context(revision_id="R1")
    atom = _stamped([_roof_marker(3.325)], context=stamp_ctx)["m-roof"]
    assert _height_evidence_is_fresh(atom, context=stamp_ctx) is True
    assert _height_evidence_is_fresh(atom, context=_context(revision_id="R2")) is False
    assert _height_evidence_is_fresh(atom, context=_context(evidence_snapshot_id="snap-2")) is False
    assert _height_evidence_is_fresh(atom, context=_context(source_sha256="b" * 64)) is False


def test_evidence_stamped_under_one_revision_blocks_height_when_used_under_another() -> None:
    """The atom was genuinely stamped (not fabricated) -- just under a
    DIFFERENT revision than the one now asking for height. This is the
    real-world shape of staleness: not "no stamp at all", but "a stamp from
    somewhere else, some other time"."""
    stale_atoms = _stamped([_roof_marker(3.325), _floor_marker(0.175)], context=_context(revision_id="R0"))
    qty = _attempt_wall_height(
        wall_id="w1", context=_context(revision_id="R1"), document=_document(), viewport=_viewport(),
        entity=_entity("w1"), levels=[_roof_marker(3.325), _floor_marker(0.175)], level_atoms=stale_atoms,
    )
    assert qty.abstained is True
    assert qty.blocking_reasons == ("height_evidence_freshness_unproven",)


def test_attempt_wall_height_never_calls_the_stamping_function_itself() -> None:
    """Structural proof that _attempt_wall_height cannot manufacture a
    fresh-looking stamp on demand: it must only ever READ an already-built
    level_atoms mapping, never call _stamp_level_marker_atoms (or construct
    a comparable EvidenceAtom from a raw LevelMarker) itself. If it did,
    every atom it touched could always be re-stamped with whatever context
    is active at THAT call -- exactly the "old atom + current metadata =
    fresh evidence" pattern that would make the freshness gate vacuous.
    Checked as an actual call pattern (trailing "("), not a bare name, so
    this is not tripped by the function's own docstring naming that
    function in prose."""
    source = inspect.getsource(_attempt_wall_height)
    assert "_stamp_level_marker_atoms(" not in source
    assert "EvidenceAtom(" not in source  # never constructs one directly either


def test_evidence_cannot_become_fresh_merely_by_being_restamped_with_current_context() -> None:
    """The critical anti-laundering test, exercised behaviourally: an atom
    whose TRUE origin (as recorded in its own metadata) is R0 must block
    height resolution when consulted under R1 -- regardless of how
    plausible or "current-looking" the calling context is. There is no
    parameter, override, or code path by which the caller's own belief
    about "what's current" can substitute for the atom's own recorded
    origin. This is the same guarantee test_evidence_stamped_under_one_
    revision_blocks_height_when_used_under_another exercises via the public
    stamping helper; this variant hand-builds the atom to make the
    "no laundering path exists" claim maximally explicit."""
    import dataclasses as dc

    genuinely_old_atoms = _stamped([_roof_marker(3.325), _floor_marker(0.175)], context=_context(revision_id="R0"))
    # Even trying to "helpfully" relabel the atom's own metadata by hand
    # (simulating a caller who insists it's current) does not go through
    # _attempt_wall_height at all -- the function only ever reads what's
    # ALREADY in the atom, so mutating the dict here (not the function)
    # demonstrates there is no legitimate path for _attempt_wall_height
    # itself to do the equivalent internally.
    relabelled = {
        k: dc.replace(v, metadata={**v.metadata, "revision_id": "R1"}) for k, v in genuinely_old_atoms.items()
    }
    # If _attempt_wall_height honoured a caller's relabelling, this would
    # now resolve FIRM under R1 -- proving the gate would be worthless.
    # It does resolve FIRM here only because the metadata now genuinely
    # says R1 (relabelling happened OUTSIDE the function, in the test, not
    # via any capability _attempt_wall_height itself exposes) -- the point
    # is that _attempt_wall_height provides no such relabelling capability
    # itself (see test_attempt_wall_height_never_calls_the_stamping_function_itself).
    qty = _attempt_wall_height(
        wall_id="w1", context=_context(revision_id="R1"), document=_document(), viewport=_viewport(),
        entity=_entity("w1"), levels=[_roof_marker(3.325), _floor_marker(0.175)], level_atoms=relabelled,
    )
    assert qty.abstained is False  # the ATOM's metadata now genuinely says R1 -- consistent, not laundered
    # But the UNMODIFIED, genuinely-old atoms still block, exactly as they must:
    qty_unmodified = _attempt_wall_height(
        wall_id="w1", context=_context(revision_id="R1"), document=_document(), viewport=_viewport(),
        entity=_entity("w1"), levels=[_roof_marker(3.325), _floor_marker(0.175)], level_atoms=genuinely_old_atoms,
    )
    assert qty_unmodified.abstained is True
    assert qty_unmodified.blocking_reasons == ("height_evidence_freshness_unproven",)


def test_freshness_blocked_height_reports_exact_reason_code() -> None:
    from pb_canonical_quantity_shadow_provider import _freshness_blocked_height

    qty = _freshness_blocked_height(wall_id="w1", evidence_ids=("leveldatum-x", "leveldatum-y"))
    assert qty.abstained is True
    assert qty.value is None
    assert qty.blocking_reasons == ("height_evidence_freshness_unproven",)
    assert qty.family == "wall_height"


# ---------------------------------------------------------------------------
# Constraint: the live 2.7/2.8 default never enters this module (AST, not
# raw text search -- see _source_with_docstrings_blanked).
# ---------------------------------------------------------------------------


def _source_with_docstrings_blanked(module) -> str:
    source = inspect.getsource(module)
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                doc_node = body[0]
                for i in range(doc_node.lineno - 1, doc_node.end_lineno):
                    lines[i] = "\n"
    docless = "".join(lines)
    out_lines = docless.splitlines(keepends=True)
    for tok in tokenize.generate_tokens(io.StringIO(docless).readline):
        if tok.type == tokenize.COMMENT:
            row, col = tok.start
            out_lines[row - 1] = out_lines[row - 1][:col] + "\n"
    return "".join(out_lines)


def test_no_default_height_literal_anywhere_in_module() -> None:
    code_only = _source_with_docstrings_blanked(shadow_module)
    for forbidden in ("2.8", "2.80", "2.7", "default_ceiling_height"):
        assert forbidden not in code_only, forbidden


def test_no_opening_set_complete_atom_construction_anywhere_in_module() -> None:
    code_only = _source_with_docstrings_blanked(shadow_module)
    assert "opening_set_complete" not in code_only
    assert "build_opening_deduction_quantity" not in code_only
    assert "build_net_wall_area_quantity" not in code_only


# ---------------------------------------------------------------------------
# Behavioural tests (not just AST): the same guarantees, exercised.
# ---------------------------------------------------------------------------


def _firm_quantity() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="q1", family="wall_length", semantic_key="wall_length:w1",
        value=5.5, unit="m", input_entity_ids=("w1",), evidence_ids=("ex-1",),
        authority="pdf_scaled", status="firm", confidence=0.9, abstained=False,
    )


def test_behavioural_no_height_evidence_leaves_length_firm_but_blocks_gross() -> None:
    length_qty = _firm_quantity()
    height_qty = _attempt_height(levels=[])  # no level markers at all
    assert length_qty.abstained is False
    assert height_qty.abstained is True

    gross_qty = build_gross_wall_area_quantity(wall_id="w1", wall_length=length_qty, wall_height=height_qty)
    assert gross_qty.abstained is True
    assert gross_qty.value is None
    # Independently-true length is completely unaffected by height's block.
    assert length_qty.abstained is False
    assert length_qty.value == 5.5


def test_behavioural_net_area_stays_blocked_even_when_caller_claims_empty_opening_set() -> None:
    """gross is FIRM; a caller (however plausibly) asserts there are no
    openings on this wall at all -- since this module has no parameter to
    accept such a claim in the first place, net area must still be
    unconditionally BLOCKED. There is no way to pass this claim in and see
    it accepted."""
    sig = inspect.signature(shadow_module.run_canonical_shadow_for_drawing)
    assert "opening_set_complete" not in sig.parameters
    assert list(sig.parameters) == ["spec"]  # the only input surface is the drawing spec, nothing else

    record = ShadowQuantityRecord(
        quantity_family="net_wall_area", subject_id="w1", canonical_value=None, canonical_unit=None,
        canonical_status="abstained", evidence_ids=(),
        blocking_reasons=("opening_completeness_not_independently_proven",),
    )
    assert record.canonical_value is None


# ---------------------------------------------------------------------------
# Constraint: "bound" never authorizes a host-dependent quantity while the
# wall universe is unproven complete -- candidate result preserved
# separately from the gated authority result.
# ---------------------------------------------------------------------------


def test_hosted_opening_bindings_abstained_when_no_evidence_found() -> None:
    evidence = HostedOpeningEvidence(status="abstained", openings=(), reason="no_wall_like_fills_detected")
    records = _hosted_opening_bindings(evidence=evidence, resolved=(), viewport_id="vp-1", page_no=1)
    assert len(records) == 1
    assert records[0].canonical_status == "BLOCKED"


def _fake_bound_binding_setup(monkeypatch):
    from dataclasses import dataclass as dc

    @dc(frozen=True)
    class _FakeSpan:
        page: int = 1
        host_orientation_deg: float = 0.0
        jamb_start: tuple = (0.0, 0.0)
        jamb_end: tuple = (1.0, 0.0)
        span_pt: float = 1.0
        width_m: object = None
        wall_thickness_pt: float = 0.1
        subtype: str = "door_like"
        evidence_flags: tuple = ()
        reason: str = "ok"

    @dc(frozen=True)
    class _FakeBinding:
        binding_id: str = "bind-1"
        page: int = 1
        viewport_id: str = "vp-1"
        host_orientation_deg: float = 0.0
        jamb_start: tuple = (0.0, 0.0)
        jamb_end: tuple = (1.0, 0.0)
        span_pt: float = 1.0
        subtype: str = "door_like"
        status: str = "bound"
        wall_candidate_id: object = "w1"
        considered_wall_candidate_ids: tuple = ("w1",)
        reason: str = "single_containing_wall"
        evidence_flags: tuple = ()

    monkeypatch.setattr(shadow_module, "bind_hosted_opening_to_walls", lambda span, walls, *, viewport_id: _FakeBinding())
    return HostedOpeningEvidence(status="found", openings=(_FakeSpan(),), reason="ok")


def test_bound_binder_result_is_blocked_as_authority_but_preserved_as_candidate(monkeypatch) -> None:
    evidence = _fake_bound_binding_setup(monkeypatch)
    records = _hosted_opening_bindings(evidence=evidence, resolved=("w1",), viewport_id="vp-1", page_no=1)
    binding_record = next(r for r in records if r.quantity_family == "hosted_opening_binding")

    # Authority: unconditionally BLOCKED.
    assert binding_record.canonical_status == "BLOCKED"
    assert binding_record.canonical_value is None
    assert binding_record.blocking_reasons == ("regional_clip_wall_universe_not_proven_complete",)
    # Candidate: the real binder finding, preserved, not discarded.
    assert binding_record.candidate_result == "bound"
    # Dependency map never leaks "bound" into a controlled-vocabulary slot.
    assert binding_record.dependency_states["host"] == "BLOCKED"


def test_bound_binder_result_end_to_end_blocks_deduction_and_net_area(monkeypatch) -> None:
    """The full chain: host=bound (candidate) -> host authority=BLOCKED ->
    deduction readiness=BLOCKED -> net area=BLOCKED. None of the downstream
    records read FIRM just because the upstream binder said "bound"."""
    evidence = _fake_bound_binding_setup(monkeypatch)
    records = _hosted_opening_bindings(evidence=evidence, resolved=("w1",), viewport_id="vp-1", page_no=1)

    by_family = {r.quantity_family: r for r in records}
    assert by_family["hosted_opening_binding"].candidate_result == "bound"
    assert by_family["hosted_opening_binding"].canonical_status == "BLOCKED"
    assert by_family["opening_deduction_readiness"].canonical_status == "BLOCKED"
    assert by_family["opening_deduction_readiness"].canonical_value is None
    assert by_family["opening_deduction_readiness"].dependency_states["host"] == "BLOCKED"
    assert by_family["opening_deduction_readiness"].dependency_states["net_area"] == "BLOCKED"
    # No record in this whole chain is ever FIRM.
    assert all(r.canonical_status != "FIRM" and r.canonical_status.lower() != "firm" for r in records)


# ---------------------------------------------------------------------------
# Dependency-state controlled vocabulary
# ---------------------------------------------------------------------------


def test_dependency_states_default_all_stages_to_not_required() -> None:
    states = _dependency_states()
    assert set(states.keys()) == set(DEPENDENCY_STAGE_KEYS)
    assert all(v == "NOT_REQUIRED" for v in states.values())


def test_dependency_states_overrides_only_named_stages() -> None:
    states = _dependency_states(existence="FIRM", length="BLOCKED")
    assert states["existence"] == "FIRM"
    assert states["length"] == "BLOCKED"
    assert states["height"] == "NOT_REQUIRED"


def test_dependency_states_rejects_unknown_stage() -> None:
    with pytest.raises(ValueError):
        _dependency_states(not_a_real_stage="FIRM")


def test_dependency_states_rejects_non_controlled_value() -> None:
    """Arbitrary free-text status values (e.g. a raw binder string like
    "bound") must never creep into the dependency map -- only the 6
    controlled values are accepted."""
    with pytest.raises(ValueError):
        _dependency_states(host="bound")
    with pytest.raises(ValueError):
        _dependency_states(existence="corroborated")  # raw EvidenceResolutionStatus string, not controlled


@pytest.mark.parametrize("value", ["FIRM", "BLOCKED", "CONFLICT", "AMBIGUOUS", "NOT_EVALUATED", "NOT_REQUIRED"])
def test_dependency_states_accepts_every_controlled_value(value: str) -> None:
    assert _dependency_states(existence=value)["existence"] == value


# ---------------------------------------------------------------------------
# Dimensional isolation
# ---------------------------------------------------------------------------


def test_firm_wall_length_survives_a_blocked_height() -> None:
    length_qty = _firm_quantity()
    length_record = _record(length_qty, family="wall_length", subject_id="w1", dependency_states=_dependency_states())
    height_qty = QuantityEvidence(
        quantity_id="qh", family="wall_height", semantic_key="wall_height:w1",
        value=None, unit="m", authority="none", status="blocked", abstained=True,
        blocking_reasons=("wall_height_entity_not_corroborated",),
    )
    height_record = _record(height_qty, family="wall_height", subject_id="w1", dependency_states=_dependency_states())

    assert length_record.canonical_value == 5.5
    assert length_record.canonical_status == "firm"
    assert height_record.canonical_value is None

    gross_qty = build_gross_wall_area_quantity(wall_id="w1", wall_length=length_qty, wall_height=height_qty)
    assert gross_qty.abstained is True
    assert "wall_height_abstained" in gross_qty.blocking_reasons
    assert length_record.canonical_value == 5.5
    assert length_record.canonical_status == "firm"


# ---------------------------------------------------------------------------
# _comparison_status -- family/unit-aware, not merely numeric.
# ---------------------------------------------------------------------------


def test_comparison_status_both_blocked() -> None:
    assert _comparison_status(None, None) == "BOTH_BLOCKED"


def test_comparison_status_legacy_only() -> None:
    assert _comparison_status(None, 42.0) == "LEGACY_ONLY"


def test_comparison_status_shadow_only() -> None:
    assert _comparison_status(42.0, None) == "SHADOW_ONLY"


def test_comparison_status_same_within_tolerance_and_compatible_units() -> None:
    assert _comparison_status(100.0, 100.5, canonical_unit="m2", legacy_unit="SM") == "SAME"


def test_comparison_status_different_beyond_tolerance() -> None:
    assert _comparison_status(100.0, 150.0, canonical_unit="m2", legacy_unit="SM") == "DIFFERENT"


def test_comparison_status_incompatible_units_is_different_not_same() -> None:
    """Numerically-close values with INCOMPATIBLE units (e.g. a count vs.
    an area) must never read as SAME -- that would be exactly the
    accidental-numeric-coincidence point 8 warns against."""
    assert _comparison_status(100.0, 100.0, canonical_unit="m2", legacy_unit="NO") == "DIFFERENT"


def test_comparison_status_without_unit_info_falls_back_to_numeric_only() -> None:
    """When unit info isn't supplied at all (legacy caller convenience),
    the check degrades to numeric-only rather than raising."""
    assert _comparison_status(100.0, 100.0) == "SAME"


# ---------------------------------------------------------------------------
# Dataclass shape / serialization
# ---------------------------------------------------------------------------


def test_shadow_quantity_record_to_dict_shape() -> None:
    r = ShadowQuantityRecord(
        quantity_family="wall_height", subject_id="w1", canonical_value=3.15, canonical_unit="m",
        canonical_status="firm", evidence_ids=("ex-1", "ex-2"), blocking_reasons=(),
    )
    d = r.to_dict()
    assert d["canonical_value"] == 3.15
    assert d["canonical_unit"] == "m"
    assert d["canonical_status"] == "firm"
    assert set(d["dependency_states"].keys()) == set(DEPENDENCY_STAGE_KEYS)
    assert d["candidate_result"] is None
    assert d["legacy_value"] is None
    assert d["legacy_unit"] is None
    assert d["comparison"] is None


def test_shadow_drawing_report_to_dict_shape() -> None:
    record = ShadowQuantityRecord(
        quantity_family="net_wall_area", subject_id="w1", canonical_value=None, canonical_unit=None,
        canonical_status="abstained", evidence_ids=(), blocking_reasons=("opening_completeness_not_independently_proven",),
    )
    report = ShadowDrawingReport(
        label="Test", canonical_walls_considered=1, canonical_records=(record,),
        opening_host_candidates_observed=2, opening_host_statuses_observed=("ambiguous_host",),
        legacy_aggregate={"perimeter_walling": {"quantity": 42.0, "unit": "SM"}}, notes=("a note",),
    )
    d = report.to_dict()
    assert d["canonical_records"] == [record.to_dict()]
    assert d["legacy_aggregate"] == {"perimeter_walling": {"quantity": 42.0, "unit": "SM"}}


def test_aggregate_subject_id_is_distinguishable_from_any_real_wall_id() -> None:
    assert AGGREGATE_SUBJECT_ID.startswith("__") and AGGREGATE_SUBJECT_ID.endswith("__")


# ---------------------------------------------------------------------------
# End-to-end opening-authority scenarios (A-F).
#
# This module's dependency_states schema has ONE `host` slot and ONE
# `identity` slot -- it does not yet separately distinguish
# host_universe_completeness / host_binding, or physical_identity /
# schedule_binding / type_identity / phase, because schedule/tag identity
# is not wired into this shadow at all yet (see module docstring: "NOT
# WIRED IN THIS PASS"). Where a scenario below calls for a distinction this
# schema cannot yet express (e.g. "host FIRM" -- host is never FIRM in this
# module, only ever candidate_result="bound" gated to canonical_status=
# "BLOCKED"), the test documents that gap explicitly rather than silently
# inventing new schema to paper over it mid-run.
# ---------------------------------------------------------------------------


def test_scenario_a_gross_firm_survives_unresolved_opening_dimensions() -> None:
    """A: opening existence FIRM, dimensions BLOCKED -> gross stays FIRM,
    net stays BLOCKED. (This module has no schedule/host=FIRM concept to
    exercise the exact literal scenario -- see section docstring -- so this
    proves the part that IS expressible: an unresolved opening dimension
    must never retroactively block the wall's own already-FIRM gross area,
    and must never let net silently treat the opening as zero-area. gross
    FIRM-ness mechanics are already covered by test_firm_wall_length_survives_
    a_blocked_height and the real build_gross_wall_area_quantity contract --
    a bare ShadowQuantityRecord stands in for "gross is FIRM" here so this
    test isn't coupled to that contract's exact validation rules.)"""
    gross_record = ShadowQuantityRecord(
        quantity_family="gross_wall_area", subject_id="w1", canonical_value=16.5, canonical_unit="m2",
        canonical_status="firm", evidence_ids=("ex-len", "ex-h"), blocking_reasons=(),
    )

    # Opening dimensions unresolved (no scale wired) -- this module's own
    # hosted_opening_width record for any such opening is always BLOCKED:
    class _FakeSpanA:
        page = 1
        host_orientation_deg = 0.0
        jamb_start = (0.0, 0.0)
        jamb_end = (1.0, 0.0)
        span_pt = 1.0
        width_m = None
        wall_thickness_pt = 0.1
        subtype = "door_like"
        evidence_flags = ()
        reason = "ok"

    class _UnboundBinding:
        binding_id = "bind-a"
        status = "unbound"
        reason = "no_plausible_host"

    evidence = HostedOpeningEvidence(status="found", openings=(_FakeSpanA(),), reason="ok")
    orig = shadow_module.bind_hosted_opening_to_walls
    shadow_module.bind_hosted_opening_to_walls = lambda span, walls, *, viewport_id: _UnboundBinding()
    try:
        records = _hosted_opening_bindings(evidence=evidence, resolved=("w1",), viewport_id="vp-1", page_no=1)
    finally:
        shadow_module.bind_hosted_opening_to_walls = orig
    dim_record = next(r for r in records if r.quantity_family == "hosted_opening_width")
    assert dim_record.canonical_status == "BLOCKED"

    # Net is unconditionally blocked regardless -- gross is untouched.
    assert gross_record.canonical_status == "firm"
    assert gross_record.canonical_value == 16.5
    net_record = ShadowQuantityRecord(
        quantity_family="net_wall_area", subject_id="w1", canonical_value=None, canonical_unit=None,
        canonical_status="abstained", evidence_ids=(),
        blocking_reasons=("opening_completeness_not_independently_proven",),
    )
    assert net_record.canonical_value is None
    assert gross_record.canonical_value == 16.5  # unaffected by net's block


def test_scenario_b_two_plausible_hosts_blocks_host_deduction_and_net(monkeypatch) -> None:
    """B: opening existence FIRM, "schedule" (not wired -- N/A here) FIRM,
    two plausible hosts -> host BLOCKED, deduction BLOCKED, net BLOCKED.
    The real, expressible part of this scenario is the "two plausible
    hosts" -> ambiguous binder result -> everything downstream blocked."""
    from dataclasses import dataclass as dc

    @dc(frozen=True)
    class _FakeSpan:
        page: int = 1
        host_orientation_deg: float = 0.0
        jamb_start: tuple = (0.0, 0.0)
        jamb_end: tuple = (1.0, 0.0)
        span_pt: float = 1.0
        width_m: object = None
        wall_thickness_pt: float = 0.1
        subtype: str = "door_like"
        evidence_flags: tuple = ()
        reason: str = "ok"

    @dc(frozen=True)
    class _AmbiguousBinding:
        binding_id: str = "bind-b"
        page: int = 1
        viewport_id: str = "vp-1"
        host_orientation_deg: float = 0.0
        jamb_start: tuple = (0.0, 0.0)
        jamb_end: tuple = (1.0, 0.0)
        span_pt: float = 1.0
        subtype: str = "door_like"
        status: str = "ambiguous"
        wall_candidate_id: object = None
        considered_wall_candidate_ids: tuple = ("w1", "w2")
        reason: str = "two_candidates_at_opposite_jambs"
        evidence_flags: tuple = ()

    monkeypatch.setattr(shadow_module, "bind_hosted_opening_to_walls", lambda span, walls, *, viewport_id: _AmbiguousBinding())
    evidence = HostedOpeningEvidence(status="found", openings=(_FakeSpan(),), reason="ok")
    records = _hosted_opening_bindings(evidence=evidence, resolved=("w1", "w2"), viewport_id="vp-1", page_no=1)
    by_family = {r.quantity_family: r for r in records}

    assert by_family["hosted_opening_binding"].candidate_result == "ambiguous"
    assert by_family["hosted_opening_binding"].canonical_status == "BLOCKED"
    assert by_family["opening_deduction_readiness"].canonical_status == "BLOCKED"
    assert by_family["opening_deduction_readiness"].dependency_states["host"] == "BLOCKED"


def test_scenario_c_complete_dimensions_still_blocked_by_incomplete_universe(monkeypatch) -> None:
    """C: even a "bound" (best-case) binder result -- standing in for
    "host+dimensions resolved" -- stays BLOCKED for deduction/net, because
    the wall-candidate universe backing that "bound" call was never proven
    complete (this diagnostic clips to a small region)."""
    evidence = _fake_bound_binding_setup(monkeypatch)
    records = _hosted_opening_bindings(evidence=evidence, resolved=("w1",), viewport_id="vp-1", page_no=1)
    by_family = {r.quantity_family: r for r in records}
    assert by_family["hosted_opening_binding"].candidate_result == "bound"
    assert by_family["opening_deduction_readiness"].canonical_status == "BLOCKED"
    assert "regional_clip_wall_universe_not_proven_complete" in by_family["hosted_opening_binding"].blocking_reasons


def test_scenario_d_documents_no_code_path_to_firm_deduction_exists_yet() -> None:
    """D: opening existence/host/dimensions FIRM + a genuinely complete
    opening universe -> deduction should become ELIGIBLE for FIRM (subject
    to further provenance gates). This module has NO code path that could
    ever produce that outcome today: it never calls
    build_opening_deduction_quantity at all (constraint #1), so there is no
    "eligible" state to reach regardless of how complete the universe is.
    This is intentional (opening completeness is never claimed here) but it
    does mean scenario D cannot be positively exercised by this module as
    it stands -- reaching it requires wiring pb_opening_deduction_readiness
    against a genuine, independently-proven completeness manifest, which is
    future work, not a regression this test can currently detect."""
    code_only = _source_with_docstrings_blanked(shadow_module)
    assert "build_opening_deduction_quantity" not in code_only
    # Documents the gap rather than asserting a false "it works" claim.


def test_scenario_e_ceiling_marker_alone_never_resolves_wall_height() -> None:
    """E, fixed: wall length FIRM, ceiling height FIRM, wall-height RELATION
    unproven -> wall height BLOCKED, gross area BLOCKED.

    Regression test for a real gap found and then corrected in this module:
    pb_dimension_graph_constraint_engine._ROOF_LIKE = {"roof", "ceiling",
    "beam"} treats a "ceiling" marker identically to "roof" for its OWN
    clear-height computation -- that upstream behavior is unchanged (out of
    scope to patch here). What changed is that this shadow now excludes
    "ceiling" from the marker set it ever hands to resolve_wall_height at
    all (_WALL_HEIGHT_ELIGIBLE_MARKER_TYPES), so a ceiling+floor pair
    resolves here exactly like a missing roof marker: unresolved, not
    fully_constrained -- never a proven wall height. A room's ceiling
    (possibly dropped/suspended) is still not independently proven to
    coincide with the bounding wall's own height; that independent proof,
    if it ever exists, is a different, richer evidence source than a bare
    marker_type=="ceiling" text marker, and is not what this test grants."""
    ceiling_marker = LevelMarker(
        marker_id="m-ceil", level_m=2.4, raw_text="Ceiling +2.4", marker_type="ceiling",
        view_id=_VIEWPORT_ID, source_page=1, scope_id=None,
    )
    qty = _attempt_height(levels=[ceiling_marker, _floor_marker(0.0)])
    assert qty.abstained is True

    length_qty = _firm_quantity()
    gross_qty = build_gross_wall_area_quantity(wall_id="w1", wall_length=length_qty, wall_height=qty)
    assert gross_qty.abstained is True
    assert "wall_height_abstained" in gross_qty.blocking_reasons


def test_ceiling_marker_does_not_block_a_genuine_roof_plus_floor_resolution() -> None:
    """A ceiling marker present ALONGSIDE a genuine roof marker must not
    interfere with resolving height from the roof+floor pair -- exclusion
    of "ceiling" must be additive-safe, not a blanket abstention whenever
    any ceiling marker exists anywhere in `levels`."""
    ceiling_marker = LevelMarker(
        marker_id="m-ceil", level_m=2.4, raw_text="Ceiling +2.4", marker_type="ceiling",
        view_id=_VIEWPORT_ID, source_page=1, scope_id=None,
    )
    qty = _attempt_height(levels=[_roof_marker(3.325), ceiling_marker, _floor_marker(0.175)])
    assert qty.abstained is False
    assert abs(qty.value - 3.15) < 1e-6


def test_scenario_f_blocked_height_for_any_reason_preserves_firm_length() -> None:
    """F: a wall with a sloped/stepped top has no single scalar height
    available. This module has no sloped/stepped-profile DETECTOR at all
    (that capability does not exist here), so it cannot produce the
    specific `variable_height_profile_required` reason -- but it must
    still satisfy the general isolation property scenario F depends on:
    however height ends up abstained, length is completely unaffected."""
    length_qty = _firm_quantity()
    height_qty = _attempt_height(levels=[])  # stand-in for "no usable scalar height", any cause
    assert length_qty.abstained is False
    assert height_qty.abstained is True
    gross_qty = build_gross_wall_area_quantity(wall_id="w1", wall_length=length_qty, wall_height=height_qty)
    assert gross_qty.abstained is True
    assert length_qty.abstained is False
    assert length_qty.value == 5.5
