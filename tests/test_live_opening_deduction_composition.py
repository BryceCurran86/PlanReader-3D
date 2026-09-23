from __future__ import annotations

import fitz

from pb_live_opening_deduction_composition import (
    LIVE_OPENING_DEDUCTION_RESOLVED,
    compose_live_opening_deductions,
)
from pb_live_physical_opening_void_composition import (
    compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_deduction_authority import OPENING_DEDUCTION_AUTHORIZED
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


TARGET_ID = "wall-finish-1"
TARGET_TOKEN = (
    "ODTARGET(target=wall-finish-1,opening=W1,trade=PAINT,"
    "finish=LOW-SHEEN,assembly=INT-WALL)"
)
RULE_TOKEN = (
    "ODRULE(target=wall-finish-1,opening=W1,trade=PAINT,"
    "finish=LOW-SHEEN,assembly=INT-WALL,id=project-mom,version=1,"
    "decision={decision})"
)


def _deduction_pdf(*, decision: str = "DEDUCT") -> bytes:
    raw = _complete_void_pdf()
    doc = fitz.open(stream=raw, filetype="pdf")
    try:
        page = doc.load_page(0)
        # Keep these source declarations outside the opening schedule region.
        page.insert_text(fitz.Point(20.0, 340.0), TARGET_TOKEN, fontsize=4.5)
        page.insert_text(
            fitz.Point(20.0, 360.0),
            RULE_TOKEN.format(decision=decision),
            fontsize=4.5,
        )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _compose(*, decision: str = "DEDUCT", target_scope_id: str = TARGET_ID):
    source = SourceVisibilityProducer(
        producer_method="live-opening-deduction-composition-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-opening-deduction",
        source_bytes=_deduction_pdf(decision=decision),
        source_locator="memory://live-opening-deduction.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    assert wall_opening.status is EvidenceResolutionStatus.CORROBORATED

    physical_void = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    assert physical_void.status is EvidenceResolutionStatus.CORROBORATED

    deductions = compose_live_opening_deductions(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
        target_scope_ids=(target_scope_id,),
    )
    return deductions


def test_live_composition_resolves_source_owned_opening_deduction() -> None:
    composition = _compose()

    assert composition.status is EvidenceResolutionStatus.CORROBORATED
    assert composition.reason_codes == (LIVE_OPENING_DEDUCTION_RESOLVED,)
    assert composition.target_scope_ids == (TARGET_ID,)
    assert len(composition.traces) == 1

    trace = composition.traces[0]
    assert trace.target_scope_id == TARGET_ID
    assert trace.target_status is EvidenceResolutionStatus.CORROBORATED
    assert trace.target_record_id
    assert trace.rule_status is EvidenceResolutionStatus.CORROBORATED
    assert trace.rule_record_id
    assert trace.applicability_status is EvidenceResolutionStatus.CORROBORATED
    assert trace.applicability_record_id
    assert trace.deduction_status is EvidenceResolutionStatus.CORROBORATED
    assert trace.deduction_record_id
    assert OPENING_DEDUCTION_AUTHORIZED in trace.deduction_reason_codes

    selector = composition.deduction_selectors[
        (trace.opening_identity_id, TARGET_ID)
    ]
    authority = composition.deduction_authorities[trace.page_id]
    replay = authority.resolve(selector)
    assert replay.status is EvidenceResolutionStatus.CORROBORATED
    assert replay.record is not None
    assert replay.record.record_id == trace.deduction_record_id
    assert replay.record.applicability_record_id == trace.applicability_record_id


def test_retain_rule_never_becomes_deduction_authority() -> None:
    composition = _compose(decision="RETAIN")

    assert composition.status is not EvidenceResolutionStatus.CORROBORATED
    assert len(composition.traces) == 1
    trace = composition.traces[0]
    assert trace.rule_status is EvidenceResolutionStatus.CORROBORATED
    assert trace.applicability_status is not EvidenceResolutionStatus.CORROBORATED
    assert trace.applicability_record_id is None
    assert trace.deduction_status is not EvidenceResolutionStatus.CORROBORATED
    assert trace.deduction_record_id is None


def test_unknown_target_address_cannot_borrow_source_target_authority() -> None:
    composition = _compose(target_scope_id="different-target")

    assert composition.status is not EvidenceResolutionStatus.CORROBORATED
    assert len(composition.traces) == 1
    trace = composition.traces[0]
    assert trace.target_scope_id == "different-target"
    assert trace.target_status is not EvidenceResolutionStatus.CORROBORATED
    assert trace.target_record_id is None
    assert trace.applicability_status is not EvidenceResolutionStatus.CORROBORATED
    assert trace.applicability_record_id is None
    assert trace.deduction_status is not EvidenceResolutionStatus.CORROBORATED
    assert trace.deduction_record_id is None
