"""Tests for hardened guided review source questions & review-to-issuer contract (#4794)."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import pytest

from pb_guided_review_source_questions import (
    GuidedSourceQuestionBundle,
    IssuerInvalidationPlan,
    ReviewToIssuerHandoffReceipt,
    SourceSuggestionProvenance,
    UserAssistedScaleIssuerRequest,
    build_guided_review_source_questions,
    build_review_to_issuer_handoff,
    build_user_assisted_scale_issuer_request,
    compute_issuer_invalidation_plan,
    derive_unresolved_guided_questions_from_source_reports,
)

_SRC_SHA = "a" * 64
_IMG_SHA = "b" * 64
_REC_SHA_1 = "c" * 64
_REC_SHA_2 = "d" * 64
_VP = "vp-ground-floor-plan"


def _make_native_packet(
    *,
    source_sha: str = _SRC_SHA,
    page_id: int = 10,
    pdf_page: int = 2,
    viewport_id: str | None = _VP,
    review_revision: int = 1,
    corrections: list[dict] | None = None,
    answers: dict | None = None,
    tamper: bool = False,
    commercial: bool = False,
    frozen: bool = False,
) -> dict:
    scope: dict = {
        "workspace_id": 1,
        "page_id": page_id,
        "pdf_page": pdf_page,
        "source_sha256": source_sha,
        "image_sha256": _IMG_SHA,
    }
    if viewport_id is not None:
        scope["viewport_id"] = viewport_id
    packet = {
        "schema_version": 1,
        "scope": scope,
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


def test_source_questions_preserve_provenance_and_reject_unbound_viewport_leak() -> None:
    scale_sugg = SourceSuggestionProvenance(
        issue="scale",
        source_sha256=_SRC_SHA,
        pdf_page=2,
        viewport_id=_VP,
        evidence_kind="same_page_figured_scale_shadow",
        source_observation_ids=("obs_dim_1", "obs_dim_2"),
        candidate_receipt_sha256=_REC_SHA_1,
        suggested_summary="Same-page orthogonal figured spans suggest 1:100.",
        suggested_value=3000.0,
        suggested_unit="mm",
    )
    bundle = build_guided_review_source_questions(
        source_sha256=_SRC_SHA,
        page_id=10,
        pdf_page=2,
        viewport_id=_VP,
        suggestions=(scale_sugg,),
        exclusions_verified=True,
    )
    assert isinstance(bundle, GuidedSourceQuestionBundle)
    assert bundle.status == "QUESTIONS_READY_FOR_USER_REVIEW"
    assert bundle.page_id == 10
    assert bundle.viewport_id == _VP
    by_issue = {q.issue: q for q in bundle.questions}
    assert set(by_issue) == {"scale", "height", "finishes"}
    assert by_issue["scale"].status == "SOURCE_SUGGESTION_REQUIRES_CONFIRMATION"
    assert by_issue["height"].suggestion is None
    assert by_issue["finishes"].suggestion is None

    # Viewport-bound suggestion cannot attach to an unbound (viewport_id=None) bundle
    unbound_abstain = build_guided_review_source_questions(
        source_sha256=_SRC_SHA,
        page_id=10,
        pdf_page=2,
        viewport_id=None,
        suggestions=(scale_sugg,),
    )
    assert unbound_abstain.status == "ABSTAINED"
    assert "viewport_bound_suggestion_requires_authenticated_bundle_viewport" in unbound_abstain.reason_codes

    # Invalid page_id fails closed
    bad_page = build_guided_review_source_questions(
        source_sha256=_SRC_SHA,
        page_id=0,
        pdf_page=2,
    )
    assert bad_page.status == "ABSTAINED"
    assert "invalid_guided_question_scope_or_flags" in bad_page.reason_codes


def test_preserves_dimension_mm_separates_needs_info_and_requires_explicit_selection() -> None:
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
        page_id=10,
        pdf_page=2,
        viewport_id=_VP,
        suggestions=(scale_sugg,),
    )
    scale_qid = next(q.question_id for q in q_bundle.questions if q.issue == "scale")

    # Generic page-level answer WITHOUT explicit selected_question_id does NOT link suggestion receipt!
    generic_packet = _make_native_packet(
        viewport_id=None,
        answers={"scale": {"decision": "correction_recorded", "note": "checked"}},
    )
    generic_handoff = build_review_to_issuer_handoff(
        native_review_packet=generic_packet,
        question_bundle=q_bundle,
    )
    assert generic_handoff.status == "USER_ASSISTED_HANDOFF_READY"
    assert generic_handoff.actionable_directives[0].selected_suggestion_receipt_sha256 is None
    assert generic_handoff.actionable_directives[0].selected_question_id is None

    # Explicit selection + typed dimension_mm + separate NEEDS_INFORMATION blocker
    packet = _make_native_packet(
        viewport_id=_VP,
        corrections=[
            {
                "correction_id": "dim_wit_1",
                "category": "dimension_witness",
                "kind": "line",
                "native_points_pdf_pts": [[100.0, 100.0], [185.03937, 100.0]],
                "dimension_mm": 3000.0,
                "dimension_unit": "mm",
                "viewport_id": _VP,
                "authority": "user_selected_geometry",
            }
        ],
        answers={
            "scale": {
                "decision": "correction_recorded",
                "note": "Confirmed 3000 mm figured span",
                "selected_question_id": scale_qid,
                "selected_suggestion_receipt_sha256": _REC_SHA_1,
            },
            "finishes": {"decision": "needs_information", "note": "Awaiting client tile schedule"},
        },
    )
    handoff = build_review_to_issuer_handoff(
        native_review_packet=packet,
        question_bundle=q_bundle,
    )
    assert isinstance(handoff, ReviewToIssuerHandoffReceipt)
    assert handoff.status == "USER_ASSISTED_HANDOFF_READY"
    assert handoff.digest_authenticates_user_evidence is False
    assert handoff.automatic_source_verified is False
    assert handoff.commercial_projection_allowed is False
    assert handoff.frozen_benchmark_allowed is False

    # Actionable vs NEEDS_INFORMATION strictly separated
    assert len(handoff.actionable_directives) == 1
    assert len(handoff.unresolved_information_requests) == 1
    scale_dir = handoff.actionable_directives[0]
    assert scale_dir.action_kind == "ACTIONABLE_USER_CORRECTION"
    assert scale_dir.selected_question_id == scale_qid
    assert scale_dir.selected_suggestion_receipt_sha256 == _REC_SHA_1
    assert scale_dir.typed_corrections[0].dimension_mm == 3000.0
    assert scale_dir.typed_corrections[0].dimension_unit == "mm"

    info_dir = handoff.unresolved_information_requests[0]
    assert info_dir.action_kind == "NEEDS_INFORMATION_BLOCKER"
    assert info_dir.issue == "finishes"
    assert "pb_page_scale_calibration_authority" in handoff.actionable_affected_issuers
    assert "pb_source_native_tiled_room_face_authority" in handoff.blocked_information_issuers
    assert "pb_source_native_tiled_room_face_authority" not in handoff.actionable_affected_issuers

    # Existing-issuer consumer contract produces typed non-commercial scale request
    req = build_user_assisted_scale_issuer_request(handoff=handoff)
    assert isinstance(req, UserAssistedScaleIssuerRequest)
    assert req.status == "USER_ASSISTED_SCALE_INPUT_READY"
    assert req.figured_mm == 3000.0
    assert req.implied_mm_per_pt == pytest.approx(35.277778, rel=1e-4)
    assert req.commercial_projection_allowed is False
    assert req.frozen_benchmark_allowed is False


def test_deletion_invalidation_plan_and_negative_hardening_gates() -> None:
    # Rev 1 has an actionable scale correction; Rev 2 deletes it -> MUST invalidate scale & downstream!
    p1 = _make_native_packet(
        review_revision=1,
        corrections=[
            {
                "correction_id": "dim_wit_1",
                "category": "dimension_witness",
                "kind": "line",
                "native_points_pdf_pts": [[10.0, 10.0], [110.0, 10.0]],
                "dimension_mm": 3527.8,
                "dimension_unit": "mm",
            }
        ],
    )
    p2 = _make_native_packet(review_revision=2, corrections=[], answers={})
    h1 = build_review_to_issuer_handoff(native_review_packet=p1)
    h2 = build_review_to_issuer_handoff(native_review_packet=p2)
    plan = compute_issuer_invalidation_plan(previous_handoff=h1, current_handoff=h2)
    assert isinstance(plan, IssuerInvalidationPlan)
    assert plan.status == "INVALIDATION_REQUIRED"
    assert plan.deleted_issues == ("scale",)
    assert "scale" in plan.invalidated_stages
    assert "floor_areas" in plan.invalidated_stages
    assert "pb_page_scale_calibration_authority" in plan.invalidated_issuers
    assert "deleted_directives_invalidate_prior_issuer_outputs" in plan.reason_codes

    # Duplicate correction_id fails closed
    dup_pkt = _make_native_packet(
        corrections=[
            {"correction_id": "dup_1", "category": "dimension_witness", "kind": "line", "native_points_pdf_pts": [[0, 0], [10, 0]], "dimension_mm": 1000.0},
            {"correction_id": "dup_1", "category": "exclusion", "kind": "polygon", "native_points_pdf_pts": [[0, 0], [10, 0], [10, 10]]},
        ]
    )
    r_dup = build_review_to_issuer_handoff(native_review_packet=dup_pkt)
    assert r_dup.status == "ABSTAINED"
    assert "duplicate_correction_id_conflict" in r_dup.reason_codes

    # Malformed dimension_mm (bool / negative) fails closed
    bad_dim_pkt = _make_native_packet(
        corrections=[
            {"correction_id": "d1", "category": "dimension_witness", "kind": "line", "native_points_pdf_pts": [[0, 0], [10, 0]], "dimension_mm": True},
        ]
    )
    r_baddim = build_review_to_issuer_handoff(native_review_packet=bad_dim_pkt)
    assert r_baddim.status == "ABSTAINED"
    assert "invalid_correction_dimension_value" in r_baddim.reason_codes

    # Viewport mismatch between packet and question_bundle fails closed
    q_other_vp = build_guided_review_source_questions(
        source_sha256=_SRC_SHA, page_id=10, pdf_page=2, viewport_id="vp-other-scale"
    )
    r_vp = build_review_to_issuer_handoff(
        native_review_packet=_make_native_packet(viewport_id=_VP),
        question_bundle=q_other_vp,
    )
    assert r_vp.status == "ABSTAINED"
    assert "question_bundle_viewport_mismatch" in r_vp.reason_codes

    # Missing page_id fails closed
    bad_scope = _make_native_packet(page_id=0)
    r_pid = build_review_to_issuer_handoff(native_review_packet=bad_scope)
    assert r_pid.status == "ABSTAINED"
    assert "invalid_review_packet_scope_or_revision" in r_pid.reason_codes

    # Automatic-first helper surfaces unresolved questions from shadow reports without inventing finishes
    class _FakeScaleReport:
        status = "CORROBORATED_SAME_PAGE_FIGURED_SCALE_SHADOW"
        source_sha256 = _SRC_SHA
        page_number = 2
        viewport_id = _VP
        receipt_sha256 = _REC_SHA_1
        mm_per_pt_x = 35.278
        horizontal_witness_ids = ("h1",)
        vertical_witness_ids = ("v1",)

    class _FakeOutlinedReport:
        finish_authority_status = "ABSTAINED"

    auto_bundle = derive_unresolved_guided_questions_from_source_reports(
        source_sha256=_SRC_SHA,
        page_id=10,
        pdf_page=2,
        viewport_id=_VP,
        same_page_scale_report=_FakeScaleReport(),
        outlined_admission_report=_FakeOutlinedReport(),
        finishes_verified=True,  # overridden to False when outlined report abstained finishes
        exclusions_verified=True,
    )
    by_i = {q.issue: q for q in auto_bundle.questions}
    assert by_i["scale"].status == "SOURCE_SUGGESTION_REQUIRES_CONFIRMATION"
    assert by_i["finishes"].status == "SOURCE_EVIDENCE_MISSING_ASK_USER"
    with pytest.raises(ValueError):
        replace(h1, digest_authenticates_user_evidence=True)
