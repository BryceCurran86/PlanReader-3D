"""Only actual live publisher output counts; original words are not authority."""
from hashlib import sha256

import fitz
import pytest

from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import EvidenceResolutionStatus
from tools.diag_gpt1_mary_window_area_live_firstgate import (
    TARGETS, diagnose_actual_window_area_gates,
)


def _pdf(*, duplicate=False, missing_elevation=False):
    d = fitz.open()
    try:
        for i in range(29):
            page = d.new_page()
            if i == 6:
                for j, mark in enumerate(TARGETS):
                    page.insert_text((40, 80 + j*30), mark)
                if duplicate:
                    page.insert_text((40, 225), "W01")
            if i == 28 and not missing_elevation:
                for j, mark in enumerate(TARGETS):
                    page.insert_text((40, 80 + j*30), mark)
        return d.tobytes()
    finally:
        d.close()


def _claim(canonical=(), quantities=()):
    # Construct an actual typed claim without authority or signed publication.
    return LivePhysicalNetWallClaim(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(), quantity_m2=None,
        source_pages=(), canonical_walls=(),
        canonical_wall_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_wall_reason_codes=(), canonical_wall_source_pages=(),
        unresolved_wall_candidate_ids=(),
        canonical_openings=tuple(canonical), canonical_rooms=(),
        canonical_floors=(),
        canonical_floor_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_floor_reason_codes=(), canonical_floor_source_pages=(),
        canonical_room_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_room_reason_codes=(), canonical_room_source_pages=(),
        external_wall_ids=(), evidence_ids=(), quantity_id=None,
        confidence=0.0, publication=object(),
        opening_quantity_evidence=tuple(quantities),
    )


def _run(pdf, claim):
    return diagnose_actual_window_area_gates(pdf, sha256(pdf).hexdigest(), claim)


def test_native_words_with_no_real_opening_do_not_issue_window_area():
    report = _run(_pdf(), _claim())
    assert report["benchmark_score_granted"] is False
    assert report["customer_seal_granted"] is False
    assert report["real_issuer_quantity_inventory"] == 0
    assert all(w["first_missing_gate"] == "physical_type_mark_binding_unavailable"
               for w in report["windows"])


def test_duplicate_or_missing_mark_cannot_select_physical_window():
    for kwargs in ({"duplicate":True}, {"missing_elevation":True}):
        report = _run(_pdf(**kwargs), _claim())
        assert report["windows"][0]["first_missing_gate"] == (
            "original_native_mark_unavailable_or_ambiguous"
        )


def test_source_sha_mismatch_fails_closed():
    pdf = _pdf()
    with pytest.raises(ValueError, match="source sha256 mismatch"):
        diagnose_actual_window_area_gates(pdf, "0"*64, _claim())


def test_issuer_report_never_uses_original_measurements_as_quantity():
    report = _run(_pdf(), _claim())
    assert report["not_source_authority"] is True
    assert report["measurement_published_by_this_tool"] is False
    assert all(w["quantity_id"] is None for w in report["windows"])


def test_untrusted_claim_shape_refused():
    pdf = _pdf()
    with pytest.raises(TypeError, match="actual LivePhysicalNetWallClaim"):
        _run(pdf, object())
