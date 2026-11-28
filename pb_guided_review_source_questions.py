"""Source-owned guided review questions, suggestion provenance & review-to-issuer contract.

Companion contract to `pb_guided_plan_review.py` (#4789),
`pb_guided_plan_review_native.py` (#4791), and `pb_guided_plan_review_snap.py` (#4795).

Key invariants:
- Strict 64-char lowercase hex SHA-256 provenance, positive integer `page_id` & `pdf_page`,
  and explicit viewport/object binding ONLY when authenticated (never silently binding a
  viewport-scoped suggestion to a generic page-level answer).
- Preserves typed `dimension_mm` / `dimension_unit`, `native_points_pdf_pts`, exact
  `correction_id` / `target_object_id` / `selected_question_id` / user-selected
  `candidate_receipt_sha256`.
- Rejects malformed or duplicate `correction_id`s and malformed packet structures fail-closed;
  treats `packet_sha256` strictly as tamper-detection integrity, NEVER as authentication.
- Separates actionable user corrections (`ACTIONABLE_USER_CORRECTION`) from unresolved
  information blockers (`NEEDS_INFORMATION_BLOCKER`).
- Computes conservative issuer & stage invalidation plans across revisions including
  correction/answer **deletions**.
- Never promotes user-assisted review data to automatic source authority, commercial
  quantity authority, or frozen120 benchmark scoring.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "2.0.0"

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")

ALLOWED_QUESTION_ISSUES: tuple[str, ...] = ("scale", "height", "finishes", "exclusions")
ALLOWED_DECISIONS: tuple[str, ...] = (
    "needs_information",
    "correction_recorded",
    "reviewed_no_change",
)
ALLOWED_CORRECTION_CATEGORIES: frozenset[str] = frozenset(
    {
        "external_wall",
        "internal_wall",
        "swing_door",
        "cavity_slider",
        "garage_door",
        "window",
        "opening",
        "boundary",
        "room_outline",
        "exclusion",
        "dimension_witness",
        "reject_candidate",
    }
)
ALLOWED_DIMENSION_UNITS: frozenset[str] = frozenset({"mm", "m"})

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

_STAGE_ORDER: tuple[str, ...] = (
    "topology",
    "scale",
    "room_faces",
    "opening_hosts",
    "opening_dimensions",
    "height",
    "exclusions",
    "floor_areas",
    "ceiling_areas",
    "net_wall_areas",
    "finishes",
    "costing",
    "model",
)

_ISSUE_INVALIDATED_STAGES: Mapping[str, tuple[str, ...]] = {
    "scale": (
        "scale",
        "room_faces",
        "opening_dimensions",
        "floor_areas",
        "ceiling_areas",
        "net_wall_areas",
        "finishes",
        "costing",
        "model",
    ),
    "height": (
        "height",
        "opening_dimensions",
        "ceiling_areas",
        "net_wall_areas",
        "finishes",
        "costing",
        "model",
    ),
    "finishes": ("finishes", "costing", "model"),
    "exclusions": (
        "exclusions",
        "floor_areas",
        "ceiling_areas",
        "net_wall_areas",
        "finishes",
        "costing",
        "model",
    ),
}

_DEFAULT_PROMPTS: Mapping[str, str] = {
    "scale": "Confirm drawing scale or supply a known source figured dimension span for this scope.",
    "height": "Confirm wall, ceiling, and opening heights from authenticated schedule/elevation/section sources.",
    "finishes": "Confirm floor, wall, and ceiling finish assignments from authenticated specification/legend sources.",
    "exclusions": "Confirm any unmeasured or excluded areas on this sheet before commercial takeoff.",
}


def _is_valid_sha256(value: object) -> bool:
    return type(value) is str and bool(_SHA256_HEX_RE.fullmatch(value))


def _is_positive_int(value: object) -> bool:
    return type(value) is int and value >= 1


def _clean_optional_id(value: object) -> tuple[bool, str | None]:
    """Return (ok, cleaned_or_None). Rejects non-string / invalid characters."""
    if value is None:
        return True, None
    if type(value) is not str:
        return False, None
    trimmed = value.strip()
    if not trimmed:
        return True, None
    if not _SAFE_ID_RE.fullmatch(trimmed):
        return False, None
    return True, trimmed


def _finite_positive_float(value: object) -> float | None:
    if type(value) is bool or value is None:
        return None
    if not isinstance(value, (int, float)):
        return None
    f = float(value)
    if not math.isfinite(f) or f <= 0.0:
        return None
    return f


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
    """Typed, strictly non-commercial source suggestion bound to exact revision & page.

    `viewport_id` and `target_object_id` are optional: populate ONLY when genuinely
    authenticated by a source producer; otherwise leave `None` (unbound).
    """

    issue: str
    source_sha256: str
    pdf_page: int
    evidence_kind: str
    source_observation_ids: tuple[str, ...]
    candidate_receipt_sha256: str
    suggested_summary: str
    viewport_id: str | None = None
    target_object_id: str | None = None
    suggested_value: float | None = None
    suggested_unit: str | None = None
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
        ok_vp, clean_vp = _clean_optional_id(self.viewport_id)
        if not ok_vp or (self.viewport_id is not None and clean_vp is None):
            raise ValueError("SourceSuggestionProvenance viewport_id must be None or a valid safe identifier")
        ok_obj, clean_obj = _clean_optional_id(self.target_object_id)
        if not ok_obj or (self.target_object_id is not None and clean_obj is None):
            raise ValueError("SourceSuggestionProvenance target_object_id must be None or a valid safe identifier")
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
        if self.suggested_value is not None:
            if _finite_positive_float(self.suggested_value) is None:
                raise ValueError("suggested_value must be a finite positive number")
            if self.suggested_unit not in ALLOWED_DIMENSION_UNITS:
                raise ValueError("suggested_value requires an explicit unit ('mm' or 'm')")
        elif self.suggested_unit is not None:
            raise ValueError("suggested_unit cannot be supplied without suggested_value")
        if self.suggestion_authority != "source_candidate_only":
            raise ValueError("suggestion_authority must remain 'source_candidate_only'")
        if self.commercial_projection_allowed is not False:
            raise ValueError("SourceSuggestionProvenance cannot authorize commercial projection")
        if self.frozen_benchmark_allowed is not False:
            raise ValueError("SourceSuggestionProvenance cannot enter frozen benchmark scoring")


@dataclass(frozen=True)
class TypedReviewCorrectionInput:
    """Typed native-page user correction preserving dimension_mm, units, and target IDs."""

    correction_id: str
    category: str
    kind: str
    native_points_pdf_pts: tuple[tuple[float, float], ...]
    dimension_mm: float | None = None
    dimension_unit: str | None = None
    target_object_id: str | None = None
    viewport_id: str | None = None
    authority: str = "user_selected_geometry"

    def __post_init__(self) -> None:
        if type(self.correction_id) is not str or not _SAFE_ID_RE.fullmatch(self.correction_id):
            raise ValueError("TypedReviewCorrectionInput requires valid correction_id")
        if self.category not in ALLOWED_CORRECTION_CATEGORIES:
            raise ValueError(f"Unsupported correction category: {self.category!r}")
        if self.kind not in ("line", "polygon"):
            raise ValueError(f"Unsupported correction kind: {self.kind!r}")
        min_pts = 3 if self.kind == "polygon" else 2
        if not isinstance(self.native_points_pdf_pts, tuple) or len(self.native_points_pdf_pts) < min_pts:
            raise ValueError(f"{self.kind} correction requires at least {min_pts} native PDF points")
        for pt in self.native_points_pdf_pts:
            if (
                not isinstance(pt, tuple)
                or len(pt) != 2
                or any(type(v) is bool or not isinstance(v, (int, float)) or not math.isfinite(float(v)) for v in pt)
            ):
                raise ValueError("Correction point must be a finite (x, y) PDF-point tuple")
        if self.dimension_mm is not None:
            if _finite_positive_float(self.dimension_mm) is None:
                raise ValueError("dimension_mm must be a finite positive number")
            if self.dimension_unit not in ALLOWED_DIMENSION_UNITS:
                raise ValueError("dimension_mm requires explicit unit ('mm' or 'm')")
        elif self.dimension_unit is not None:
            raise ValueError("dimension_unit cannot be supplied without dimension_mm")
        if self.authority != "user_selected_geometry":
            raise ValueError("TypedReviewCorrectionInput authority must remain 'user_selected_geometry'")


@dataclass(frozen=True)
class GuidedSourceQuestion:
    """One guided review question bound to source revision, page_id, pdf_page, and optional viewport."""

    question_id: str
    issue: str
    source_sha256: str
    page_id: int
    pdf_page: int
    viewport_id: str | None
    target_object_id: str | None
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
    """Immutable bundle of guided source review questions for one page/scope."""

    status: str  # "QUESTIONS_READY_FOR_USER_REVIEW" | "NO_OPEN_QUESTIONS" | "ABSTAINED"
    source_sha256: str
    page_id: int
    pdf_page: int
    viewport_id: str | None
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
    """Typed user-assisted review directive targeting existing generic issuers.

    Explicitly separates:
    - `ACTIONABLE_USER_CORRECTION`: geometry-bound or explicitly suggestion-bound correction
      NOT vetoed by `needs_information`.
    - `USER_PROPOSAL_UNBOUND`: unbound free-text `correction_recorded` note (proposal only,
      never executable by an issuer).
    - `NEEDS_INFORMATION_BLOCKER`: explicit `needs_information` veto (blocks actionability
      even when draft marks exist on that issue).
    """

    directive_id: str
    issue: str
    action_kind: str  # "ACTIONABLE_USER_CORRECTION" | "USER_PROPOSAL_UNBOUND" | "NEEDS_INFORMATION_BLOCKER"
    target_issuers: tuple[str, ...]
    decision: str
    user_note: str
    typed_corrections: tuple[TypedReviewCorrectionInput, ...]
    linked_correction_ids: tuple[str, ...]
    viewport_id: str | None
    target_object_id: str | None
    selected_question_id: str | None
    selected_suggestion_receipt_sha256: str | None
    authority: str = "user_assisted_review_pending_issuer"
    automatic_source_verified: bool = False
    commercial_projection_allowed: bool = False
    frozen_benchmark_allowed: bool = False

    def __post_init__(self) -> None:
        if self.action_kind not in (
            "ACTIONABLE_USER_CORRECTION",
            "USER_PROPOSAL_UNBOUND",
            "NEEDS_INFORMATION_BLOCKER",
        ):
            raise ValueError(f"Invalid directive action_kind: {self.action_kind!r}")
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
    """Verified handoff from a native Plan Mapper review packet to existing issuers.

    Note: `source_packet_sha256` is tamper-detection integrity ONLY — it does not
    authenticate user-supplied geometry or grant automatic/commercial authority.
    """

    status: str  # "USER_ASSISTED_HANDOFF_READY" | "USER_PROPOSALS_ONLY" | "NEEDS_INFORMATION_ONLY" | "NO_SOURCE_ISSUER_UPDATES" | "ABSTAINED"
    source_sha256: str
    page_id: int
    pdf_page: int
    viewport_id: str | None
    review_revision: int
    source_packet_sha256: str
    actionable_directives: tuple[ReviewToIssuerDirective, ...]
    unresolved_information_requests: tuple[ReviewToIssuerDirective, ...]
    directives: tuple[ReviewToIssuerDirective, ...]
    actionable_affected_issuers: tuple[str, ...]
    blocked_information_issuers: tuple[str, ...]
    affected_issuers: tuple[str, ...]
    handoff_sha256: str
    reason_codes: tuple[str, ...]
    unbound_proposals: tuple[ReviewToIssuerDirective, ...] = ()
    proposed_affected_issuers: tuple[str, ...] = ()
    digest_authenticates_user_evidence: bool = False
    automatic_source_verified: bool = False
    commercial_projection_allowed: bool = False
    frozen_benchmark_allowed: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.digest_authenticates_user_evidence is not False:
            raise ValueError("Packet digest is integrity only, never authentication")
        if self.automatic_source_verified is not False:
            raise ValueError("ReviewToIssuerHandoffReceipt cannot claim automatic_source_verified=True")
        if self.commercial_projection_allowed is not False:
            raise ValueError("ReviewToIssuerHandoffReceipt cannot authorize commercial projection")
        if self.frozen_benchmark_allowed is not False:
            raise ValueError("ReviewToIssuerHandoffReceipt cannot enter frozen benchmark scoring")


@dataclass(frozen=True)
class IssuerInvalidationPlan:
    """Conservative downstream invalidation plan across review revisions (including deletions)."""

    status: str  # "INVALIDATION_REQUIRED" | "NO_CHANGES" | "ABSTAINED"
    source_sha256: str
    page_id: int
    pdf_page: int
    previous_revision: int | None
    current_revision: int
    added_or_modified_issues: tuple[str, ...]
    deleted_issues: tuple[str, ...]
    invalidated_stages: tuple[str, ...]
    invalidated_issuers: tuple[str, ...]
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    frozen_benchmark_allowed: bool = False

    def __post_init__(self) -> None:
        if self.commercial_projection_allowed is not False:
            raise ValueError("IssuerInvalidationPlan cannot authorize commercial projection")
        if self.frozen_benchmark_allowed is not False:
            raise ValueError("IssuerInvalidationPlan cannot enter frozen benchmark scoring")


@dataclass(frozen=True)
class UserAssistedScaleIssuerRequest:
    """Typed non-commercial consumer input for `pb_page_scale_calibration_authority`."""

    status: str  # "USER_ASSISTED_SCALE_INPUT_READY" | "ABSTAINED"
    target_issuer: str
    source_sha256: str
    page_id: int
    pdf_page: int
    viewport_id: str | None
    correction_id: str
    native_span_endpoints_pdf_pts: tuple[tuple[float, float], tuple[float, float]] | None
    span_pdf_pts: float | None
    figured_mm: float | None
    implied_mm_per_pt: float | None
    source_handoff_sha256: str
    reason_codes: tuple[str, ...]
    authority: str = "user_assisted_review_pending_issuer"
    automatic_source_verified: bool = False
    commercial_projection_allowed: bool = False
    frozen_benchmark_allowed: bool = False

    def __post_init__(self) -> None:
        if self.automatic_source_verified is not False:
            raise ValueError("UserAssistedScaleIssuerRequest cannot claim automatic_source_verified=True")
        if self.commercial_projection_allowed is not False:
            raise ValueError("UserAssistedScaleIssuerRequest cannot authorize commercial projection")
        if self.frozen_benchmark_allowed is not False:
            raise ValueError("UserAssistedScaleIssuerRequest cannot enter frozen benchmark scoring")


def _abstain_questions(
    *,
    source_sha256: str,
    page_id: int,
    pdf_page: int,
    viewport_id: str | None,
    reasons: tuple[str, ...],
) -> GuidedSourceQuestionBundle:
    digest = _canonical_json_sha256(
        {
            "sha": source_sha256,
            "page_id": page_id,
            "page": pdf_page,
            "viewport_id": viewport_id,
            "reasons": list(reasons),
        }
    )
    return GuidedSourceQuestionBundle(
        status="ABSTAINED",
        source_sha256=source_sha256,
        page_id=page_id,
        pdf_page=pdf_page,
        viewport_id=viewport_id,
        questions=(),
        bundle_sha256=digest,
        reason_codes=reasons,
    )


def build_guided_review_source_questions(
    *,
    source_sha256: str,
    page_id: int,
    pdf_page: int,
    viewport_id: str | None = None,
    suggestions: Sequence[SourceSuggestionProvenance] = (),
    scale_verified: bool = False,
    height_verified: bool = False,
    finishes_verified: bool = False,
    exclusions_verified: bool = False,
) -> GuidedSourceQuestionBundle:
    """Build source-owned guided questions for scale, height, finishes, and exclusions.

    `viewport_id` is required ONLY when genuinely authenticated; leave `None` for
    page-scoped unbound review. Never fabricates defaults when source evidence is absent.
    """
    clean_sha = source_sha256.strip() if type(source_sha256) is str else ""
    safe_page_id = page_id if type(page_id) is int else 0
    safe_page = pdf_page if type(pdf_page) is int else 0
    ok_vp, clean_vp = _clean_optional_id(viewport_id)

    if (
        not _is_valid_sha256(clean_sha)
        or not _is_positive_int(page_id)
        or not _is_positive_int(pdf_page)
        or not ok_vp
        or (viewport_id is not None and clean_vp is None)
        or any(
            type(flag) is not bool
            for flag in (scale_verified, height_verified, finishes_verified, exclusions_verified)
        )
    ):
        return _abstain_questions(
            source_sha256=clean_sha,
            page_id=safe_page_id,
            pdf_page=safe_page,
            viewport_id=clean_vp,
            reasons=("invalid_guided_question_scope_or_flags",),
        )

    by_issue: dict[str, list[SourceSuggestionProvenance]] = {k: [] for k in ALLOWED_QUESTION_ISSUES}
    for item in suggestions:
        if not isinstance(item, SourceSuggestionProvenance):
            return _abstain_questions(
                source_sha256=clean_sha,
                page_id=page_id,
                pdf_page=pdf_page,
                viewport_id=clean_vp,
                reasons=("invalid_source_suggestion_type",),
            )
        if item.source_sha256 != clean_sha or item.pdf_page != pdf_page:
            return _abstain_questions(
                source_sha256=clean_sha,
                page_id=page_id,
                pdf_page=pdf_page,
                viewport_id=clean_vp,
                reasons=("suggestion_scope_mismatch",),
            )
        # Require matching viewport whenever either bundle or suggestion carries one
        if clean_vp is not None and item.viewport_id is not None and item.viewport_id != clean_vp:
            return _abstain_questions(
                source_sha256=clean_sha,
                page_id=page_id,
                pdf_page=pdf_page,
                viewport_id=clean_vp,
                reasons=("suggestion_viewport_mismatch",),
            )
        if clean_vp is None and item.viewport_id is not None:
            return _abstain_questions(
                source_sha256=clean_sha,
                page_id=page_id,
                pdf_page=pdf_page,
                viewport_id=clean_vp,
                reasons=("viewport_bound_suggestion_requires_authenticated_bundle_viewport",),
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
            target_obj = chosen.target_object_id
        elif len(unique_receipts) > 1:
            chosen = None
            q_status = "SOURCE_EVIDENCE_MISSING_ASK_USER"
            q_reasons = (f"{issue}_ambiguous_source_suggestions_require_user_choice",)
            prompt = (
                f"{_DEFAULT_PROMPTS[issue]} "
                f"Multiple conflicting source candidates exist; explicit user confirmation required."
            )
            target_obj = None
        else:
            chosen = None
            q_status = "SOURCE_EVIDENCE_MISSING_ASK_USER"
            q_reasons = (f"{issue}_source_evidence_missing_no_default_assumed",)
            prompt = _DEFAULT_PROMPTS[issue]
            target_obj = None

        qid = "guided_q_" + _canonical_json_sha256(
            {
                "sha": clean_sha,
                "page_id": page_id,
                "page": pdf_page,
                "vp": clean_vp,
                "obj": target_obj,
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
                page_id=page_id,
                pdf_page=pdf_page,
                viewport_id=clean_vp,
                target_object_id=target_obj,
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
            "page_id": page_id,
            "page": pdf_page,
            "vp": clean_vp,
            "status": status,
            "qids": [q.question_id for q in questions],
        }
    )
    return GuidedSourceQuestionBundle(
        status=status,
        source_sha256=clean_sha,
        page_id=page_id,
        pdf_page=pdf_page,
        viewport_id=clean_vp,
        questions=tuple(questions),
        bundle_sha256=bundle_sha,
        reason_codes=tuple(sorted(bundle_reasons)),
    )


def derive_unresolved_guided_questions_from_source_reports(
    *,
    source_sha256: str,
    page_id: int,
    pdf_page: int,
    viewport_id: str | None = None,
    same_page_scale_report: Any | None = None,
    outlined_admission_report: Any | None = None,
    dimension_evidence_bundle: Any | None = None,
    height_verified: bool = False,
    finishes_verified: bool = False,
    exclusions_verified: bool = False,
) -> GuidedSourceQuestionBundle:
    """Automatic-first question builder fed by real source shadow reports.

    Supports exact `#4790` producer results (`SamePageFiguredScaleReport`,
    `NativeTiledRoomFaceSamePageScaleShadowResult`, `OutlinedDrawingAdmissionReport`,
    `OutlinedDrawingSetIngestionShadowBundle`) and live `DimensionEvidenceBundle`
    from `pb_figured_dimension_evidence`. Never invents a `viewport_id` or missing
    finish specifications.
    """
    suggestions: list[SourceSuggestionProvenance] = []
    scale_verified = False

    if same_page_scale_report is not None:
        # Unwrap NativeTiledRoomFaceSamePageScaleShadowResult if caller passed wrapper
        inner_scale = getattr(same_page_scale_report, "scale_report", same_page_scale_report)
        rep_status = getattr(inner_scale, "status", None)
        rep_sha = getattr(inner_scale, "source_sha256", None)
        rep_page = getattr(inner_scale, "page_number", None)
        rep_vp = getattr(inner_scale, "viewport_id", None)
        rep_receipt = getattr(inner_scale, "receipt_sha256", None)
        rep_mx = getattr(inner_scale, "mm_per_pt_x", None)
        rep_hids = tuple(getattr(inner_scale, "horizontal_witness_ids", ()) or ())
        rep_vids = tuple(getattr(inner_scale, "vertical_witness_ids", ()) or ())
        if (
            rep_status == "CORROBORATED_SAME_PAGE_FIGURED_SCALE_SHADOW"
            and rep_sha == source_sha256
            and rep_page == pdf_page
            and _is_valid_sha256(rep_receipt)
            and _finite_positive_float(rep_mx) is not None
            and (rep_hids or rep_vids)
            and (viewport_id is not None and rep_vp == viewport_id)
        ):
            suggestions.append(
                SourceSuggestionProvenance(
                    issue="scale",
                    source_sha256=source_sha256,
                    pdf_page=pdf_page,
                    viewport_id=viewport_id,
                    evidence_kind="same_page_figured_scale_shadow",
                    source_observation_ids=tuple(sorted(set(rep_hids + rep_vids))),
                    candidate_receipt_sha256=str(rep_receipt),
                    suggested_summary=(
                        f"Same-page viewport-bound orthogonal figured scale shadow "
                        f"({rep_mx} mm/pt) pending confirmation."
                    ),
                )
            )
    elif dimension_evidence_bundle is not None:
        bindings = tuple(getattr(dimension_evidence_bundle, "bindings", ()) or ())
        obs_by_id = {
            getattr(o, "dimension_id", ""): o
            for o in (getattr(dimension_evidence_bundle, "observations", ()) or ())
        }
        witness_bound = [
            b for b in bindings
            if getattr(b, "status", None) == "witness_bound"
            and getattr(b, "endpoints", None) is not None
            and getattr(b, "observation_id", "") in obs_by_id
            and getattr(obs_by_id[getattr(b, "observation_id", "")], "source_page", None) == pdf_page
        ]
        if witness_bound:
            obs_ids = tuple(sorted({str(getattr(b, "observation_id")) for b in witness_bound}))
            cand_receipt = _canonical_json_sha256(
                {
                    "sha": source_sha256,
                    "page": pdf_page,
                    "vp": viewport_id,
                    "witness_bound_obs": list(obs_ids),
                }
            )
            suggestions.append(
                SourceSuggestionProvenance(
                    issue="scale",
                    source_sha256=source_sha256,
                    pdf_page=pdf_page,
                    viewport_id=viewport_id,
                    evidence_kind="figured_dimension_witness_bundle",
                    source_observation_ids=obs_ids,
                    candidate_receipt_sha256=cand_receipt,
                    suggested_summary=(
                        f"{len(obs_ids)} witness-bound figured dimension(s) detected on page {pdf_page} "
                        f"pending user confirmation."
                    ),
                )
            )

    fin_verified = finishes_verified
    if outlined_admission_report is not None:
        inner_adm = getattr(outlined_admission_report, "admission_report", outlined_admission_report)
        fin_status = getattr(inner_adm, "finish_authority_status", None)
        if fin_status == "ABSTAINED":
            fin_verified = False

    return build_guided_review_source_questions(
        source_sha256=source_sha256,
        page_id=page_id,
        pdf_page=pdf_page,
        viewport_id=viewport_id,
        suggestions=tuple(suggestions),
        scale_verified=scale_verified,
        height_verified=height_verified,
        finishes_verified=fin_verified,
        exclusions_verified=exclusions_verified,
    )


def _abstain_handoff(
    *,
    source_sha256: str = "",
    page_id: int = 0,
    pdf_page: int = 0,
    viewport_id: str | None = None,
    review_revision: int = 0,
    packet_sha256: str = "",
    reasons: tuple[str, ...],
) -> ReviewToIssuerHandoffReceipt:
    digest = _canonical_json_sha256(
        {
            "sha": source_sha256,
            "page_id": page_id,
            "page": pdf_page,
            "vp": viewport_id,
            "rev": review_revision,
            "packet_sha": packet_sha256,
            "reasons": list(reasons),
        }
    )
    return ReviewToIssuerHandoffReceipt(
        status="ABSTAINED",
        source_sha256=source_sha256,
        page_id=page_id,
        pdf_page=pdf_page,
        viewport_id=viewport_id,
        review_revision=review_revision,
        source_packet_sha256=packet_sha256,
        actionable_directives=(),
        unresolved_information_requests=(),
        directives=(),
        actionable_affected_issuers=(),
        blocked_information_issuers=(),
        affected_issuers=(),
        handoff_sha256=digest,
        reason_codes=reasons,
    )


def _parse_typed_correction(
    raw: object,
    *,
    packet_viewport_id: str | None,
) -> tuple[TypedReviewCorrectionInput | None, str | None]:
    if not isinstance(raw, Mapping):
        return None, "malformed_review_correction"
    cid = raw.get("correction_id")
    cat = raw.get("category")
    kind = raw.get("kind")
    raw_pts = raw.get("native_points_pdf_pts")
    if (
        type(cid) is not str
        or not _SAFE_ID_RE.fullmatch(cid)
        or cat not in ALLOWED_CORRECTION_CATEGORIES
        or kind not in ("line", "polygon")
        or not isinstance(raw_pts, (list, tuple))
    ):
        return None, "malformed_review_correction"

    min_pts = 3 if kind == "polygon" else 2
    if len(raw_pts) < min_pts:
        return None, "malformed_review_correction"

    parsed_pts: list[tuple[float, float]] = []
    for pt in raw_pts:
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            return None, "malformed_review_correction"
        x, y = pt[0], pt[1]
        if (
            type(x) is bool
            or type(y) is bool
            or not isinstance(x, (int, float))
            or not isinstance(y, (int, float))
            or not (math.isfinite(float(x)) and math.isfinite(float(y)))
        ):
            return None, "malformed_review_correction"
        parsed_pts.append((float(x), float(y)))

    dim_mm: float | None = None
    dim_unit: str | None = None
    if "dimension_mm" in raw and raw.get("dimension_mm") is not None:
        dim_mm = _finite_positive_float(raw.get("dimension_mm"))
        if dim_mm is None:
            return None, "invalid_correction_dimension_value"
        raw_unit = raw.get("dimension_unit", "mm")
        if raw_unit not in ALLOWED_DIMENSION_UNITS:
            return None, "invalid_correction_dimension_unit"
        dim_unit = str(raw_unit)
    elif raw.get("dimension_unit") is not None:
        return None, "invalid_correction_dimension_value"

    ok_obj, target_obj = _clean_optional_id(raw.get("target_object_id"))
    if not ok_obj:
        return None, "malformed_review_correction"
    ok_vp, corr_vp = _clean_optional_id(raw.get("viewport_id"))
    if not ok_vp:
        return None, "malformed_review_correction"
    if corr_vp is not None and packet_viewport_id is not None and corr_vp != packet_viewport_id:
        return None, "correction_viewport_mismatch"
    effective_vp = corr_vp if corr_vp is not None else packet_viewport_id

    auth = raw.get("authority", "user_selected_geometry")
    if auth != "user_selected_geometry":
        return None, "malformed_review_correction"

    return (
        TypedReviewCorrectionInput(
            correction_id=cid,
            category=str(cat),
            kind=str(kind),
            native_points_pdf_pts=tuple(parsed_pts),
            dimension_mm=dim_mm,
            dimension_unit=dim_unit,
            target_object_id=target_obj,
            viewport_id=effective_vp,
            authority="user_selected_geometry",
        ),
        None,
    )


def build_review_to_issuer_handoff(
    *,
    native_review_packet: Mapping[str, Any],
    question_bundle: GuidedSourceQuestionBundle | None = None,
) -> ReviewToIssuerHandoffReceipt:
    """Convert a verified #4791 native review packet into typed issuer handoff directives.

    - Strictly validates `packet_sha256` (integrity only, NOT authentication), `schema_version`,
      `scope` (`workspace_id`, `page_id`, `pdf_page`, `source_sha256`, `image_sha256`, optional
      authenticated `viewport_id`), and non-commercial / non-benchmark flags.
    - Rejects duplicate or malformed `correction_id`s and malformed packet bodies fail-closed.
    - Preserves typed `dimension_mm` / `dimension_unit` and `native_points_pdf_pts`.
    - Only links suggestion receipts when the user explicitly selected `selected_question_id`
      and/or `selected_suggestion_receipt_sha256` with matching scope/viewport/object binding.
    - Separates `ACTIONABLE_USER_CORRECTION` from `NEEDS_INFORMATION_BLOCKER`.
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
    if not isinstance(scope, Mapping):
        return _abstain_handoff(
            packet_sha256=str(packet_sha),
            reasons=("invalid_review_packet_scope_or_revision",),
        )
    ok_pkt_vp, packet_vp = _clean_optional_id(scope.get("viewport_id"))
    if (
        not _is_valid_sha256(scope.get("source_sha256"))
        or not _is_valid_sha256(scope.get("image_sha256"))
        or not _is_positive_int(scope.get("page_id"))
        or not _is_positive_int(scope.get("pdf_page"))
        or not _is_positive_int(scope.get("workspace_id"))
        or not _is_positive_int(review_rev)
        or not ok_pkt_vp
    ):
        return _abstain_handoff(
            packet_sha256=str(packet_sha),
            reasons=("invalid_review_packet_scope_or_revision",),
        )

    src_sha = str(scope["source_sha256"])
    page_id = int(scope["page_id"])
    pdf_page = int(scope["pdf_page"])

    questions_by_id: dict[str, GuidedSourceQuestion] = {}
    if question_bundle is not None:
        if not isinstance(question_bundle, GuidedSourceQuestionBundle):
            return _abstain_handoff(
                source_sha256=src_sha,
                page_id=page_id,
                pdf_page=pdf_page,
                viewport_id=packet_vp,
                review_revision=review_rev,
                packet_sha256=str(packet_sha),
                reasons=("invalid_question_bundle_type",),
            )
        if (
            question_bundle.source_sha256 != src_sha
            or question_bundle.page_id != page_id
            or question_bundle.pdf_page != pdf_page
        ):
            return _abstain_handoff(
                source_sha256=src_sha,
                page_id=page_id,
                pdf_page=pdf_page,
                viewport_id=packet_vp,
                review_revision=review_rev,
                packet_sha256=str(packet_sha),
                reasons=("question_bundle_scope_mismatch",),
            )
        if (
            question_bundle.viewport_id is not None
            and packet_vp is not None
            and question_bundle.viewport_id != packet_vp
        ):
            return _abstain_handoff(
                source_sha256=src_sha,
                page_id=page_id,
                pdf_page=pdf_page,
                viewport_id=packet_vp,
                review_revision=review_rev,
                packet_sha256=str(packet_sha),
                reasons=("question_bundle_viewport_mismatch",),
            )
        questions_by_id = {q.question_id: q for q in question_bundle.questions}

    corrections = native_review_packet.get("corrections")
    answers = native_review_packet.get("unbound_review_answers")
    if not isinstance(corrections, (list, tuple)) or not isinstance(answers, Mapping):
        return _abstain_handoff(
            source_sha256=src_sha,
            page_id=page_id,
            pdf_page=pdf_page,
            viewport_id=packet_vp,
            review_revision=review_rev,
            packet_sha256=str(packet_sha),
            reasons=("invalid_review_packet_body",),
        )

    seen_correction_ids: set[str] = set()
    corrections_by_issue: dict[str, list[TypedReviewCorrectionInput]] = {
        k: [] for k in ALLOWED_QUESTION_ISSUES
    }
    for raw_corr in corrections:
        parsed_corr, err = _parse_typed_correction(raw_corr, packet_viewport_id=packet_vp)
        if err is not None or parsed_corr is None:
            return _abstain_handoff(
                source_sha256=src_sha,
                page_id=page_id,
                pdf_page=pdf_page,
                viewport_id=packet_vp,
                review_revision=review_rev,
                packet_sha256=str(packet_sha),
                reasons=(err or "malformed_review_correction",),
            )
        if parsed_corr.correction_id in seen_correction_ids:
            return _abstain_handoff(
                source_sha256=src_sha,
                page_id=page_id,
                pdf_page=pdf_page,
                viewport_id=packet_vp,
                review_revision=review_rev,
                packet_sha256=str(packet_sha),
                reasons=("duplicate_correction_id_conflict",),
            )
        seen_correction_ids.add(parsed_corr.correction_id)
        if parsed_corr.category == "dimension_witness":
            corrections_by_issue["scale"].append(parsed_corr)
        elif parsed_corr.category == "exclusion":
            corrections_by_issue["exclusions"].append(parsed_corr)

    actionable: list[ReviewToIssuerDirective] = []
    proposals: list[ReviewToIssuerDirective] = []
    unresolved_info: list[ReviewToIssuerDirective] = []
    actionable_issuers: set[str] = set()
    proposed_issuers: set[str] = set()
    blocked_issuers: set[str] = set()
    reasons: set[str] = set()

    for issue in ALLOWED_QUESTION_ISSUES:
        raw_answer = answers.get(issue)
        typed_corrs = tuple(
            sorted(corrections_by_issue[issue], key=lambda c: c.correction_id)
        )
        corr_ids = tuple(c.correction_id for c in typed_corrs)
        decision = ""
        note = ""
        ans_vp: str | None = packet_vp
        ans_obj: str | None = None
        selected_qid: str | None = None
        selected_receipt: str | None = None

        if raw_answer is not None:
            if not isinstance(raw_answer, Mapping):
                return _abstain_handoff(
                    source_sha256=src_sha,
                    page_id=page_id,
                    pdf_page=pdf_page,
                    viewport_id=packet_vp,
                    review_revision=review_rev,
                    packet_sha256=str(packet_sha),
                    reasons=("malformed_review_answer",),
                )
            raw_dec = raw_answer.get("decision")
            if raw_dec not in ALLOWED_DECISIONS:
                return _abstain_handoff(
                    source_sha256=src_sha,
                    page_id=page_id,
                    pdf_page=pdf_page,
                    viewport_id=packet_vp,
                    review_revision=review_rev,
                    packet_sha256=str(packet_sha),
                    reasons=("invalid_review_answer_decision",),
                )
            decision = str(raw_dec)
            note = str(raw_answer.get("note") or "").strip()[:500]
            ok_avp, cleaned_avp = _clean_optional_id(raw_answer.get("viewport_id"))
            ok_aobj, cleaned_aobj = _clean_optional_id(raw_answer.get("target_object_id"))
            ok_qid, cleaned_qid = _clean_optional_id(raw_answer.get("selected_question_id"))
            if not (ok_avp and ok_aobj and ok_qid):
                return _abstain_handoff(
                    source_sha256=src_sha,
                    page_id=page_id,
                    pdf_page=pdf_page,
                    viewport_id=packet_vp,
                    review_revision=review_rev,
                    packet_sha256=str(packet_sha),
                    reasons=("malformed_review_answer_identifiers",),
                )
            if cleaned_avp is not None and packet_vp is not None and cleaned_avp != packet_vp:
                return _abstain_handoff(
                    source_sha256=src_sha,
                    page_id=page_id,
                    pdf_page=pdf_page,
                    viewport_id=packet_vp,
                    review_revision=review_rev,
                    packet_sha256=str(packet_sha),
                    reasons=("review_answer_viewport_mismatch",),
                )
            if cleaned_avp is not None:
                ans_vp = cleaned_avp
            ans_obj = cleaned_aobj

            raw_sel_rec = raw_answer.get("selected_suggestion_receipt_sha256")
            if raw_sel_rec is not None:
                if not _is_valid_sha256(raw_sel_rec):
                    return _abstain_handoff(
                        source_sha256=src_sha,
                        page_id=page_id,
                        pdf_page=pdf_page,
                        viewport_id=packet_vp,
                        review_revision=review_rev,
                        packet_sha256=str(packet_sha),
                        reasons=("invalid_selected_suggestion_receipt_sha256",),
                    )
                selected_receipt = str(raw_sel_rec)
            selected_qid = cleaned_qid

            # Strict explicit selection validation: NEVER implicitly bind a suggestion
            # receipt to a generic page-level answer.
            if selected_qid is not None or selected_receipt is not None:
                if question_bundle is None:
                    return _abstain_handoff(
                        source_sha256=src_sha,
                        page_id=page_id,
                        pdf_page=pdf_page,
                        viewport_id=packet_vp,
                        review_revision=review_rev,
                        packet_sha256=str(packet_sha),
                        reasons=("selected_suggestion_requires_question_bundle",),
                    )
                if selected_qid is None or selected_qid not in questions_by_id:
                    return _abstain_handoff(
                        source_sha256=src_sha,
                        page_id=page_id,
                        pdf_page=pdf_page,
                        viewport_id=packet_vp,
                        review_revision=review_rev,
                        packet_sha256=str(packet_sha),
                        reasons=("selected_question_id_not_found",),
                    )
                matched_q = questions_by_id[selected_qid]
                if matched_q.issue != issue:
                    return _abstain_handoff(
                        source_sha256=src_sha,
                        page_id=page_id,
                        pdf_page=pdf_page,
                        viewport_id=packet_vp,
                        review_revision=review_rev,
                        packet_sha256=str(packet_sha),
                        reasons=("selected_question_issue_mismatch",),
                    )
                if matched_q.viewport_id is not None and ans_vp != matched_q.viewport_id:
                    return _abstain_handoff(
                        source_sha256=src_sha,
                        page_id=page_id,
                        pdf_page=pdf_page,
                        viewport_id=packet_vp,
                        review_revision=review_rev,
                        packet_sha256=str(packet_sha),
                        reasons=("selected_question_viewport_binding_required",),
                    )
                if matched_q.target_object_id is not None and ans_obj != matched_q.target_object_id:
                    return _abstain_handoff(
                        source_sha256=src_sha,
                        page_id=page_id,
                        pdf_page=pdf_page,
                        viewport_id=packet_vp,
                        review_revision=review_rev,
                        packet_sha256=str(packet_sha),
                        reasons=("selected_question_object_binding_required",),
                    )
                if selected_receipt is not None:
                    if (
                        matched_q.suggestion is None
                        or matched_q.suggestion.candidate_receipt_sha256 != selected_receipt
                    ):
                        return _abstain_handoff(
                            source_sha256=src_sha,
                            page_id=page_id,
                            pdf_page=pdf_page,
                            viewport_id=packet_vp,
                            review_revision=review_rev,
                            packet_sha256=str(packet_sha),
                            reasons=("selected_suggestion_provenance_mismatch",),
                        )

        if not typed_corrs and decision not in ("correction_recorded", "needs_information"):
            continue

        issuers = EXISTING_ISSUER_TARGETS[issue]
        # Explicit needs_information ALWAYS vetoes actionability even when draft marks exist.
        if decision == "needs_information":
            effective_decision = "needs_information"
            action_kind = "NEEDS_INFORMATION_BLOCKER"
        elif typed_corrs or (selected_qid is not None and selected_receipt is not None):
            effective_decision = decision or "correction_recorded"
            action_kind = "ACTIONABLE_USER_CORRECTION"
        else:
            # Unbound free-text correction_recorded notes remain non-executable proposals.
            effective_decision = "correction_recorded"
            action_kind = "USER_PROPOSAL_UNBOUND"

        did = "issuer_dir_" + _canonical_json_sha256(
            {
                "packet_sha": str(packet_sha),
                "issue": issue,
                "action_kind": action_kind,
                "decision": effective_decision,
                "corr_ids": list(corr_ids),
                "dims": [(c.correction_id, c.dimension_mm, c.dimension_unit) for c in typed_corrs],
                "vp": ans_vp,
                "obj": ans_obj,
                "qid": selected_qid,
                "sel_rec": selected_receipt,
                "note": note,
            }
        )[:24]
        directive = ReviewToIssuerDirective(
            directive_id=did,
            issue=issue,
            action_kind=action_kind,
            target_issuers=issuers,
            decision=effective_decision,
            user_note=note,
            typed_corrections=typed_corrs,
            linked_correction_ids=corr_ids,
            viewport_id=ans_vp,
            target_object_id=ans_obj,
            selected_question_id=selected_qid,
            selected_suggestion_receipt_sha256=selected_receipt,
        )
        if action_kind == "ACTIONABLE_USER_CORRECTION":
            actionable.append(directive)
            actionable_issuers.update(issuers)
            reasons.add(f"actionable_{issue}_{effective_decision}")
        elif action_kind == "USER_PROPOSAL_UNBOUND":
            proposals.append(directive)
            proposed_issuers.update(issuers)
            reasons.add(f"unbound_proposal_{issue}")
        else:
            unresolved_info.append(directive)
            blocked_issuers.update(issuers)
            reasons.add(f"needs_information_{issue}")

    all_directives = tuple(actionable + proposals + unresolved_info)
    all_issuers = tuple(sorted(actionable_issuers | proposed_issuers | blocked_issuers))
    if actionable:
        status = "USER_ASSISTED_HANDOFF_READY"
    elif proposals:
        status = "USER_PROPOSALS_ONLY"
    elif unresolved_info:
        status = "NEEDS_INFORMATION_ONLY"
    else:
        status = "NO_SOURCE_ISSUER_UPDATES"
        reasons.add("no_scale_height_finish_or_exclusion_updates_in_packet")

    handoff_sha = _canonical_json_sha256(
        {
            "packet_sha": str(packet_sha),
            "status": status,
            "actionable": [d.directive_id for d in actionable],
            "proposals": [d.directive_id for d in proposals],
            "needs_info": [d.directive_id for d in unresolved_info],
            "issuers": list(all_issuers),
        }
    )
    return ReviewToIssuerHandoffReceipt(
        status=status,
        source_sha256=src_sha,
        page_id=page_id,
        pdf_page=pdf_page,
        viewport_id=packet_vp,
        review_revision=review_rev,
        source_packet_sha256=str(packet_sha),
        actionable_directives=tuple(actionable),
        unresolved_information_requests=tuple(unresolved_info),
        directives=all_directives,
        actionable_affected_issuers=tuple(sorted(actionable_issuers)),
        blocked_information_issuers=tuple(sorted(blocked_issuers)),
        affected_issuers=all_issuers,
        handoff_sha256=handoff_sha,
        reason_codes=tuple(sorted(reasons)),
        unbound_proposals=tuple(proposals),
        proposed_affected_issuers=tuple(sorted(proposed_issuers)),
    )


def compute_issuer_invalidation_plan(
    *,
    previous_handoff: ReviewToIssuerHandoffReceipt | None,
    current_handoff: ReviewToIssuerHandoffReceipt,
) -> IssuerInvalidationPlan:
    """Compute conservative downstream stage/issuer invalidation including deletions."""
    if (
        not isinstance(current_handoff, ReviewToIssuerHandoffReceipt)
        or current_handoff.status == "ABSTAINED"
    ):
        return IssuerInvalidationPlan(
            status="ABSTAINED",
            source_sha256="",
            page_id=0,
            pdf_page=0,
            previous_revision=None,
            current_revision=0,
            added_or_modified_issues=(),
            deleted_issues=(),
            invalidated_stages=(),
            invalidated_issuers=(),
            reason_codes=("invalid_or_abstained_current_handoff",),
        )

    def _signature(d: ReviewToIssuerDirective) -> tuple:
        return (
            d.issue,
            d.action_kind,
            d.decision,
            d.user_note,
            d.viewport_id,
            d.target_object_id,
            d.selected_question_id,
            d.selected_suggestion_receipt_sha256,
            tuple(
                (c.correction_id, c.category, c.native_points_pdf_pts, c.dimension_mm, c.dimension_unit)
                for c in d.typed_corrections
            ),
        )

    curr_map = {d.issue: _signature(d) for d in current_handoff.actionable_directives}
    if previous_handoff is None:
        added = tuple(sorted(curr_map))
        stages = tuple(
            s for s in _STAGE_ORDER if any(s in _ISSUE_INVALIDATED_STAGES[i] for i in added)
        )
        issuers = tuple(sorted({iss for i in added for iss in EXISTING_ISSUER_TARGETS[i]}))
        return IssuerInvalidationPlan(
            status="INVALIDATION_REQUIRED" if added else "NO_CHANGES",
            source_sha256=current_handoff.source_sha256,
            page_id=current_handoff.page_id,
            pdf_page=current_handoff.pdf_page,
            previous_revision=None,
            current_revision=current_handoff.review_revision,
            added_or_modified_issues=added,
            deleted_issues=(),
            invalidated_stages=stages,
            invalidated_issuers=issuers,
            reason_codes=(("initial_user_assisted_handoff_invalidation",) if added else ("no_actionable_directives",)),
        )

    if (
        not isinstance(previous_handoff, ReviewToIssuerHandoffReceipt)
        or previous_handoff.status == "ABSTAINED"
        or previous_handoff.source_sha256 != current_handoff.source_sha256
        or previous_handoff.page_id != current_handoff.page_id
        or previous_handoff.pdf_page != current_handoff.pdf_page
    ):
        return IssuerInvalidationPlan(
            status="ABSTAINED",
            source_sha256=current_handoff.source_sha256,
            page_id=current_handoff.page_id,
            pdf_page=current_handoff.pdf_page,
            previous_revision=getattr(previous_handoff, "review_revision", None),
            current_revision=current_handoff.review_revision,
            added_or_modified_issues=(),
            deleted_issues=(),
            invalidated_stages=(),
            invalidated_issuers=(),
            reason_codes=("previous_handoff_scope_mismatch",),
        )

    if previous_handoff.review_revision > current_handoff.review_revision:
        return IssuerInvalidationPlan(
            status="ABSTAINED",
            source_sha256=current_handoff.source_sha256,
            page_id=current_handoff.page_id,
            pdf_page=current_handoff.pdf_page,
            previous_revision=previous_handoff.review_revision,
            current_revision=current_handoff.review_revision,
            added_or_modified_issues=(),
            deleted_issues=(),
            invalidated_stages=(),
            invalidated_issuers=(),
            reason_codes=("review_revision_regression_rejected",),
        )

    if (
        previous_handoff.review_revision == current_handoff.review_revision
        and previous_handoff.handoff_sha256 != current_handoff.handoff_sha256
    ):
        return IssuerInvalidationPlan(
            status="ABSTAINED",
            source_sha256=current_handoff.source_sha256,
            page_id=current_handoff.page_id,
            pdf_page=current_handoff.pdf_page,
            previous_revision=previous_handoff.review_revision,
            current_revision=current_handoff.review_revision,
            added_or_modified_issues=(),
            deleted_issues=(),
            invalidated_stages=(),
            invalidated_issuers=(),
            reason_codes=("conflicting_handoff_at_same_revision",),
        )

    prev_map = {d.issue: _signature(d) for d in previous_handoff.actionable_directives}
    added_or_mod = tuple(
        sorted(i for i, sig in curr_map.items() if prev_map.get(i) != sig)
    )
    deleted = tuple(sorted(i for i in prev_map if i not in curr_map))
    touched = set(added_or_mod) | set(deleted)
    stages = tuple(
        s for s in _STAGE_ORDER if any(s in _ISSUE_INVALIDATED_STAGES[i] for i in touched)
    )
    issuers = tuple(sorted({iss for i in touched for iss in EXISTING_ISSUER_TARGETS[i]}))
    reason_list: list[str] = []
    if added_or_mod:
        reason_list.append("actionable_directives_added_or_modified")
    if deleted:
        reason_list.append("deleted_directives_invalidate_prior_issuer_outputs")
    if not reason_list:
        reason_list.append("handoff_unchanged_no_invalidation")

    return IssuerInvalidationPlan(
        status="INVALIDATION_REQUIRED" if touched else "NO_CHANGES",
        source_sha256=current_handoff.source_sha256,
        page_id=current_handoff.page_id,
        pdf_page=current_handoff.pdf_page,
        previous_revision=previous_handoff.review_revision,
        current_revision=current_handoff.review_revision,
        added_or_modified_issues=added_or_mod,
        deleted_issues=deleted,
        invalidated_stages=stages,
        invalidated_issuers=issuers,
        reason_codes=tuple(reason_list),
    )


def build_user_assisted_scale_issuer_request(
    *,
    handoff: ReviewToIssuerHandoffReceipt,
) -> UserAssistedScaleIssuerRequest:
    """Consumer adapter translating an actionable scale directive for `pb_page_scale_calibration_authority`.

    Requires an actionable `scale` directive containing exactly one `dimension_witness`
    line correction with finite positive `dimension_mm` and non-zero native span length.
    Multiple conflicting witnesses or `NEEDS_INFORMATION_BLOCKER` abstain fail-closed.
    """
    def _abstain(reasons: tuple[str, ...]) -> UserAssistedScaleIssuerRequest:
        return UserAssistedScaleIssuerRequest(
            status="ABSTAINED",
            target_issuer="pb_page_scale_calibration_authority",
            source_sha256=getattr(handoff, "source_sha256", ""),
            page_id=getattr(handoff, "page_id", 0),
            pdf_page=getattr(handoff, "pdf_page", 0),
            viewport_id=getattr(handoff, "viewport_id", None),
            correction_id="",
            native_span_endpoints_pdf_pts=None,
            span_pdf_pts=None,
            figured_mm=None,
            implied_mm_per_pt=None,
            source_handoff_sha256=getattr(handoff, "handoff_sha256", ""),
            reason_codes=reasons,
        )

    if not isinstance(handoff, ReviewToIssuerHandoffReceipt) or handoff.status != "USER_ASSISTED_HANDOFF_READY":
        return _abstain(("no_actionable_user_assisted_handoff",))

    scale_dirs = [d for d in handoff.actionable_directives if d.issue == "scale"]
    if len(scale_dirs) != 1:
        return _abstain(("actionable_scale_directive_unavailable",))

    scale_dir = scale_dirs[0]
    witnesses = [
        c for c in scale_dir.typed_corrections
        if c.category == "dimension_witness" and c.kind == "line"
    ]
    if not witnesses:
        return _abstain(("missing_typed_dimension_witness_correction",))
    if len(witnesses) > 1:
        return _abstain(("ambiguous_multiple_dimension_witness_corrections",))

    wit = witnesses[0]
    if wit.dimension_mm is None or wit.dimension_unit is None:
        return _abstain(("missing_typed_dimension_mm_on_witness",))
    figured_mm = wit.dimension_mm * 1000.0 if wit.dimension_unit == "m" else wit.dimension_mm
    p0, p1 = wit.native_points_pdf_pts[0], wit.native_points_pdf_pts[-1]
    span_pts = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if not math.isfinite(span_pts) or span_pts <= 1e-3:
        return _abstain(("degenerate_zero_length_dimension_witness_span",))
    implied = figured_mm / span_pts
    if not math.isfinite(implied) or implied <= 0.0:
        return _abstain(("invalid_implied_scale_ratio",))

    return UserAssistedScaleIssuerRequest(
        status="USER_ASSISTED_SCALE_INPUT_READY",
        target_issuer="pb_page_scale_calibration_authority",
        source_sha256=handoff.source_sha256,
        page_id=handoff.page_id,
        pdf_page=handoff.pdf_page,
        viewport_id=wit.viewport_id,
        correction_id=wit.correction_id,
        native_span_endpoints_pdf_pts=(p0, p1),
        span_pdf_pts=round(span_pts, 6),
        figured_mm=round(figured_mm, 3),
        implied_mm_per_pt=round(implied, 6),
        source_handoff_sha256=handoff.handoff_sha256,
        reason_codes=("user_assisted_scale_witness_ready_for_calibration_authority",),
    )
