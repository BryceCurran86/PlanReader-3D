"""Source-safe, multi-page *review revision* PDF generation for PlanReader.

The new PDF is an immutable, annotated working copy. It does not pretend that
changing a wall in the 3D model automatically redraws that wall accurately on
an elevation/section. Only explicitly source-verified related pages are tagged.
No original PDF, original-SHA authority or commercial measurement is altered.

Proof of *all* related pages must come from a trusted source registration
provider. A browser cannot supply either links or a coverage-complete flag.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
import re
from typing import Optional

import fitz

from pb_editable_3d_correction_model import EditableGeometryObject
from pb_vr_editor_scene_manifest import EditorWorkspaceScope, VerifiedSourceWitness

_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
_MAX_PDF = 80 * 1024 * 1024
_MAX_PAGES = 700
_MAX_LINKS = 700
_MAX_PDF_OUT = 100 * 1024 * 1024


@dataclass(frozen=True)
class SourcePageLink:
    """A producer-attested physical correspondence on one PDF page.

    page_index is 0-based PDF index, independently mapped by the producer.
    page_label is the ORIGINAL source identity (not inferred from page_index).
    For related sheets, independent cross-reference, source and target receipts
    must each be present. Same geometry mark or canonical ID alone is NOT proof.
    """
    page_index: int
    page_label: str
    sheet: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    canonical_object_id: str
    native_geometry_ref: str
    relationship: str  # "origin" or "cross_sheet"
    producer_status: str  # "original_source" or "corroborated"
    evidence_ids: tuple[str, ...]
    # Optional producer-attested region in PDF page coordinates; never guessed.
    pdf_region: Optional[tuple[float, float, float, float]] = None

    def __post_init__(self):
        for field in ("page_label", "sheet", "document_id", "revision_id",
                      "snapshot_id", "canonical_object_id", "native_geometry_ref"):
            value = getattr(self, field)
            if type(value) is not str or not value or len(value) > 256:
                raise ValueError("revision_page_source_identity_invalid:" + field)
        if type(self.page_index) is not int or not 0 <= self.page_index < _MAX_PAGES:
            raise ValueError("revision_pdf_page_index_invalid")
        if type(self.source_sha256) is not str or not _SHA.fullmatch(self.source_sha256):
            raise ValueError("revision_source_sha_invalid")
        if self.relationship not in ("origin", "cross_sheet"):
            raise ValueError("revision_page_relationship_invalid")
        expected = "original_source" if self.relationship == "origin" else "corroborated"
        if self.producer_status != expected:
            raise ValueError("revision_cross_page_proof_unverified")
        if (type(self.evidence_ids) is not tuple or
            len(self.evidence_ids) < (1 if self.relationship == "origin" else 3) or
            any(type(s) is not str or not s or s != s.strip()
                or len(s) > 256 for s in self.evidence_ids) or
            len(set(self.evidence_ids)) != len(self.evidence_ids)):
            raise ValueError("revision_page_independent_evidence_missing")
        if self.pdf_region is not None:
            r = self.pdf_region
            if (type(r) is not tuple or len(r) != 4 or
                any(type(x) not in (int, float) or not math.isfinite(float(x))
                    for x in r) or r[2] <= r[0] or r[3] <= r[1]):
                raise ValueError("revision_page_region_invalid")


@dataclass(frozen=True)
class RelatedPageCoverage:
    """Must be returned by an independent server-side correspondence resolver.

    known_related_page_indices is the FULL discovered related-page universe.
    Missing/ambiguous pages block saving an allegedly complete drawing set.
    """
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    canonical_object_id: str
    links: tuple[SourcePageLink, ...]
    known_related_page_indices: tuple[int, ...]
    complete: bool
    unresolved_page_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class RevisedPlanPdf:
    bytes: bytes
    sha256: str
    original_sha256: str
    related_pages: tuple[dict, ...]
    revision_label: str


def _validated_links(scope: EditorWorkspaceScope, edited: EditableGeometryObject,
                     witness: VerifiedSourceWitness, canonical_id: str,
                     coverage: RelatedPageCoverage, page_count: int):
    if type(coverage) is not RelatedPageCoverage or coverage.complete is not True:
        raise ValueError("cross_page_universe_not_proven_complete")
    if (coverage.document_id != scope.document_id or
        coverage.revision_id != scope.revision_id or
        coverage.snapshot_id != scope.snapshot_id or
        coverage.source_sha256.lower() != scope.source_sha256.lower() or
        coverage.canonical_object_id != canonical_id):
        raise ValueError("cross_page_coverage_source_scope_mismatch")
    if not witness.matches(scope, edited):
        raise ValueError("edited_source_witness_mismatch")
    if (type(coverage.links) is not tuple or not 1 <= len(coverage.links) <= _MAX_LINKS or
        type(coverage.known_related_page_indices) is not tuple or
        type(coverage.unresolved_page_indices) is not tuple or
        coverage.unresolved_page_indices):
        raise ValueError("cross_page_unresolved_or_excessive")
    expected = coverage.known_related_page_indices
    indices = tuple(sorted(link.page_index for link in coverage.links))
    if (not expected or len(set(expected)) != len(expected) or
        any(type(idx) is not int or idx < 0 or idx >= page_count for idx in expected) or
        tuple(sorted(expected)) != indices or len(set(indices)) != len(indices)):
        raise ValueError("cross_page_missing_duplicate_or_out_of_pdf")
    origins = [link for link in coverage.links if link.relationship == "origin"]
    if len(origins) != 1:
        raise ValueError("edited_original_page_link_missing_or_ambiguous")
    origin = origins[0]
    if (origin.page_label != str(edited.source_page) or
        origin.sheet != edited.source_sheet or
        origin.native_geometry_ref != edited.original_geometry_ref or
        origin.canonical_object_id != canonical_id):
        raise ValueError("edited_original_page_link_mismatch")
    for link in coverage.links:
        if (link.document_id != scope.document_id or
            link.revision_id != scope.revision_id or
            link.source_sha256.lower() != scope.source_sha256.lower() or
            link.snapshot_id != scope.snapshot_id or
            link.canonical_object_id != canonical_id):
            raise ValueError("cross_page_link_lineage_mismatch")
        if link.relationship == "cross_sheet" and link.page_index == origin.page_index:
            raise ValueError("cross_page_self_registration_invalid")
    return tuple(sorted(coverage.links, key=lambda link: link.page_index))


def render_related_page_revision(
    original_pdf_bytes: bytes, *,
    scope: EditorWorkspaceScope,
    edited: EditableGeometryObject,
    witness: VerifiedSourceWitness,
    canonical_object_id: str,
    coverage: RelatedPageCoverage,
    revision_label: str,
    correction_field: str,
    prior_value: object,
    new_value: object,
) -> RevisedPlanPdf:
    """Render visible revision notes on all registered related source pages.

    The source PDF's existing content/pages are never rewritten in place.
    This adds a review annotation and optional reviewed-region outline.
    It does not redraw original physical wall/opening lines or infer an elevation.
    """
    if type(original_pdf_bytes) is not bytes or not 1 <= len(original_pdf_bytes) <= _MAX_PDF:
        raise ValueError("original_pdf_bytes_required_or_too_large")
    original_sha = sha256(original_pdf_bytes).hexdigest()
    if original_sha != scope.source_sha256.lower():
        raise ValueError("original_pdf_sha_mismatch")
    if not re.fullmatch(r"PR-R[0-9]{4,6}", revision_label):
        raise ValueError("revision_label_invalid")
    if type(correction_field) is not str or not 1 <= len(correction_field) <= 64:
        raise ValueError("revision_correction_field_invalid")
    if len(str(prior_value)) > 80 or len(str(new_value)) > 80:
        raise ValueError("revision_change_value_too_long")
    try:
        document = fitz.open(stream=original_pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("source_pdf_invalid") from exc
    try:
        if document.needs_pass or document.is_encrypted or document.is_form_pdf:
            raise ValueError("encrypted_or_form_pdf_revision_requires_manual_workflow")
        if not 1 <= document.page_count <= _MAX_PAGES:
            raise ValueError("pdf_page_count_unsafe")
        links = _validated_links(
            scope, edited, witness, canonical_object_id, coverage,
            document.page_count,
        )
        pages = []
        for link in links:
            page = document[link.page_index]
            box = page.rect
            # Only add source-bound REVIEW annotations; never obscure
            # construction dimensions by redrawing source geometry.
            stamp_width = min(360.0, max(120.0, box.width * 0.50))
            stamp_height = min(54.0, max(30.0, box.height * 0.085))
            location = fitz.Rect(
                box.x1 - stamp_width - 6, box.y0 + 6,
                box.x1 - 6, box.y0 + 6 + stamp_height,
            )
            label = (
                f"{revision_label} | PLANREADER REVIEW REVISION\n"
                f"{correction_field}: {str(prior_value)[:46]} -> {str(new_value)[:46]}\n"
                "Cross-page coordination note; drawing geometry NOT redrawn."
            )
            annot = page.add_freetext_annot(
                location, label, fontsize=7, fontname="Helv",
                text_color=(0.30, 0.03, 0.03),
                fill_color=(1.0, 0.97, 0.83),
                border_color=(0.70, 0.30, 0.12),
            )
            annot.set_info(
                title="PlanReader - unapproved working revision",
                subject=revision_label,
                content=label,
            )
            annot.update()
            if link.pdf_region is not None:
                target = fitz.Rect(*link.pdf_region)
                if not box.contains(target):
                    raise ValueError("linked_original_region_outside_source_page")
                cloud = page.add_rect_annot(target)
                cloud.set_colors(stroke=(0.8, 0.2, 0.08))
                cloud.set_border(width=1.0, dashes=[2, 3])
                cloud.set_info(
                    title="PlanReader linked region - REVIEW only",
                    subject=revision_label,
                    content="Verified source location; revised geometry not redrawn",
                )
                cloud.update()
            pages.append({
                "pageIndex": link.page_index,
                "pageLabel": link.page_label,
                "sheet": link.sheet,
                "relationship": link.relationship,
                "originalGeometryRef": link.native_geometry_ref,
                "evidenceIds": list(link.evidence_ids),
                "geometryRedrawn": False,
                "requiresDrawingCoordination": True,
            })
        # Keep the original pages and attachments as far as PyMuPDF supports.
        rendered = document.tobytes(garbage=3, deflate=True)
        if len(rendered) > _MAX_PDF_OUT:
            raise ValueError("revised_pdf_too_large")
        return RevisedPlanPdf(
            bytes=rendered, sha256=sha256(rendered).hexdigest(),
            original_sha256=original_sha, related_pages=tuple(pages),
            revision_label=revision_label,
        )
    finally:
        document.close()
