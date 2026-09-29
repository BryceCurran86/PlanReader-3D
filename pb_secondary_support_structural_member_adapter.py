"""Adapt corroborated secondary-area physical support evidence into structural-member authority."""
from __future__ import annotations

from dataclasses import dataclass

from pb_secondary_area_support_evidence import SecondaryAreaSupportEvidence
from pb_structural_member_authority import (
    StructuralMemberProducer,
    StructuralMemberResolution,
    StructuralMemberSelector,
    StructuralMemberObservation,
    StructuralMemberViewScope,
)


@dataclass(frozen=True)
class SecondarySupportStructuralMemberResult:
    selector: StructuralMemberSelector
    resolution: StructuralMemberResolution


def _member_kind(evidence: SecondaryAreaSupportEvidence) -> str:
    kind = str(evidence.support_kind or "").strip().lower()
    if kind in {"column", "pillar", "post", "pier"}:
        return kind
    return "structural_support"


def build_secondary_support_structural_member_authority(
    *,
    evidence: SecondaryAreaSupportEvidence,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    decision_scope_id: str,
    view_id: str,
    view_complete: bool,
) -> SecondarySupportStructuralMemberResult:
    """Publish physical-member identities only from proven physical support symbols.

    Text/bay-count evidence without physical symbol ids never creates instances.
    """
    selector = StructuralMemberSelector(
        document_id=str(document_id),
        revision_id=str(revision_id),
        source_sha256=str(source_sha256),
        snapshot_id=str(snapshot_id),
        decision_scope_id=str(decision_scope_id),
        member_kind=_member_kind(evidence),
    )

    physical_ids = tuple(str(value) for value in evidence.support_symbol_ids)
    physical_row_consistent = (
        evidence.evidence_mode == "physical_symbol"
        and bool(physical_ids)
        and len(physical_ids) == int(evidence.support_count)
        and len(evidence.source_pages) == 1
    )
    if not physical_row_consistent:
        resolution = StructuralMemberProducer.from_authenticated_evidence(
            selector=selector,
            observations=(),
            view_scopes=(),
        ).publish()
        return SecondarySupportStructuralMemberResult(selector, resolution)

    page_id = str(evidence.source_pages[0])
    observations = tuple(
        StructuralMemberObservation(
            observation_id=f"structural-member:{symbol_id}",
            member_kind=selector.member_kind,
            page_id=page_id,
            view_id=str(view_id),
            view_type="plan",
            source_evidence_ids=tuple(sorted({
                str(symbol_id),
                *(str(chain_id) for chain_id in evidence.chain_ids),
            })),
            source_primitive_ids=(str(symbol_id),),
        )
        for symbol_id in physical_ids
    )
    scope_reasons = () if view_complete else ("secondary_support_view_incomplete",)
    resolution = StructuralMemberProducer.from_authenticated_evidence(
        selector=selector,
        observations=observations,
        relations=(),
        view_scopes=(
            StructuralMemberViewScope(
                page_id=page_id,
                view_id=str(view_id),
                view_type="plan",
                complete=bool(view_complete),
                reason_codes=scope_reasons,
            ),
        ),
    ).publish()
    return SecondarySupportStructuralMemberResult(selector, resolution)
