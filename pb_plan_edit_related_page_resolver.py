"""Bridge producer-owned cross-sheet authority to PlanReader revision pages.

The caller must supply a COMPLETE, independently indexed page candidate
universe for the canonical original physical element. This module does not
search page labels, match IDs by appearance, or assume all sheets contain
the same wall. Each related page must have a positive producer-owned cross-
sheet registration result. An unresolved candidate blocks the whole revision.

Handles ONE source PDF/document SHA at a time. Cross-file drawing sets need
a separately authenticated multi-document revision transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from pb_cross_sheet_registration_authority import (
    CrossSheetRegistrationAuthority, CrossSheetRegistrationSelector,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_plan_edit_revision_bundle import SourcePageLink, RelatedPageCoverage
from pb_editable_3d_correction_model import EditableGeometryObject
from pb_vr_editor_scene_manifest import EditorWorkspaceScope, VerifiedSourceWitness


@dataclass(frozen=True)
class IndependentlyIndexedPage:
    page_index: int
    page_id: str
    sheet: str
    physical_element_id: str
    original_native_geometry_ref: str

    def __post_init__(self):
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("related_page_index_invalid")
        if not all(type(value) is str and value for value in (
            self.page_id, self.sheet, self.physical_element_id,
            self.original_native_geometry_ref,
        )):
            raise ValueError("related_page_independent_source_receipt_missing")


def corroborated_related_page_coverage(
    *, scope: EditorWorkspaceScope, edited: EditableGeometryObject,
    witness: VerifiedSourceWitness, canonical_object_id: str,
    source_physical_element_id: str,
    origin_page_index: int,
    related_candidates: Sequence[IndependentlyIndexedPage],
    page_universe_complete: bool,
    registration: CrossSheetRegistrationAuthority,
) -> RelatedPageCoverage:
    """Require an externally complete candidate universe AND registration.

    A positive registration verifies real callout + source/target physical
    object. It cannot be manufactured merely from a matching canonical ID.
    """
    if type(registration) is not CrossSheetRegistrationAuthority:
        raise ValueError("producer_owned_cross_sheet_authority_required")
    if page_universe_complete is not True:
        raise ValueError("related_page_candidate_universe_unresolved")
    if not witness.matches(scope, edited):
        raise ValueError("original_source_page_witness_invalid")
    if not isinstance(canonical_object_id, str) or not canonical_object_id:
        raise ValueError("canonical_element_required")
    if not isinstance(source_physical_element_id, str) or not source_physical_element_id:
        raise ValueError("source_physical_element_proof_missing")
    if type(origin_page_index) is not int or origin_page_index < 0:
        raise ValueError("source_page_index_unproven")
    if len(related_candidates) > 699:
        raise ValueError("related_page_candidate_cap_exceeded")
    first = SourcePageLink(
        page_index=origin_page_index,
        page_label=str(edited.source_page), sheet=edited.source_sheet,
        document_id=scope.document_id, revision_id=scope.revision_id,
        source_sha256=scope.source_sha256,
        snapshot_id=scope.snapshot_id,
        canonical_object_id=canonical_object_id,
        native_geometry_ref=edited.original_geometry_ref,
        relationship="origin", producer_status="original_source",
        evidence_ids=(f"source:{scope.source_sha256}:{edited.original_geometry_ref}",),
    )
    links = [first]
    seen_pages = {origin_page_index}
    for candidate in related_candidates:
        if type(candidate) is not IndependentlyIndexedPage:
            raise ValueError("untrusted_related_page_candidate")
        if candidate.page_index in seen_pages:
            raise ValueError("duplicated_or_self_cross_sheet_page")
        seen_pages.add(candidate.page_index)
        selector = CrossSheetRegistrationSelector(
            document_id=scope.document_id, revision_id=scope.revision_id,
            source_sha256=scope.source_sha256, snapshot_id=scope.snapshot_id,
            source_page_id=str(edited.source_page),
            target_page_id=candidate.page_id,
            physical_element_id=source_physical_element_id,
        )
        outcome = registration.resolve(selector)
        record = outcome.record
        if (outcome.status is not EvidenceResolutionStatus.CORROBORATED or
            record is None or
            record.document_id != scope.document_id or
            record.revision_id != scope.revision_id or
            record.source_sha256.lower() != scope.source_sha256.lower() or
            record.snapshot_id != scope.snapshot_id or
            record.source_page_id != str(edited.source_page) or
            record.target_page_id != candidate.page_id or
            record.physical_element_id != source_physical_element_id or
            record.target_physical_element_id != candidate.physical_element_id or
            record.referenced_sheet_code != candidate.sheet or
            not record.callout_mark or not record.record_id):
            raise ValueError("unresolved_cross_sheet_registration")
        links.append(SourcePageLink(
            page_index=candidate.page_index, page_label=candidate.page_id,
            sheet=candidate.sheet,
            document_id=scope.document_id, revision_id=scope.revision_id,
            source_sha256=scope.source_sha256, snapshot_id=scope.snapshot_id,
            canonical_object_id=canonical_object_id,
            native_geometry_ref=candidate.original_native_geometry_ref,
            relationship="cross_sheet", producer_status="corroborated",
            evidence_ids=(record.record_id,
                          f"callout:{record.callout_mark}",
                          f"target:{candidate.physical_element_id}"),
        ))
    return RelatedPageCoverage(
        document_id=scope.document_id, revision_id=scope.revision_id,
        source_sha256=scope.source_sha256, snapshot_id=scope.snapshot_id,
        canonical_object_id=canonical_object_id,
        links=tuple(sorted(links, key=lambda link: link.page_index)),
        known_related_page_indices=tuple(sorted(seen_pages)),
        complete=True,
    )
