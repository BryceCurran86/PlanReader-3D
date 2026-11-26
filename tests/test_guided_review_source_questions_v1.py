"""Tests for source-owned guided review questions & review-to-issuer handoff contract."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import pytest

from pb_guided_review_source_questions import (
    GuidedSourceQuestionBundle,
    ReviewToIssuerHandoffReceipt,
    SourceSuggestionProvenance,
    build_guided_review_source_questions,
    build_review_to_issuer_handoff,
)

_SRC_SHA = "a" * 64
_IMG_SHA = "b" * 64
_REC_SHA_1 = "c" * 64
_REC_SHA_2 = "d" * 64
_VP = "vp-ground-floor-plan"


def _make_native_packet(
    *,
    source_sha: str = _SRC_SHA,
    pdf_page: int = 2,
    review_revision: int = 1,
    corrections: list[dict] | None = None,
    answers: dict | None = None,
    tamper: bool = False,
    commercial: bool = False,
    frozen: bool = False,
) -> dict:
    packet = {
        "schema_version": 1,
        "scope": {
            "workspace_id": 1,
            "page_id": 10,
            "pdf_page": pdf_page,
            "source_sha256": source_sha,
            "image_sha256": _IMG_SHA,
        },
        "review_revision": review_revision,
        "corrections": corrections if corrections is not None else [],
        "unbound_review_answers": answers if answers is not None else {},
        "affected_stage_candidates": ["scale", "finishes"],
        "status": "USER_CORRECTIONS_PENDING_CONSUMER",
        "automatic_source_verified": False,
        "commercial_projection_allowed": commercial,
        "frozen_benchmark_allowed": frozen,
        "topology_recalculated": False,
    }
    raw = json.dumps(packet, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    packet["packet_sha256"] = hashlib.sha256(raw).hexdigest()
    if tamper:
        packet["review_revision"] = review_revision + 1
    return packet


def test_source_questions_attach_provenance_without_inventing_missing_defaults() -> None:
    scale_sugg = SourceSuggestionProvenance(
        issue="scale",
        source_sha256=_SRC_SHA,
        pdf_page=2,
        viewport_id=_VP,
        evidence_kind="same_page_figured_scale_shadow",
        source_observation_ids=("obs_dim_1", "obs_dim_2"),
        candidate_receipt_sha256=_REC_SHA_1,
        suggested_summary="Same-page orthogonal figured spans suggest 1:100 in this viewport.",
    )
    bundle = build_guided_review_source_questions(
        source_sha256=_SRC_SHA,
        pdf_page=2,
        viewport_id=_VP,
        suggestions=(scale_sugg,),
        scale_verified=False,
        height_verified=False,
        finishes_verified=False,
        exclusions_verified=True,
    )
    assert isinstance(bundle, GuidedSourceQuestionBundle)
    assert bundle.status == "QUESTIONS_READY_FOR_USER_REVIEW"
    assert bundle.commercial_projection_allowed is False
    assert bundle.frozen_benchmark_allowed is False
    by_issue = {q.issue: q for q in bundle.questions}
    assert set(by_issue) == {"scale", "height", "finishes"}

    # Scale carries source candidate suggestion pending confirmation
    assert by_issue["scale"].status == "SOURCE_SUGGESTION_REQUIRES_CONFIRMATION"
    assert by_issue["scale"].suggestion == scale_sugg
    assert "pb_page_scale_calibration_authority" in by_issue["scale"].target_issuers

    # Height and finishes have NO fabricated default
    assert by_issue["height"].status == "SOURCE_EVIDENCE_MISSING_ASK_USER"
    assert by_issue["height"].suggestion is None
    assert by_issue["finishes"].status == "SOURCE_EVIDENCE_MISSING_ASK_USER"
    assert by_issue["finishes"].suggestion is None

    with pytest.raises(ValueError):
        replace(bundle, commercial_projection_allowed=True)
    with pytest.raises(ValueError):
        replace(scale_sugg, frozen_benchmark_allowed=True)


def test_conflicting_suggestions_and_scope_mismatch_fail_closed() -> None:
    s1 = SourceSuggestionProvenance(
        issue="height",
        source_sha256=_SRC_SHA,
        pdf_page=2,
        viewport_id=_VP,
        evidence_kind="rcp_spatial_ceiling_label_shadow",
        source_observation_ids=("obs_1",),
        candidate_receipt_sha256=_REC_SHA_1,
        suggested_summary="2700 mm ceiling note candidate",
    )
    s2 = SourceSuggestionProvenance(
        issue="height",
        source_sha256=_SRC_SHA,
        pdf_page=2,
        viewport_id=_VP,
        evidence_kind="section_height_candidate",
        source_observation_ids=("obs_2",),
        candidate_receipt_sha256=_REC_SHA_2,
        suggested_summary="2400 mm section note candidate",
    )
    bundle = build_guided_review_source_questions(
        source_sha256=_SRC_SHA,
        pdf_page=2,
        viewport_id=_VP,
        suggestions=(s1, s2),
        scale_verified=True,
        finishes_verified=True,
        exclusions_verified=True,
    )
    assert len(bundle.questions) == 1
    assert bundle.questions[0].status == "SOURCE_EVIDENCE_MISSING_ASK_USER"
    assert bundle.questions[0].suggestion is None
    assert "height_ambiguous_source_suggestions_require_user_choice" in bundle.questions[0].reason_codes

    # Cross-viewport or cross-page suggestion MUST abstain fail-closed
    bad_vp = replace(s1, viewport_id="vp-detail-1to20")
    abstained = build_guided_review_source_questions(
        source_sha256=_SRC_SHA,
        pdf_page=2,
        viewport_id=_VP,
        suggestions=(bad_vp,),
    )
    assert abstained.status == "ABSTAINED"
    assert "suggestion_scope_mismatch" in abstained.reason_codes


def test_review_to_issuer_handoff_verifies_packet_and_preserves_non_commercial_boundaries() -> None:
    scale_sugg = SourceSuggestionProvenance(
        issue="scale",
        source_sha256=_SRC_SHA,
        pdf_page=2,
        viewport_id=_VP,
        evidence_kind="same_page_figured_scale_shadow",
        source_observation_ids=("obs_dim_1",),
        candidate_receipt_sha256=_REC_SHA_1,
        suggested_summary="1:100 orthogonal figured scale candidate",
    )
    q_bundle = build_guided_review_source_questions(
        source_sha256=_SRC_SHA,
        pdf_page=2,
        viewport_id=_VP,
        suggestions=(scale_sugg,),
    )
    packet = _make_native_packet(
        corrections=[
            {
                "correction_id": "dim_wit_1",
                "category": "dimension_witness",
                "kind": "line",
                "native_points_pdf_pts": [[100.0, 100.0], [200.0, 100.0]],
            }
        ],
        answers={
            "scale": {"decision": "correction_recorded", "note": "Confirmed 1:100 against figured span"},
            "finishes": {"decision": "needs_information", "note": "Awaiting client tile schedule"},
            "height": {"decision": "reviewed_no_change", "note": ""},
        },
    )
    handoff = build_review_to_issuer_handoff(
        native_review_packet=packet,
        question_bundle=q_bundle,
    )
    assert isinstance(handoff, ReviewToIssuerHandoffReceipt)
    assert handoff.status == "USER_ASSISTED_HANDOFF_READY"
    assert handoff.automatic_source_verified is False
    assert handoff.commercial_projection_allowed is False
    assert handoff.frozen_benchmark_allowed is False
    by_issue = {d.issue: d for d in handoff.directives}
    assert set(by_issue) == {"scale", "finishes"}
    assert by_issue["scale"].linked_correction_ids == ("dim_wit_1",)
    assert by_issue["scale"].linked_source_suggestion_receipts == (_REC_SHA_1,)
    assert "pb_page_scale_calibration_authority" in handoff.affected_issuers
    assert "pb_source_native_tiled_room_face_authority" in handoff.affected_issuers

    with pytest.raises(ValueError):
        replace(handoff, commercial_projection_allowed=True)
    with pytest.raises(ValueError):
        replace(handoff, frozen_benchmark_allowed=True)


def test_review_to_issuer_handoff_rejects_tampered_commercial_or_cross_scope_packets() -> None:
    tampered = _make_native_packet(tamper=True)
    r_tamper = build_review_to_issuer_handoff(native_review_packet=tampered)
    assert r_tamper.status == "ABSTAINED"
    assert "review_packet_sha256_tampered" in r_tamper.reason_codes

    commercial = _make_native_packet(commercial=True)
    r_comm = build_review_to_issuer_handoff(native_review_packet=commercial)
    assert r_comm.status == "ABSTAINED"
    assert "review_packet_authority_boundary_violated" in r_comm.reason_codes

    frozen = _make_native_packet(frozen=True)
    r_froz = build_review_to_issuer_handoff(native_review_packet=frozen)
    assert r_froz.status == "ABSTAINED"
    assert "review_packet_authority_boundary_violated" in r_froz.reason_codes

    q_other_page = build_guided_review_source_questions(
        source_sha256=_SRC_SHA,
        pdf_page=5,
        viewport_id=_VP,
    )
    r_scope = build_review_to_issuer_handoff(
        native_review_packet=_make_native_packet(pdf_page=2),
        question_bundle=q_other_page,
    )
    assert r_scope.status == "ABSTAINED"
    assert "question_bundle_scope_mismatch" in r_scope.reason_codes
