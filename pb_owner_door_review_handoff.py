"""Owner-approved door review, project handoff library (default off; used only when an approvals file is supplied).

What this adds
--------------
* ``load_owner_door_height_approvals``: a strict loader for an explicit owner approvals file.  Each entry becomes the same
  ``MeasurementRecord`` that layer A (``pb_door_height_owner_gate_shadow``) and layer B
  (``pb_owner_approved_door_review_promotion``) already re-verify, so the file grants nothing by itself: the approver, the
  timezone-aware date, the page, the document hash, the bounds, the retained height and "exactly one per opening" are all
  re-checked downstream.  The two axes are fixed by the schema (printed width, approved height); the file cannot choose them.
* ``assess_owner_door_review``: builds the review candidates from a composition and keeps only openings that the standard claim
  of the same run also proves (a review row must not outlive the claim it has to agree with), seals them and verifies the sealed
  run against its rows.
* ``run_owner_door_review_step``: re-derives the opening composition with the claim collector's own page scope and producer
  options, for the approved pages only.

What this does not do
---------------------
It never changes the claim, any family run, the combined run, customer rows or a status.  Its output is a separate estimator-review
run (origin AI, "To review", all three commercial gates closed): not FIRM, not CORROBORATED, not publishable, not priced.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from pb_customer_output_verification import verify_sealed_customer_output
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType, MeasurementRecord
from pb_live_physical_opening_void_composition import LivePhysicalOpeningVoidComposition
from pb_owner_approved_door_review_promotion import (
    build_owner_approved_door_review_candidates,
    seal_owner_approved_door_review_run,
)
from pb_quantity_takeoff_adapter import existing_commercial_gate_results
from pb_source_closed_run_export import SealedSourceClosedRun

OWNER_DOOR_HEIGHT_APPROVALS_SCHEMA_VERSION = "1.0.0"
MAX_APPROVALS_FILE_BYTES = 1_048_576
REVIEW_DIRNAME = "owner_door_review"
REVIEW_RUN_FILENAME = "owner_door_review.sealed.json"
REVIEW_ROWS_FILENAME = "verified_owner_door_review_rows.json"

GATE_VERIFIED = "OWNER_DOOR_REVIEW_VERIFIED"
GATE_NO_CANDIDATES = "NO_REVIEW_CANDIDATES"
GATE_NOT_RUN = "OWNER_DOOR_REVIEW_NOT_RUN"
REASON_NOT_IN_STANDARD_CLAIM = "opening_not_in_standard_claim"

TEMPLATE_FILENAME = "owner_door_height_approvals_template.json"
GATE_TEMPLATE_READY = "OWNER_DOOR_APPROVALS_TEMPLATE_READY"
GATE_TEMPLATE_NO_DOORS = "NO_DOOR_OPENINGS_FOR_TEMPLATE"
GATE_TEMPLATE_NOT_RUN = "OWNER_DOOR_APPROVALS_TEMPLATE_NOT_RUN"

_SHA256 = re.compile(r"[0-9a-f]{64}")
_TOP_KEYS = frozenset({"schema_version", "source_sha256", "approvals"})
_ENTRY_KEYS = frozenset({"physical_opening_id", "page", "height_mm", "approved_by", "approved_at"})
_NATIVE_TEXT_SWITCHES = frozenset({"source_native_finish_text_shadow", "source_glyph_ledger_text_trust"})
_OWNER_BASIS = "owner_approved_second_axis"


class OwnerDoorHeightApprovalsError(ValueError):
    """The approvals file is not an acceptable explicit owner input."""


@dataclass(frozen=True)
class OwnerDoorHeightApprovals:
    records: tuple[MeasurementRecord, ...]
    pages: tuple[int, ...]
    file_sha256: str


@dataclass(frozen=True)
class OwnerDoorReviewOutcome:
    gate: str
    run: Optional[SealedSourceClosedRun]
    rows: tuple[Mapping[str, Any], ...]
    candidate_count: int
    withheld_counts: Mapping[str, int]
    unused_approval_count: int
    approval_pages_out_of_scope: tuple[int, ...] = ()


@dataclass(frozen=True)
class OwnerDoorApprovalsTemplateOutcome:
    """An approvals file with every owner field blank, or the typed reason there is nothing to list."""

    gate: str
    document: Optional[Mapping[str, Any]]
    door_count: int
    pages: tuple[int, ...]


# ----------------------------------------------------------------------------------------------- approvals file

def _is_sha256(value: object) -> bool:
    return type(value) is str and _SHA256.fullmatch(value) is not None


def _no_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise OwnerDoorHeightApprovalsError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _reject_constant(name: str) -> Any:
    raise OwnerDoorHeightApprovalsError(f"non-finite JSON literal: {name}")


def _canonical_text(value: object, field: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise OwnerDoorHeightApprovalsError(f"{field} must be a non-empty, trimmed string")
    return value


def _entry_record(entry: object, source_sha256: str) -> MeasurementRecord:
    if type(entry) is not dict or set(entry) != _ENTRY_KEYS:
        raise OwnerDoorHeightApprovalsError("each approval must be an object with exactly the schema keys")
    opening_id = _canonical_text(entry["physical_opening_id"], "physical_opening_id")
    approver = _canonical_text(entry["approved_by"], "approved_by")
    stamp_text = _canonical_text(entry["approved_at"], "approved_at")
    page, height = entry["page"], entry["height_mm"]
    if type(page) is not int or page <= 0:
        raise OwnerDoorHeightApprovalsError("page must be a positive integer")
    if type(height) not in (int, float) or not math.isfinite(height) or height <= 0:
        raise OwnerDoorHeightApprovalsError("height_mm must be a finite positive number")
    try:
        stamp = datetime.fromisoformat(stamp_text)
    except ValueError as exc:
        raise OwnerDoorHeightApprovalsError("approved_at must be an ISO-8601 timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise OwnerDoorHeightApprovalsError("approved_at must carry a timezone offset")
    return MeasurementRecord(
        value=float(height), unit="mm", source_type=MeasurementAuthorityType.USER_APPROVED.value, confidence=1.0,
        sheet="", page=page, scale="", geometry_ref=opening_id,
        authority_status=AuthorityStatus.USER_APPROVED.value, approved_by=approver, approved_at=stamp_text,
        metadata={"second_axis": "height", "single_figure_axis": "width", "source_sha256": source_sha256},
    )


def load_owner_door_height_approvals(path: object, *, source_sha256: str) -> OwnerDoorHeightApprovals:
    """Load an explicit owner approvals file bound to one document hash; refuse anything that is not exactly the schema."""
    if not _is_sha256(source_sha256):
        raise OwnerDoorHeightApprovalsError("source_sha256 must be a lowercase 64-hex digest")
    try:
        file_path = Path(path)  # type: ignore[arg-type]
    except TypeError as exc:
        raise OwnerDoorHeightApprovalsError("approvals path must be a path") from exc
    if file_path.is_symlink():
        raise OwnerDoorHeightApprovalsError("approvals file must not be a symlink")
    if not file_path.is_file():
        raise OwnerDoorHeightApprovalsError("approvals file not found")
    with file_path.open("rb") as handle:
        raw = handle.read(MAX_APPROVALS_FILE_BYTES + 1)
    if len(raw) > MAX_APPROVALS_FILE_BYTES:
        raise OwnerDoorHeightApprovalsError("approvals file size exceeds the cap")
    try:
        document = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant)
    except OwnerDoorHeightApprovalsError:
        raise
    except (ValueError, RecursionError) as exc:       # UnicodeDecodeError and JSONDecodeError are ValueErrors
        raise OwnerDoorHeightApprovalsError("approvals file is not valid UTF-8 JSON") from exc
    if type(document) is not dict or set(document) != _TOP_KEYS:
        raise OwnerDoorHeightApprovalsError("approvals file must be an object with exactly the schema keys")
    if document["schema_version"] != OWNER_DOOR_HEIGHT_APPROVALS_SCHEMA_VERSION:
        raise OwnerDoorHeightApprovalsError("unsupported approvals schema_version")
    if document["source_sha256"] != source_sha256:
        raise OwnerDoorHeightApprovalsError("approvals file is bound to a different document")
    entries = document["approvals"]
    if type(entries) is not list:
        raise OwnerDoorHeightApprovalsError("approvals must be a list")
    records = tuple(_entry_record(entry, source_sha256) for entry in entries)
    return OwnerDoorHeightApprovals(
        records=records,
        pages=tuple(sorted({int(record.page) for record in records})),
        file_sha256=hashlib.sha256(raw).hexdigest(),
    )


# ----------------------------------------------------------------------------------------------- page scope

def claim_page_scope(
    page_count: int,
    pages: Optional[Sequence[int]],
    topology_pages: Optional[Sequence[int]],
    room_area_support_pages: Optional[Sequence[int]],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """(decoded, topology, evidence) page ids exactly as ``collect_live_physical_net_wall_claim`` derives them.

    The same selection function is used, so identity of the ingested source and of the composed pages cannot drift.
    """
    from pb_live_physical_net_wall_integration import _selected_page_indices

    selected = _selected_page_indices(page_count, pages)
    if topology_pages is None:
        topology_selected = selected
    else:
        topology_selected = _selected_page_indices(page_count, topology_pages)
        if not set(topology_selected) <= set(selected):
            raise ValueError("topology_pages must be a subset of pages")
    support = () if room_area_support_pages is None else _selected_page_indices(page_count, room_area_support_pages)
    decoded = tuple(sorted(set(selected) | set(support)))

    def ids(indices: Sequence[int]) -> tuple[str, ...]:
        return tuple(str(index + 1) for index in indices)

    topology_ids = ids(topology_selected)
    evidence_ids = tuple(page_id for page_id in ids(selected) if page_id not in topology_ids)
    return ids(decoded), topology_ids, evidence_ids


# ----------------------------------------------------------------------------------------------- assessment

def _claim_opening_ids(claim: object) -> frozenset[str]:
    openings = getattr(claim, "canonical_openings", None)
    if not isinstance(openings, (list, tuple)):
        return frozenset()
    ids: set[str] = set()
    for opening in openings:
        identity = getattr(opening, "canonical_opening_id", None)
        if type(identity) is str and identity and identity == identity.strip():
            ids.add(identity)
    return frozenset(ids)


def assess_owner_door_review(
    composition: LivePhysicalOpeningVoidComposition,
    *,
    approvals: Sequence[MeasurementRecord],
    claim: object,
    workspace_id: int,
    project_id: str,
    source_sha256: str,
) -> OwnerDoorReviewOutcome:
    """Candidates -> claim identity cross-check -> sealed review run -> customer-output verification."""
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    if not _is_sha256(source_sha256):
        raise ValueError("source_sha256 must be a lowercase 64-hex digest")
    collection = build_owner_approved_door_review_candidates(
        composition, approvals=approvals, workspace_id=workspace_id, project_id=project_id)

    claim_ids = _claim_opening_ids(claim)
    kept = tuple(
        candidate for candidate in collection.candidates
        if len(candidate.promoted_quantity.input_entity_ids) == 1
        and candidate.promoted_quantity.input_entity_ids[0] in claim_ids
    )
    withheld = Counter(item.reason_code for item in collection.withheld)
    withheld[REASON_NOT_IN_STANDARD_CLAIM] += len(collection.candidates) - len(kept)
    withheld_counts = {reason: count for reason, count in sorted(withheld.items()) if count}

    owner_basis_ids = {
        opening.canonical_opening_id for opening in composition.canonical_openings if opening.area_basis == _OWNER_BASIS}
    unused = sum(1 for record in approvals if record.geometry_ref not in owner_basis_ids)

    if not kept:
        return OwnerDoorReviewOutcome(GATE_NO_CANDIDATES, None, (), 0, withheld_counts, unused)

    run = seal_owner_approved_door_review_run(kept, project_id=project_id)
    if set(run.source_sha256s) != {source_sha256}:
        raise RuntimeError("review run source envelope differs from the handoff source")
    rows = tuple(
        dict(candidate.review_row)
        for candidate in sorted(kept, key=lambda item: item.promoted_quantity.quantity_id))
    verified = verify_sealed_customer_output(run, list(rows))
    sealed_ids = {quantity.quantity_id for quantity in run.quantities}
    if (
        len(sealed_ids) != len(run.quantities)
        or len(rows) != len(sealed_ids)
        or set(verified.verified_quantity_ids) != sealed_ids
        or verified.customer_row_count != len(sealed_ids)
    ):
        raise RuntimeError("review rows and sealed review run disagree")
    if any(quantity.abstained or not quantity.lineage_ok for quantity in run.quantities):
        raise RuntimeError("review run holds a quantity without exact lineage")
    if any(result[0] for row in rows for result in existing_commercial_gate_results(row).values()):
        raise RuntimeError("an unreviewed door row is commercially authorised")
    return OwnerDoorReviewOutcome(GATE_VERIFIED, run, rows, len(kept), withheld_counts, unused)


# ----------------------------------------------------------------------------------------------- source step

def compose_owner_approved_opening_voids(
    pdf_bytes: bytes,
    *,
    source_sha256: str,
    decoded_page_ids: Sequence[str],
    topology_page_ids: Sequence[str],
    evidence_page_ids: Sequence[str],
    approvals: Sequence[MeasurementRecord],
    native_text_kwargs: Mapping[str, bool],
    single_width_uniform_page_door_height_shadow: bool = False,
) -> LivePhysicalOpeningVoidComposition:
    """Re-derive the opening composition exactly as the claim collector does, with the owner approvals as an explicit extra input.

    ``single_width_uniform_page_door_height_shadow`` must be the value the claim collector ran with: a door the claim already
    measured from a source-printed uniform page door height must not look unmeasured here (and so must not be offered for, or
    given, an owner-assumed height).
    """
    from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
    from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
        **dict(native_text_kwargs),
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{source_sha256[:32]}",
        source_bytes=pdf_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=tuple(decoded_page_ids),
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=tuple(topology_page_ids),
        evidence_page_ids=tuple(evidence_page_ids),
    )
    return compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        owner_approved_second_axis=tuple(approvals),
        single_width_uniform_page_door_height_shadow=single_width_uniform_page_door_height_shadow,
    )


def _validated_native_text_kwargs(value: object) -> dict[str, bool]:
    if not isinstance(value, Mapping):
        raise TypeError("native_text_kwargs must be a mapping")
    if any(key not in _NATIVE_TEXT_SWITCHES or item is not True for key, item in value.items()):
        raise ValueError("native_text_kwargs may only switch on the claim collector's explicit text options")
    return dict(value)


def run_owner_door_review_step(
    pdf_path: object,
    *,
    approvals: OwnerDoorHeightApprovals,
    claim: object,
    workspace_id: int,
    project_id: str,
    source_sha256: str,
    page_count: int,
    pages: Optional[Sequence[int]],
    topology_pages: Optional[Sequence[int]],
    room_area_support_pages: Optional[Sequence[int]],
    native_text_kwargs: Mapping[str, bool],
    single_width_uniform_page_door_height_shadow: bool = False,
) -> OwnerDoorReviewOutcome:
    """Compose for the approved topology pages only, then assess against the run's own standard claim."""
    if type(approvals) is not OwnerDoorHeightApprovals:
        raise TypeError("approvals must be OwnerDoorHeightApprovals")
    text_kwargs = _validated_native_text_kwargs(native_text_kwargs)
    pdf_bytes = Path(pdf_path).read_bytes()  # type: ignore[arg-type]
    if hashlib.sha256(pdf_bytes).hexdigest() != source_sha256:
        raise RuntimeError("source PDF changed before the owner door review step")

    decoded, topology, evidence = claim_page_scope(page_count, pages, topology_pages, room_area_support_pages)
    in_scope = tuple(record for record in approvals.records if str(record.page) in topology)
    out_of_scope = tuple(record for record in approvals.records if str(record.page) not in topology)
    out_of_scope_pages = tuple(sorted({int(record.page) for record in out_of_scope}))
    if not in_scope:
        return OwnerDoorReviewOutcome(
            GATE_NO_CANDIDATES, None, (), 0, {}, len(out_of_scope), out_of_scope_pages)

    composition = compose_owner_approved_opening_voids(
        pdf_bytes,
        source_sha256=source_sha256,
        decoded_page_ids=decoded,
        topology_page_ids=topology,
        evidence_page_ids=evidence,
        approvals=in_scope,
        native_text_kwargs=text_kwargs,
        single_width_uniform_page_door_height_shadow=single_width_uniform_page_door_height_shadow,
    )
    outcome = assess_owner_door_review(
        composition, approvals=in_scope, claim=claim, workspace_id=workspace_id,
        project_id=project_id, source_sha256=source_sha256)
    return replace(
        outcome,
        unused_approval_count=outcome.unused_approval_count + len(out_of_scope),
        approval_pages_out_of_scope=out_of_scope_pages,
    )


# ----------------------------------------------------------------------------------------------- approvals template

def build_owner_door_approvals_template(
    composition: LivePhysicalOpeningVoidComposition,
    *,
    claim: object,
    source_sha256: str,
) -> OwnerDoorApprovalsTemplateOutcome:
    """List the doors an owner could approve, in the approvals-file shape, with every owner field left ``null``.

    A door is listed when it is a door, has no area of its own yet, and is also an opening of the same run's standard claim (the
    review step would withhold it otherwise).  Nothing here says the door is eligible: whether it prints exactly one authenticated
    figure is only decided when an approval is assessed, and an approval for an ineligible door is reported as unused.  No height,
    approver or date is produced; the loader refuses the file until the owner has filled every entry they keep.
    """
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    if not _is_sha256(source_sha256):
        raise ValueError("source_sha256 must be a lowercase 64-hex digest")
    claim_ids = _claim_opening_ids(claim)
    pages_by_id: dict[str, int] = {}
    for opening in composition.canonical_openings:
        if opening.opening_kind != "door" or opening.area_m2 is not None:
            continue
        if opening.source_sha256 != source_sha256:
            raise RuntimeError("composed opening belongs to a different document")
        identity = opening.canonical_opening_id
        if identity not in claim_ids:
            continue
        page_text = opening.page_id
        if (
            type(page_text) is not str
            or not page_text.isascii()
            or not page_text.isdigit()
            or str(int(page_text)) != page_text
            or int(page_text) <= 0
        ):
            raise RuntimeError("composed opening has a page id that is not a positive page number")
        if identity in pages_by_id:
            raise RuntimeError("composed openings repeat a canonical opening id")
        pages_by_id[identity] = int(page_text)
    if not pages_by_id:
        return OwnerDoorApprovalsTemplateOutcome(GATE_TEMPLATE_NO_DOORS, None, 0, ())
    entries = [
        {"physical_opening_id": identity, "page": page, "height_mm": None, "approved_by": None, "approved_at": None}
        for identity, page in sorted(pages_by_id.items(), key=lambda item: (item[1], item[0]))
    ]
    document = {
        "schema_version": OWNER_DOOR_HEIGHT_APPROVALS_SCHEMA_VERSION,
        "source_sha256": source_sha256,
        "approvals": entries,
    }
    return OwnerDoorApprovalsTemplateOutcome(
        GATE_TEMPLATE_READY, document, len(entries), tuple(sorted(set(pages_by_id.values()))))


def run_owner_door_approvals_template_step(
    pdf_path: object,
    *,
    claim: object,
    source_sha256: str,
    page_count: int,
    pages: Optional[Sequence[int]],
    topology_pages: Optional[Sequence[int]],
    room_area_support_pages: Optional[Sequence[int]],
    native_text_kwargs: Mapping[str, bool],
    single_width_uniform_page_door_height_shadow: bool = False,
) -> OwnerDoorApprovalsTemplateOutcome:
    """Compose with the claim collector's page scope and options and no approvals, then list the possible door approvals."""
    text_kwargs = _validated_native_text_kwargs(native_text_kwargs)
    pdf_bytes = Path(pdf_path).read_bytes()  # type: ignore[arg-type]
    if hashlib.sha256(pdf_bytes).hexdigest() != source_sha256:
        raise RuntimeError("source PDF changed before the owner door approvals template step")
    decoded, topology, evidence = claim_page_scope(page_count, pages, topology_pages, room_area_support_pages)
    composition = compose_owner_approved_opening_voids(
        pdf_bytes,
        source_sha256=source_sha256,
        decoded_page_ids=decoded,
        topology_page_ids=topology,
        evidence_page_ids=evidence,
        approvals=(),
        native_text_kwargs=text_kwargs,
        single_width_uniform_page_door_height_shadow=single_width_uniform_page_door_height_shadow,
    )
    return build_owner_door_approvals_template(composition, claim=claim, source_sha256=source_sha256)


__all__ = [
    "GATE_NOT_RUN",
    "GATE_NO_CANDIDATES",
    "GATE_TEMPLATE_NOT_RUN",
    "GATE_TEMPLATE_NO_DOORS",
    "GATE_TEMPLATE_READY",
    "GATE_VERIFIED",
    "MAX_APPROVALS_FILE_BYTES",
    "OWNER_DOOR_HEIGHT_APPROVALS_SCHEMA_VERSION",
    "OwnerDoorApprovalsTemplateOutcome",
    "OwnerDoorHeightApprovals",
    "OwnerDoorHeightApprovalsError",
    "OwnerDoorReviewOutcome",
    "REASON_NOT_IN_STANDARD_CLAIM",
    "REVIEW_DIRNAME",
    "REVIEW_ROWS_FILENAME",
    "REVIEW_RUN_FILENAME",
    "TEMPLATE_FILENAME",
    "assess_owner_door_review",
    "build_owner_door_approvals_template",
    "claim_page_scope",
    "compose_owner_approved_opening_voids",
    "load_owner_door_height_approvals",
    "run_owner_door_approvals_template_step",
    "run_owner_door_review_step",
]
