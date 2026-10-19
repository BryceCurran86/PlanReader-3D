"""Source-issued architectural schedule area, NEVER a net construction takeoff.

One ORIGINAL PDF schedule repeated on drawing sheets represents one set of
architectural declared quantities, not one quantity per repeated title block.
Only native glyph-backed, fully balanced, SHA-pinned schedules can mint source-
semantic FIRM records. Physical floor/finish/commercial authority remains false.
No expected benchmark value, project-specific area, height or geometry default.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re

from pb_migration_contracts import QuantityEvidence, stable_contract_id
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import seal_source_closed_run

_AREA_RE = re.compile(r"^(?P<amount>[0-9]{1,6}\.[0-9]{2})\s*(?:m²|m2)$", re.I)
_LABEL_RE = re.compile(r"^[A-Z][A-Z0-9 /&-]{1,79}$")
_HEADING = "AREA CALCULATIONS"


@dataclass(frozen=True)
class NativeScheduledArea:
    label: str
    amount_m2: Decimal
    row_number: int
    word_ids_by_page: tuple[tuple[int, tuple[str, ...]], ...]


@dataclass(frozen=True)
class NativeArchitecturalScheduleResult:
    status: str
    reason_codes: tuple[str, ...]
    source_sha256: str
    rows: tuple[NativeScheduledArea, ...] = ()
    total_m2: Decimal | None = None
    repeated_source_pages: tuple[int, ...] = ()
    quantities: tuple[QuantityEvidence, ...] = ()
    sealed_run: object | None = None
    customer_release_allowed: bool = False
    canonical_physical_floor_bound: bool = False


def _reject(sha: str, reason: str) -> NativeArchitecturalScheduleResult:
    return NativeArchitecturalScheduleResult("ABSTAIN", (reason,), sha)


def _native_receipts(page, block_no: int, lines: tuple[str, ...], page_no: int):
    """Require independent original native word addresses and visible text paint."""
    words = [w for w in page.get_text("words")
             if len(w) >= 8 and w[5] == block_no]
    if not words:
        return None
    # Numeric and label must each have native words in the SAME source block.
    native = defaultdict(list)
    for word in words:
        native[int(word[6])].append(word)
    native_lines = tuple(
        (line_no, tuple(sorted(line, key=lambda w: w[7])))
        for line_no, line in sorted(native.items())
    )
    if len(native_lines) != len(lines):
        return None
    for (_, line_words), expected in zip(native_lines, lines):
        if "".join(w[4] for w in line_words).casefold() != (
            "".join(expected.split()).casefold()
        ):
            return None
    # Both text and paint must exist. Neither a copied value nor an invisible
    # text layer is sufficient. This is SOURCE-SCHEDULE authority, not a floor.
    rect = page.get_text("blocks")[block_no]
    bx0, by0, bx1, by1 = rect[:4]
    text_runs = []
    for trace in page.get_texttrace():
        x0, y0, x1, y1 = trace["bbox"]
        if (x0 >= bx0 - 1 and y0 >= by0 - 2
                and x1 <= bx1 + 1 and y1 <= by1 + 2):
            if trace.get("type") != 0 or trace.get("opacity") != 1.0:
                return None
            try:
                text_runs.append("".join(chr(glyph[0]) for glyph in trace["chars"]))
            except (ValueError, TypeError, OverflowError):
                return None
    painted = "".join(text_runs).replace(" ", "").casefold()
    for label_or_value in lines:
        if "".join(label_or_value.split()).casefold() not in painted:
            return None
    return tuple(
        (line_no, tuple(
            f"p{page_no}:b{block_no}:l{line_no}:w{int(w[7])}"
            for w in line_words
        )) for line_no, line_words in native_lines
    )


def _page_schedule(page, page_no: int):
    blocks = page.get_text("blocks")
    headings = [
        (i, block) for i, block in enumerate(blocks)
        if len(block) > 6 and block[6] == 0
        and _HEADING in (block[4] or "").upper()
    ]
    if len(headings) != 1:
        return None
    heading = headings[0][1]
    tables = []
    for index, block in enumerate(blocks):
        if len(block) <= 6 or block[6] != 0 or index == headings[0][0]:
            continue
        if not (heading[1] < block[1] < heading[1] + 45):
            continue
        raw = tuple(line.strip() for line in block[4].splitlines() if line.strip())
        if len(raw) < 6 or len(raw) % 2:
            continue
        if raw[-2].rstrip(":").upper() != "TOTAL":
            continue
        categories = raw[0:-2:2]
        values = raw[1:-2:2]
        if not 2 <= len(categories) <= 20:
            continue
        if any(_LABEL_RE.fullmatch(label) is None for label in categories):
            continue
        if len(set(label.casefold() for label in categories)) != len(categories):
            continue
        if any(_AREA_RE.fullmatch(value) is None for value in values + (raw[-1],)):
            continue
        try:
            amounts = tuple(
                Decimal(_AREA_RE.fullmatch(value)["amount"]) for value in values
            )
            total = Decimal(_AREA_RE.fullmatch(raw[-1])["amount"])
        except (InvalidOperation, ValueError, TypeError):
            continue
        if sum(amounts, Decimal(0)) != total:
            continue
        receipt_lines = _native_receipts(page, index, raw, page_no)
        if receipt_lines is None:
            continue
        tables.append((categories, amounts, total, receipt_lines))
    return tables[0] if len(tables) == 1 else None


def issue_native_scheduled_areas(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    project_id: str, workspace_id: int,
) -> NativeArchitecturalScheduleResult:
    """Issue genuine *source-declared* m²; never a scored/customer floor area."""
    if type(original_pdf_bytes) is not bytes or not original_pdf_bytes:
        raise ValueError("original source PDF bytes required")
    digest = sha256(original_pdf_bytes).hexdigest()
    if type(expected_sha256) is not str or digest != expected_sha256.lower():
        return _reject(digest, "original_source_sha256_mismatch")
    if (type(project_id) is not str or not project_id
            or project_id.strip() != project_id
            or type(workspace_id) is not int or workspace_id <= 0):
        return _reject(digest, "typed_project_scope_unavailable")
    try:
        import fitz
        pdf = fitz.open(stream=original_pdf_bytes, filetype="pdf")
    except Exception:
        return _reject(digest, "original_pdf_unreadable")
    schedule = None
    pages = []
    addresses = {}
    try:
        if pdf.is_encrypted or pdf.page_count < 1:
            return _reject(digest, "original_pdf_unreadable")
        for pageno in range(pdf.page_count):
            page = pdf.load_page(pageno)
            # Heading alone does not establish a schedule. A page with such
            # a heading but no unique balanced source-authenticated table
            # makes the entire document's declared area universe ambiguous.
            if _HEADING not in page.get_text().upper():
                continue
            evidence = _page_schedule(page, pageno + 1)
            if evidence is None:
                return _reject(digest, "original_area_schedule_missing_or_ambiguous")
            labels, amounts, total, word_receipts = evidence
            current = (tuple(labels), tuple(amounts), total)
            if schedule is None:
                schedule = current
            elif current != schedule:
                return _reject(digest, "repeated_area_schedule_source_conflict")
            pages.append(pageno + 1)
            for i, (_, words) in enumerate(word_receipts):
                addresses[(pageno + 1, i)] = words
    finally:
        pdf.close()
    if schedule is None or not pages:
        return _reject(digest, "original_area_schedule_unavailable")
    labels, amounts, total = schedule
    document_id = "original-source:" + digest[:32]
    revision_id = "original-sha:" + digest[:32]
    source_viewport = "native-architectural-schedule"
    quantities, traces, rows = [], {}, []
    for index, (label, amount) in enumerate(zip(labels, amounts)):
        # Each category appears only once physically even if the same source
        # title block is drawn on every sheet. Page copies are corroboration.
        # Zero-based table positions: category 2*i, value 2*i+1.
        receipts = tuple(
            word for page in pages for k in (2 * index, 2 * index + 1)
            for word in addresses[(page, k)]
        )
        if not receipts or len(set(receipts)) != len(receipts):
            return _reject(digest, "source_row_word_identity_conflict")
        source_id = stable_contract_id("native_schedule_row", {
            "sha256": digest, "heading": _HEADING, "row": index + 1,
            "label": label, "amount": str(amount),
        }, digest_chars=32)
        quantity = QuantityEvidence(
            quantity_id=stable_contract_id("source_scheduled_area", {
                "source_row": source_id, "sha256": digest,
            }, digest_chars=32),
            family="architectural_scheduled_area",
            semantic_key="architectural_scheduled_area:" + source_id,
            value=float(amount), unit="m2",
            input_entity_ids=(source_id,),
            formula="original_native_declared_area_schedule_not_net_floor",
            formula_version="1.0.0",
            evidence_ids=receipts,
            authority="original_pdf_explicit_architectural_area_schedule",
            status="firm", confidence=1.0, abstained=False,
            metadata={
                "project_id": project_id, "document_id": document_id,
                "source_sha256": digest, "revision_id": revision_id,
                "source_pages": tuple(pages), "source_area_label": label,
                "source_declared_area_m2": str(amount),
                "quantity_handoff_only": True, "shadow_only": False,
                "commercial_projection_allowed": False,
                "canonical_physical_floor_owner_authenticated": False,
                "floor_finish_authority": False,
                "repeated_title_block_not_physical_instance": True,
            },
        )
        traces[quantity.quantity_id] = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id, project_id=project_id,
            document_id=document_id, source_sha256=digest,
            source_page=str(pages[0]), viewport_id=source_viewport,
            revision_id=revision_id, current_revision_id=revision_id,
            evidence_ids=receipts, canonical_entity_ids=(source_id,),
            metadata={"source_role": "architectural_declared_area",
                      "source_pages": pages, "not_customer_release": True},
        )
        rows.append(NativeScheduledArea(label, amount, index + 1, tuple(
            (page, tuple(
                word for k in (2 * index, 2 * index + 1)
                for word in addresses[(page, k)]
            )) for page in pages
        )))
        quantities.append(quantity)
    sealed_run = seal_source_closed_run(
        tuple(quantities), project_id=project_id, traces_by_quantity_id=traces
    )
    if (len(sealed_run.quantities) != len(quantities)
            or not all(row.lineage_ok and not row.abstained
                       for row in sealed_run.quantities)):
        return _reject(digest, "source_declared_area_sealing_unavailable")
    return NativeArchitecturalScheduleResult(
        "SOURCE_FIRM_HANDOFF_ONLY",
        ("verified_native_printed_area_not_physical_takeoff",),
        digest, tuple(rows), total, tuple(pages),
        tuple(quantities), sealed_run,
    )
