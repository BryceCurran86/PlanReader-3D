"""Source-owned guided review questions, suggestion provenance & review-to-issuer contract.

Companion contract to `pb_guided_plan_review.py` (#4789) and
`pb_guided_plan_review_native.py` (#4791). Produces strictly non-commercial,
viewport- and revision-bound questions for scale, height, finishes, and
exclusions, attaches typed source-suggestion provenance (never inventing
defaults when source evidence is absent), and converts verified native review
packets into typed user-assisted handoff directives targeting existing generic
issuers.

Never promotes a review suggestion or user answer to automatic source evidence,
commercial quantity authority, or frozen benchmark scoring.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "1.0.0"

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")

ALLOWED_QUESTION_ISSUES: tuple[str, ...] = ("scale", "height", "finishes", "exclusions")
ALLOWED_DECISIONS: tuple[str, ...] = (
    "needs_information",
    "correction_recorded",
    "reviewed_no_change",
)

EXISTING_ISSUER_TARGETS: Mapping[str, tuple[str, ...]] = {
    "scale": ("pb_page_scale_calibration_authority",),
    "height": (
        "pb_opening_schedule_v171",
        "pb_opening_vertical_placement_authority",
        "pb_cross_view_ceiling_finish_authority",
    ),
    "finishes": (
        "pb_source_native_tiled_room_face_authority",
        "pb_cross_view_ceiling_finish_authority",
    ),
    "exclusions": (
        "pb_source_native_tiled_room_face_authority",
        "pb_cross_view_ceiling_finish_authority",
    ),
}

_DEFAULT_PROMPTS: Mapping[str, str] = {
    "scale": "Confirm drawing scale or supply a known source figured dimension span for this viewport.",
    "height": "Confirm wall, ceiling, and opening heights from authenticated schedule/elevation/section sources.",
    "finishes": "Confirm floor, wall, and ceiling finish assignments from authenticated specification/legend sources.",
    "exclusions": "Confirm any unmeasured or excluded areas on this sheet before commercial takeoff.",
}


def _is_valid_sha256(value: object) -> bool:
    return type(value) is str and bool(_SHA256_HEX_RE.fullmatch(value))


def _is_positive_int(value: object) -> bool:
    return type(value) is int and value >= 1


def _canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SourceSuggestionProvenance:
    """Typed, strictly non-commercial source suggestion bound to exact revision/page/viewport."""

    issue: str
    source_sha256: str
    pdf_page: int
    viewport_id: str
    evidence_kind: str
    source_observation_ids: tuple[str, ...]
    candidate_receipt_sha256: str
    suggested_summary: str
    suggestion_authority: str = "source_candidate_only"
    commercial_projection_allowed: bool = False
    frozen_benchmark_allowed: bool = False

    def __post_init__(self) -> None:
        if self.issue not in ALLOWED_QUESTION_ISSUES:
            raise ValueError(f"Unsupported guided question issue: {self.issue!r}")
        if not _is_valid_sha256(self.source_sha256):
            raise ValueError("SourceSuggestionProvenance requires exact 64-hex lowercase source_sha256")
        if not _is_positive_int(self.pdf_page):
            raise ValueError("SourceSuggestionProvenance requires positive integer pdf_page")
        if type(self.viewport_id) is not str or not _SAFE_ID_RE.fullmatch(self.viewport_id.strip()):
            raise ValueError("SourceSuggestionProvenance requires a valid non-empty viewport_id")
        if type(self.evidence_kind) is not str or not _SAFE_ID_RE.fullmatch(self.evidence_kind.strip()):
            raise ValueError("SourceSuggestionProvenance requires a valid evidence_kind")
        if (
            not isinstance(self.source_observation_ids, tuple)
            or not self.source_observation_ids
            or any(type(oid) is not str or not oid.strip() for oid in self.source_observation_ids)
        ):
            raise ValueError("SourceSuggestionProvenance requires non-empty tuple of source_observation_ids")
        if not _is_valid_sha256(self.candidate_receipt_sha256):
            raise ValueError("SourceSuggestionProvenance requires exact 64-hex candidate_receipt_sha256")
        if type(self.suggested_summary) is not str or not (1 <= len(self.suggested_summary.strip()) <= 240):
            raise ValueError("SourceSuggestionProvenance requires non-empty suggested_summary (<=240 chars)")
        if self.suggestion_authority != "source_candidate_only":
            raise ValueError("suggestion_authority must remain 'source_candidate_only'")
        if self.commercial_projection_allowed is not False:
            raise ValueError("SourceSuggestionProvenance cannot authorize commercial projection")
        if self.frozen_benchmark_allowed is not False:
            raise ValueError("SourceSuggestionProvenance cannot enter frozen benchmark scoring")


@dataclass(frozen=True)
class GuidedSourceQuestion:
    """One guided review question bound to source revision, page, and viewport."""

    question_id: str
    issue: str
    source_sha256: str
    pdf_page: int
    viewport_id: str
    prompt: str
    status: str  # "SOURCE_SUGGESTION_REQUIRES_CONFIRMATION" | "SOURCE_EVIDENCE_MISSING_ASK_USER"
    suggestion: SourceSuggestionProvenance | None
    target_issuers: tuple[str, ...]
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    frozen_benchmark_allowed: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.commercial_projection_allowed is not False:
            raise ValueError("GuidedSourceQuestion cannot authorize commercial projection")
        if self.frozen_benchmark_allowed is not False:
            raise ValueError("GuidedSourceQuestion cannot enter frozen benchmark scoring")


@dataclass(frozen=True)
class GuidedSourceQuestionBundle:
    """Immutable bundle of guided source review questions for one viewport/page."""

    status: str  # "QUESTIONS_READY_FOR_USER_REVIEW" | "NO_OPEN_QUESTIONS" | "ABSTAINED"
    source_sha256: str
    pdf_page: int
    viewport_id: str
    questions: tuple[GuidedSourceQuestion, ...]
    bundle_sha256: str
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    frozen_benchmark_allowed: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.commercial_projection_allowed is not False:
            raise ValueError("GuidedSourceQuestionBundle cannot authorize commercial projection")
        if self.frozen_benchmark_allowed is not False:
            raise ValueError("GuidedSourceQuestionBundle cannot enter frozen benchmark scoring")


@dataclass(frozen=True)
class ReviewToIssuerDirective:
    """Non-commercial user-assisted review directive targeting existing generic issuers."""

    directive_id: str
    issue: str
    target_issuers: tuple[str, ...]
    decision: str
    user_note: str
    linked_correction_ids: tuple[str, ...]
    linked_source_suggestion_receipts: tuple[str, ...]
    authority: str = "user_assisted_review_pending_issuer"
    automatic_source_verified: bool = False
    commercial_projection_allowed: bool = False
    frozen_benchmark_allowed: bool = False

    def __post_init__(self) -> None:
        if self.authority != "user_assisted_review_pending_issuer":
            raise ValueError("ReviewToIssuerDirective authority must remain user_assisted_review_pending_issuer")
        if self.automatic_source_verified is not False:
            raise ValueError("ReviewToIssuerDirective cannot claim automatic_source_verified=True")
        if self.commercial_projection_allowed is not False:
            raise ValueError("ReviewToIssuerDirective cannot authorize commercial projection")
        if self.frozen_benchmark_allowed is not False:
            raise ValueError("ReviewToIssuerDirective cannot enter frozen benchmark scoring")


@dataclass(frozen=True)
class ReviewToIssuerHandoffReceipt:
    """Verified handoff from a native Plan Mapper review packet to existing issuers."""

    status: str  # "USER_ASSISTED_HANDOFF_READY" | "NO_SOURCE_ISSUER_UPDATES" | "ABSTAINED"
    source_sha256: str
    pdf_page: int
    review_revision: int
    source_packet_sha256: str
    directives: tuple[ReviewToIssuerDirective, ...]
    affected_issuers: tuple[str, ...]
    handoff_sha256: str
    reason_codes: tuple[str, ...]
    automatic_source_verified: bool = False
    commercial_projection_allowed: bool = False
    frozen_benchmark_allowed: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.automatic_source_verified is not False:
            raise ValueError("ReviewToIssuerHandoffReceipt cannot claim automatic_source_verified=True")
        if self.commercial_projection_allowed is not False:
            raise ValueError("ReviewToIssuerHandoffReceipt cannot authorize commercial projection")
        if self.frozen_benchmark_allowed is not False:
            raise ValueError("ReviewToIssuerHandoffReceipt cannot enter frozen benchmark scoring")


def _abstain_questions(
    *,
    source_sha256: str,
    pdf_page: int,
    viewport_id: str,
    reasons: tuple[str, ...],
) -> GuidedSourceQuestionBundle:
    digest = _canonical_json_sha256(
        {
            "sha": source_sha256,
            "page": pdf_page,
            "viewport_id": viewport_id,
            "reasons": list(reasons),
        }
    )
    return GuidedSourceQuestionBundle(
        status="ABSTAINED",
        source_sha256=source_sha256,
        pdf_page=pdf_page,
        viewport_id=viewport_id,
        questions=(),
        bundle_sha256=digest,
        reason_codes=reasons,
    )


def build_guided_review_source_questions(
    *,
    source_sha256: str,
    pdf_page: int,
    viewport_id: str,
    suggestions: Sequence[SourceSuggestionProvenance] = (),
    scale_verified: bool = False,
    height_verified: bool = False,
    finishes_verified: bool = False,
    exclusions_verified: bool = False,
) -> GuidedSourceQuestionBundle:
    """Build source-owned guided questions for scale, height, finishes, and exclusions.

    Never invents default scale/height/finish values when source evidence is absent.
    Conflicting multiple suggestions for the same issue remain unresolved and surface
    an open question requiring explicit user confirmation.
    """
    clean_sha = source_sha256.strip() if type(source_sha256) is str else ""
    clean_vp = viewport_id.strip() if type(viewport_id) is str else ""
    safe_page = pdf_page if type(pdf_page) is int else 0

    if (
        not _is_valid_sha256(clean_sha)
        or not _is_positive_int(pdf_page)
        or not _SAFE_ID_RE.fullmatch(clean_vp)
        or any(
            type(flag) is not bool
            for flag in (scale_verified, height_verified, finishes_verified, exclusions_verified)
        )
    ):
        return _abstain_questions(
            source_sha256=clean_sha,
            pdf_page=safe_page,
            viewport_id=clean_vp,
            reasons=("invalid_guided_question_scope_or_flags",),
        )

    by_issue: dict[str, list[SourceSuggestionProvenance]] = {k: [] for k in ALLOWED_QUESTION_ISSUES}
    for item in suggestions:
        if not isinstance(item, SourceSuggestionProvenance):
            return _abstain_questions(
                source_sha256=clean_sha,
                pdf_page=pdf_page,
                viewport_id=clean_vp,
                reasons=("invalid_source_suggestion_type",),
            )
        if (
            item.source_sha256 != clean_sha
            or item.pdf_page != pdf_page
            or item.viewport_id.strip() != clean_vp
        ):
            return _abstain_questions(
                source_sha256=clean_sha,
                pdf_page=pdf_page,
                viewport_id=clean_vp,
                reasons=("suggestion_scope_mismatch",),
            )
        by_issue[item.issue].append(item)

    verified_map = {
        "scale": scale_verified,
        "height": height_verified,
        "finishes": finishes_verified,
        "exclusions": exclusions_verified,
    }
    questions: list[GuidedSourceQuestion] = []
    bundle_reasons: set[str] = set()

    for issue in ALLOWED_QUESTION_ISSUES:
        if verified_map[issue]:
            continue
        candidates = by_issue[issue]
        unique_receipts = {c.candidate_receipt_sha256 for c in candidates}
        if len(unique_receipts) == 1:
            chosen = candidates[0]
            q_status = "SOURCE_SUGGESTION_REQUIRES_CONFIRMATION"
            q_reasons = (
                f"{issue}_source_candidate_pending_user_confirmation",
                f"evidence_kind:{chosen.evidence_kind}",
            )
            prompt = (
                f"{_DEFAULT_PROMPTS[issue]} "
                f"Source candidate (review only): {chosen.suggested_summary.strip()}"
            )
        elif len(unique_receipts) > 1:
            chosen = None
            q_status = "SOURCE_EVIDENCE_MISSING_ASK_USER"
            q_reasons = (
                f"{issue}_ambiguous_source_suggestions_require_user_choice",
            )
            prompt = (
                f"{_DEFAULT_PROMPTS[issue]} "
                f"Multiple conflicting source candidates exist; explicit user confirmation required."
            )
        else:
            chosen = None
            q_status = "SOURCE_EVIDENCE_MISSING_ASK_USER"
            q_reasons = (f"{issue}_source_evidence_missing_no_default_assumed",)
            prompt = _DEFAULT_PROMPTS[issue]

        qid = "guided_q_" + _canonical_json_sha256(
            {
                "sha": clean_sha,
                "page": pdf_page,
                "vp": clean_vp,
                "issue": issue,
                "status": q_status,
                "receipt": chosen.candidate_receipt_sha256 if chosen is not None else None,
            }
        )[:24]
        bundle_reasons.update(q_reasons)
        questions.append(
            GuidedSourceQuestion(
                question_id=qid,
                issue=issue,
                source_sha256=clean_sha,
                pdf_page=pdf_page,
                viewport_id=clean_vp,
                prompt=prompt,
                status=q_status,
                suggestion=chosen,
                target_issuers=EXISTING_ISSUER_TARGETS[issue],
                reason_codes=q_reasons,
            )
        )

    status = "QUESTIONS_READY_FOR_USER_REVIEW" if questions else "NO_OPEN_QUESTIONS"
    if not questions:
        bundle_reasons.add("all_source_review_domains_already_verified")
    bundle_sha = _canonical_json_sha256(
        {
            "sha": clean_sha,
            "page": pdf_page,
            "vp": clean_vp,
            "status": status,
            "qids": [q.question_id for q in questions],
        }
    )
    return GuidedSourceQuestionBundle(
        status=status,
        source_sha256=clean_sha,
        pdf_page=pdf_page,
        viewport_id=clean_vp,
        questions=tuple(questions),
        bundle_sha256=bundle_sha,
        reason_codes=tuple(sorted(bundle_reasons)),
    )


def _abstain_handoff(
    *,
    source_sha256: str = "",
    pdf_page: int = 0,
    review_revision: int = 0,
    packet_sha256: str = "",
    reasons: tuple[str, ...],
) -> ReviewToIssuerHandoffReceipt:
    digest = _canonical_json_sha256(
        {
            "sha": source_sha256,
            "page": pdf_page,
            "rev": review_revision,
            "packet_sha": packet_sha256,
            "reasons": list(reasons),
        }
    )
    return ReviewToIssuerHandoffReceipt(
        status="ABSTAINED",
        source_sha256=source_sha256,
        pdf_page=pdf_page,
        review_revision=review_revision,
        source_packet_sha256=packet_sha256,
        directives=(),
        affected_issuers=(),
        handoff_sha256=digest,
        reason_codes=reasons,
    )


def build_review_to_issuer_handoff(
    *,
    native_review_packet: Mapping[str, Any],
    question_bundle: GuidedSourceQuestionBundle | None = None,
) -> ReviewToIssuerHandoffReceipt:
    """Convert a verified #4791 native review packet into typed issuer handoff directives.

    Strictly verifies packet SHA-256 integrity, non-commercial/non-benchmark flags,
    and scope alignment before emitting user-assisted directives for existing issuers.
    """
    if not isinstance(native_review_packet, Mapping):
        return _abstain_handoff(reasons=("invalid_native_review_packet_type",))

    packet_sha = native_review_packet.get("packet_sha256")
    if not _is_valid_sha256(packet_sha):
        return _abstain_handoff(reasons=("missing_or_invalid_packet_sha256",))

    payload_without_sha = {k: v for k, v in native_review_packet.items() if k != "packet_sha256"}
    try:
        recomputed = _canonical_json_sha256(payload_without_sha)
    except (TypeError, ValueError):
        return _abstain_handoff(packet_sha256=str(packet_sha), reasons=("non_serializable_review_packet",))

    if recomputed != packet_sha:
        return _abstain_handoff(packet_sha256=str(packet_sha), reasons=("review_packet_sha256_tampered",))

    if (
        native_review_packet.get("schema_version") != 1
        or native_review_packet.get("automatic_source_verified") is not False
        or native_review_packet.get("commercial_projection_allowed") is not False
        or native_review_packet.get("frozen_benchmark_allowed") is not False
    ):
        return _abstain_handoff(
            packet_sha256=str(packet_sha),
            reasons=("review_packet_authority_boundary_violated",),
        )

    scope = native_review_packet.get("scope")
    review_rev = native_review_packet.get("review_revision")
    if (
        not isinstance(scope, Mapping)
        or not _is_valid_sha256(scope.get("source_sha256"))
        or not _is_valid_sha256(scope.get("image_sha256"))
        or not _is_positive_int(scope.get("pdf_page"))
        or not _is_positive_int(scope.get("workspace_id"))
        or not _is_positive_int(review_rev)
    ):
        return _abstain_handoff(
            packet_sha256=str(packet_sha),
            reasons=("invalid_review_packet_scope_or_revision",),
        )

    src_sha = str(scope["source_sha256"])
    pdf_page = int(scope["pdf_page"])

    suggestion_receipts_by_issue: dict[str, tuple[str, ...]] = {}
    if question_bundle is not None:
        if not isinstance(question_bundle, GuidedSourceQuestionBundle):
            return _abstain_handoff(
                source_sha256=src_sha,
                pdf_page=pdf_page,
                review_revision=review_rev,
                packet_sha256=str(packet_sha),
                reasons=("invalid_question_bundle_type",),
            )
        if question_bundle.source_sha256 != src_sha or question_bundle.pdf_page != pdf_page:
            return _abstain_handoff(
                source_sha256=src_sha,
                pdf_page=pdf_page,
                review_revision=review_rev,
                packet_sha256=str(packet_sha),
                reasons=("question_bundle_scope_mismatch",),
            )
        for q in question_bundle.questions:
            if q.suggestion is not None:
                suggestion_receipts_by_issue[q.issue] = (q.suggestion.candidate_receipt_sha256,)

    corrections = native_review_packet.get("corrections")
    answers = native_review_packet.get("unbound_review_answers")
    if not isinstance(corrections, Sequence) or not isinstance(answers, Mapping):
        return _abstain_handoff(
            source_sha256=src_sha,
            pdf_page=pdf_page,
            review_revision=review_rev,
            packet_sha256=str(packet_sha),
            reasons=("invalid_review_packet_body",),
        )

    correction_ids_by_issue: dict[str, list[str]] = {k: [] for k in ALLOWED_QUESTION_ISSUES}
    for corr in corrections:
        if not isinstance(corr, Mapping):
            continue
        cid = corr.get("correction_id")
        cat = corr.get("category")
        if type(cid) is not str or not cid.strip():
            continue
        if cat == "dimension_witness":
            correction_ids_by_issue["scale"].append(cid.strip())
        elif cat == "exclusion":
            correction_ids_by_issue["exclusions"].append(cid.strip())

    directives: list[ReviewToIssuerDirective] = []
    affected_issuers: set[str] = set()
    reasons: set[str] = set()

    for issue in ALLOWED_QUESTION_ISSUES:
        raw_answer = answers.get(issue)
        corr_ids = tuple(sorted(set(correction_ids_by_issue[issue])))
        decision = ""
        note = ""
        if isinstance(raw_answer, Mapping):
            raw_dec = raw_answer.get("decision")
            if raw_dec not in ALLOWED_DECISIONS:
                return _abstain_handoff(
                    source_sha256=src_sha,
                    pdf_page=pdf_page,
                    review_revision=review_rev,
                    packet_sha256=str(packet_sha),
                    reasons=("invalid_review_answer_decision",),
                )
            decision = str(raw_dec)
            note = str(raw_answer.get("note") or "").strip()[:500]

        if not corr_ids and decision not in ("correction_recorded", "needs_information"):
            continue
        effective_decision = decision or "correction_recorded"
        issuers = EXISTING_ISSUER_TARGETS[issue]
        affected_issuers.update(issuers)
        linked_receipts = suggestion_receipts_by_issue.get(issue, ())
        did = "issuer_dir_" + _canonical_json_sha256(
            {
                "packet_sha": str(packet_sha),
                "issue": issue,
                "decision": effective_decision,
                "corr_ids": list(corr_ids),
                "note": note,
            }
        )[:24]
        directives.append(
            ReviewToIssuerDirective(
                directive_id=did,
                issue=issue,
                target_issuers=issuers,
                decision=effective_decision,
                user_note=note,
                linked_correction_ids=corr_ids,
                linked_source_suggestion_receipts=linked_receipts,
            )
        )
        reasons.add(f"handoff_{issue}_{effective_decision}")

    status = "USER_ASSISTED_HANDOFF_READY" if directives else "NO_SOURCE_ISSUER_UPDATES"
    if not directives:
        reasons.add("no_scale_height_finish_or_exclusion_updates_in_packet")
    handoff_sha = _canonical_json_sha256(
        {
            "packet_sha": str(packet_sha),
            "status": status,
            "directives": [d.directive_id for d in directives],
            "issuers": sorted(affected_issuers),
        }
    )
    return ReviewToIssuerHandoffReceipt(
        status=status,
        source_sha256=src_sha,
        pdf_page=pdf_page,
        review_revision=review_rev,
        source_packet_sha256=str(packet_sha),
        directives=tuple(directives),
        affected_issuers=tuple(sorted(affected_issuers)),
        handoff_sha256=handoff_sha,
        reason_codes=tuple(sorted(reasons)),
    )
