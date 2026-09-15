"""C15 ceiling-lining governance: gold-free synthetic contract tests.

No benchmark IDs, expected BOQ quantities, scorer mappings, or project-specific
thresholds appear here.  These tests prove shadow-mode dependency governance:
same-scope explicit finish evidence + an already-authoritative finalized area,
or fail closed.
"""
from __future__ import annotations

import pytest

from pb_ceiling_lining_quantity import (
    build_ceiling_lining_quantity,
    resolve_ceiling_finish_entity,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext


SOURCE_SHA = "a" * 64
DOC_ID = "doc-c15"
PAGE_ID = "page-1"
VIEWPORT_ID = "vp-floor-1"
SCOPE_ID = "room-1"
REVISION_ID = "rev-1"


def _context(**overrides) -> ProviderContext:
    values = {
        "run_id": "run-c15",
        "workspace_id": "workspace-c15",
        "project_id": "project-c15",
        "document_id": DOC_ID,
        "source_sha256": SOURCE_SHA,
        "revision_id": REVISION_ID,
        "current_revision_id": REVISION_ID,
        "selected_pages": (0,),
        "owned_viewport_ids": (VIEWPORT_ID,),
        "evidence_snapshot_id": "snapshot-c15",
        "owned_page_numbers": (1,),
        "viewport_page_ownership": ((VIEWPORT_ID, 1),),
    }
    values.update(overrides)
    return ProviderContext(**values)


def _document(*evidence_ids: str) -> DocumentEvidence:
    ids = evidence_ids or ("ev-area", "ev-ceiling")
    return DocumentEvidence(
        document_id=DOC_ID,
        source_sha256=SOURCE_SHA,
        page_count=1,
        page_ids=(PAGE_ID,),
        evidence_ids=tuple(ids),
        producer="synthetic-c15",
        producer_version="1",
    )


def _viewport(**overrides) -> ViewportEvidence:
    values = {
        "viewport_id": VIEWPORT_ID,
        "document_id": DOC_ID,
        "page_id": PAGE_ID,
        "bbox": (0.0, 0.0, 600.0, 800.0),
        "view_type": "floor_plan",
        "status": ViewportResolutionStatus.RESOLVED,
        "evidence_ids": ("ev-area", "ev-ceiling"),
        "confidence": 1.0,
    }
    values.update(overrides)
    return ViewportEvidence(**values)


def _finish_atom(
    *,
    evidence_id: str = "ev-ceiling",
    raw_text: str = "CEILING FINISH: 12mm gypsum plasterboard",
    scope_id: str = SCOPE_ID,
    viewport_id: str = VIEWPORT_ID,
    page_id: str = PAGE_ID,
    document_id: str = DOC_ID,
    method: str = "native_pdf_text",
    kind: str = "ceiling_finish",
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.RAW,
) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=evidence_id,
        document_id=document_id,
        page_id=page_id,
        kind=kind,
        method=method,
        viewport_id=viewport_id,
        raw_text=raw_text,
        confidence=0.97,
        status=status,
        metadata={"scope_entity_id": scope_id},
    )


def _area_quantity(
    *,
    quantity_id: str = "qty-area-room-1",
    value: float = 42.375,
    family: str = "room_area",
    unit: str = "m2",
    scope_id: str = SCOPE_ID,
    status: str = AuthorityStatus.FIRM.value,
    authority: str = MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
    blocking_reasons: tuple[str, ...] = (),
    viewport_id: str = VIEWPORT_ID,
    revision_id: str = REVISION_ID,
    source_sha256: str = SOURCE_SHA,
    page_no: int = 1,
) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family=family,
        semantic_key=f"{family}:{scope_id}",
        value=value,
        unit=unit,
        input_entity_ids=(scope_id,),
        formula="synthetic_authoritative_area",
        formula_version="1",
        evidence_ids=("ev-area",),
        authority=authority,
        status=status,
        confidence=0.99,
        blocking_reasons=blocking_reasons,
        metadata={
            "source_sha256": source_sha256,
            "revision_id": revision_id,
            "page_no": page_no,
            "viewport_id": viewport_id,
        },
    )


def _build(
    *,
    area: QuantityEvidence | None = None,
    finish_atoms: tuple[EvidenceAtom, ...] | None = None,
    scope_id: str = SCOPE_ID,
    context: ProviderContext | None = None,
    document: DocumentEvidence | None = None,
    viewport: ViewportEvidence | None = None,
):
    return build_ceiling_lining_quantity(
        scope_entity_id=scope_id,
        area_quantity=_area_quantity() if area is None else area,
        finish_evidence_atoms=(_finish_atom(),) if finish_atoms is None else finish_atoms,
        context=_context() if context is None else context,
        document=_document("ev-area", "ev-ceiling") if document is None else document,
        viewport=_viewport() if viewport is None else viewport,
        page_no=1,
    )


def test_same_scope_explicit_finish_reuses_final_area_exactly_but_stays_shadow() -> None:
    area = _area_quantity(value=42.375)
    result = _build(area=area)

    assert result.value == 42.375
    assert result.value == area.value
    assert result.family == "ceiling_lining"
    assert result.semantic_key == f"ceiling_lining:{SCOPE_ID}"
    assert result.authority == MeasurementAuthorityType.MODEL_DERIVED.value
    assert result.status == AuthorityStatus.PROVISIONAL.value
    assert result.status != AuthorityStatus.FIRM.value
    assert result.abstained is False
    assert result.metadata["shadow_only"] is True
    assert result.metadata["commercial_projection_allowed"] is False
    assert result.metadata["upstream_area_quantity_id"] == area.quantity_id
    assert result.metadata["upstream_area_status"] == AuthorityStatus.FIRM.value


def test_area_only_cannot_create_ceiling_quantity() -> None:
    result = _build(finish_atoms=())

    assert result.abstained is True
    assert result.value is None
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "missing_explicit_ceiling_finish" in result.blocking_reasons


def test_explicit_finish_without_area_blocks() -> None:
    result = build_ceiling_lining_quantity(
        scope_entity_id=SCOPE_ID,
        area_quantity=None,
        finish_evidence_atoms=(_finish_atom(),),
        context=_context(),
        document=_document("ev-ceiling"),
        viewport=_viewport(evidence_ids=("ev-ceiling",)),
        page_no=1,
    )

    assert result.abstained is True
    assert result.value is None
    assert "missing_authoritative_area_quantity" in result.blocking_reasons


@pytest.mark.parametrize(
    "status",
    [
        AuthorityStatus.PROVISIONAL.value,
        AuthorityStatus.REVIEW_REQUIRED.value,
        AuthorityStatus.BLOCKED.value,
        AuthorityStatus.REFERENCE_ONLY.value,
    ],
)
def test_non_authoritative_upstream_area_never_promotes(status: str) -> None:
    area = _area_quantity(status=status)
    result = _build(area=area)

    assert result.abstained is True
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "upstream_area_not_authoritative" in result.blocking_reasons


def test_upstream_area_with_blockers_is_not_consumed_even_if_marked_firm() -> None:
    area = _area_quantity(blocking_reasons=("upstream_conflict",))
    result = _build(area=area)

    assert result.abstained is True
    assert "upstream_area_carries_blockers" in result.blocking_reasons


def test_scope_mismatch_blocks_floor_to_ceiling_copy() -> None:
    area = _area_quantity(scope_id="room-other")
    result = _build(area=area)

    assert result.abstained is True
    assert "upstream_area_scope_mismatch" in result.blocking_reasons


def test_same_scope_finish_bound_to_different_coordinate_frame_blocks() -> None:
    wrong_frame = _finish_atom(viewport_id="vp-other")
    result = _build(finish_atoms=(wrong_frame,))

    assert result.abstained is True
    assert "finish_coordinate_frame_mismatch" in result.blocking_reasons


def test_upstream_area_bound_to_different_coordinate_frame_blocks() -> None:
    area = _area_quantity(viewport_id="vp-other")
    result = _build(area=area)

    assert result.abstained is True
    assert "upstream_area_coordinate_frame_mismatch" in result.blocking_reasons


def test_conflicting_explicit_ceiling_finishes_fail_closed() -> None:
    a = _finish_atom(
        evidence_id="ev-ceiling-a",
        raw_text="CEILING FINISH: 12mm gypsum plasterboard",
    )
    b = _finish_atom(
        evidence_id="ev-ceiling-b",
        raw_text="CEILING FINISH: acoustic mineral fibre tile",
    )
    doc = _document("ev-area", "ev-ceiling-a", "ev-ceiling-b")
    result = _build(finish_atoms=(a, b), document=doc)

    assert result.abstained is True
    assert result.value is None
    assert "conflicting_explicit_ceiling_finishes" in result.blocking_reasons


def test_generic_ceiling_height_text_is_not_finish_evidence() -> None:
    atom = _finish_atom(raw_text="CEILING LEVEL 2700 ABOVE FFL")
    result = _build(finish_atoms=(atom,))

    assert result.abstained is True
    assert "ceiling_finish_not_explicit" in result.blocking_reasons


def test_reference_to_unseen_schedule_is_not_explicit_finish_evidence() -> None:
    atom = _finish_atom(raw_text="CEILING FINISH: refer to schedule")
    result = _build(finish_atoms=(atom,))

    assert result.abstained is True
    assert "ceiling_finish_not_explicit" in result.blocking_reasons


def test_ocr_only_finish_is_retained_but_cannot_corroborate_this_slice() -> None:
    atom = _finish_atom(method="raster_ocr")
    result = _build(finish_atoms=(atom,))

    assert result.abstained is True
    assert (
        "ocr_only_ceiling_finish_requires_secondary_authority"
        in result.blocking_reasons
    )


def test_native_and_ocr_same_finish_can_corroborate_without_authority_escalation() -> None:
    native = _finish_atom(evidence_id="ev-native")
    ocr = _finish_atom(evidence_id="ev-ocr", method="raster_ocr")
    doc = _document("ev-area", "ev-native", "ev-ocr")
    result = _build(finish_atoms=(ocr, native), document=doc)

    assert result.abstained is False
    assert result.status == AuthorityStatus.PROVISIONAL.value
    assert result.value == _area_quantity().value
    assert set(result.metadata["finish_evidence_ids"]) == {"ev-native", "ev-ocr"}


def test_unrelated_other_scope_finish_does_not_change_resolution() -> None:
    relevant = _finish_atom(evidence_id="ev-relevant")
    unrelated = _finish_atom(
        evidence_id="ev-unrelated",
        scope_id="room-other",
        raw_text="CEILING FINISH: metal pan ceiling",
    )
    doc = _document("ev-area", "ev-relevant", "ev-unrelated")

    baseline = _build(finish_atoms=(relevant,), document=doc)
    expanded = _build(finish_atoms=(unrelated, relevant), document=doc)

    assert baseline.value == expanded.value
    assert baseline.status == expanded.status == AuthorityStatus.PROVISIONAL.value
    assert expanded.metadata["finish_evidence_ids"] == ("ev-relevant",)


def test_finish_evidence_input_order_is_deterministic() -> None:
    a = _finish_atom(evidence_id="ev-a")
    b = _finish_atom(
        evidence_id="ev-b",
        raw_text=" ceiling finish : 12MM   GYPSUM PLASTERBOARD ",
    )
    doc = _document("ev-area", "ev-a", "ev-b")

    left = _build(finish_atoms=(a, b), document=doc)
    right = _build(finish_atoms=(b, a), document=doc)

    assert left.to_dict() == right.to_dict()
    assert left.quantity_id == right.quantity_id


def test_replay_is_stable_and_does_not_mutate_inputs() -> None:
    area = _area_quantity()
    atom = _finish_atom()
    area_before = area.to_dict()
    atom_before = atom.to_dict()

    first = _build(area=area, finish_atoms=(atom,))
    second = _build(area=area, finish_atoms=(atom,))

    assert first.to_dict() == second.to_dict()
    assert area.to_dict() == area_before
    assert atom.to_dict() == atom_before


def test_stale_revision_blocks_even_with_otherwise_valid_evidence() -> None:
    context = _context(revision_id="rev-old", current_revision_id=REVISION_ID)
    result = _build(context=context)

    assert result.abstained is True
    assert "stale_revision" in result.blocking_reasons


def test_finish_evidence_must_be_owned_by_active_document() -> None:
    result = _build(document=_document("ev-area"))

    assert result.abstained is True
    assert "finish_evidence_not_owned_by_document" in result.blocking_reasons


def test_area_evidence_must_be_owned_by_active_document() -> None:
    result = _build(document=_document("ev-ceiling"))

    assert result.abstained is True
    assert "upstream_area_evidence_not_owned_by_document" in result.blocking_reasons


def test_wall_area_cannot_be_substituted_for_floor_or_footprint_area() -> None:
    result = _build(area=_area_quantity(family="wall_area"))

    assert result.abstained is True
    assert "upstream_quantity_not_floor_or_footprint_area" in result.blocking_reasons


def test_zero_or_negative_area_cannot_create_ceiling_quantity() -> None:
    # QuantityEvidence itself permits zero, so the dependent ceiling gate must
    # explicitly reject it as a physically unresolved/empty scope.
    result = _build(area=_area_quantity(value=0.0))

    assert result.abstained is True
    assert "upstream_area_invalid" in result.blocking_reasons


def test_resolved_output_does_not_publish_dependent_perimeter_fixture_wastage_or_roof() -> None:
    result = _build()

    assert result.family == "ceiling_lining"
    assert result.value == pytest.approx(42.375)
    excluded = set(result.metadata["dependent_claims_not_evaluated"])
    assert excluded == {
        "ceiling_perimeter_trim",
        "recessed_fixture_accessories",
        "commercial_wastage",
        "roof_area",
    }
    assert result.metadata["commercial_projection_allowed"] is False


def test_finish_entity_is_recomputed_from_atoms_not_caller_certified() -> None:
    atom = _finish_atom()
    entity = resolve_ceiling_finish_entity(
        evidence_atoms=(atom,),
        scope_entity_id=SCOPE_ID,
        context=_context(),
        document=_document("ev-area", "ev-ceiling"),
        viewport=_viewport(),
        page_no=1,
    )

    assert entity is not None
    assert entity.status == EvidenceResolutionStatus.CORROBORATED
    assert entity.metadata["finish_descriptor"] == "12mm gypsum plasterboard"
    assert entity.metadata["scope_entity_id"] == SCOPE_ID


def test_same_scope_finish_on_wrong_page_blocks_instead_of_cross_page_guessing() -> None:
    atom = _finish_atom(page_id="page-2")
    result = _build(finish_atoms=(atom,))

    assert result.abstained is True
    assert "finish_page_mismatch" in result.blocking_reasons


def test_upstream_area_page_mismatch_blocks() -> None:
    area = _area_quantity(page_no=2)
    result = _build(area=area)

    assert result.abstained is True
    assert "upstream_area_page_mismatch" in result.blocking_reasons


def test_missing_scope_id_blocks_without_guessing_identity() -> None:
    result = _build(scope_id="")

    assert result.abstained is True
    assert "scope_entity_id_missing" in result.blocking_reasons
