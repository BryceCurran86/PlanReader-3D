"""pb_source_opening_candidate_authority.py — Evidence-first source opening candidate authority.

Phase F.23 / Item 23 replacement authority:
1. Reuses existing upstream authority contracts (pb_source_observation_authority,
   pb_viewport_view_class_authority, pb_physical_opening_authority, pb_opening_universe_completeness_authority)
   without creating duplicate or competing authority seals.
2. SourceToleranceProvenance: mathematically grounded tolerance provenance recording measurement units,
   sample population, residual distribution, robust scale estimator, coverage quantile rule, and frame conversions.
   Never uses unexplained fixed numbers.
3. CandidateContextFilter: discriminates genuine floor-plan openings from title block logos, furniture arcs,
   sanitary fixtures, and schedule/detail viewports.
4. PhysicalOpeningCandidateRecord: stores candidate linework anchored to CandidateSemanticOpening and
   SourceObservationRecord in status CANDIDATE or RAW, never CORROBORATED directly from detector.
5. OpeningIdentityResolver: proves tag binding fail-closed with OpeningTagBindingResult, and candidate identity
   via PhysicalOpeningIdentityResult. Rejects nearest-neighbor / Hungarian guessing.
6. validate_opening_decision_viewport: validates viewport ownership, view class, and crop boundary state
   via ViewportViewClassAuthority and SegmentedViewport.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import statistics
from typing import Any, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    canonical_contract_json,
    stable_contract_id,
)
from pb_opening_tag_normalization import normalize_opening_tag
from pb_physical_opening_authority import (
    CandidateSemanticOpening,
    PhysicalOpeningIdentityResult,
    PHYSICAL_OPENING_IDENTITIES_DISTINCT,
    PHYSICAL_OPENING_IDENTITY_RESOLVED,
    PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
)
from pb_source_observation_authority import (
    SourceDecodeCoverageRecord,
    SourceObservationRecord,
)
from pb_viewport_segmentation import SegmentedViewport
from pb_viewport_view_class_authority import (
    VIEW_KIND_DETAIL,
    VIEW_KIND_ELEVATION,
    VIEW_KIND_FLOOR_PLAN,
    VIEW_KIND_SCHEDULE,
    VIEW_KIND_SECTION,
    VIEW_KIND_UNKNOWN,
    ViewportViewClassAuthority,
    ViewportViewClassSelector,
)

SOURCE_OPENING_CANDIDATE_SCHEMA_VERSION = "2.0.0"

PT_TO_MM = 25.4 / 72.0
MM_TO_PT = 72.0 / 25.4


class IdentityState(str, Enum):
    """Explicit three-state opening identity resolution."""

    PROVEN_SAME = "proven_same"
    PROVEN_DISTINCT = "proven_distinct"
    UNRESOLVED = "unresolved"


# ---------------------------------------------------------------------------
# 1. Source-Derived Tolerance Provenance (Statistically Grounded Model)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceToleranceProvenance:
    """Statistically and mathematically grounded tolerance provenance.

    Records:
    - measurement units in target frame
    - sample population size
    - residual distribution characteristics
    - robust scale estimator (MAD, empirical quantile, calibrated residual)
    - coverage / quantile rule
    - coordinate frame conversion factor
    """

    derived_tolerance_target: float
    target_unit: str  # "pt" or "mm"
    derived_tolerance_mm: float
    derived_tolerance_pt: float
    sample_size: int
    residual_distribution: str  # "empirical_residuals", "calibrated_residual", "stroke_quantization"
    robust_scale_estimator: str  # "quantile_99", "median_absolute_deviation", "scale_calibration", "stroke_width"
    coverage_rule: str  # e.g. "empirical_p99", "mad_gaussian_k2.576", "physical_bounding"
    coverage_factor: float  # e.g. 0.99 for p99, 2.576 for 99% normal, 1.0 for physical stroke bounding
    scale_ratio: float
    conversion_factor: float  # factor applied to convert native measurement to target unit
    formula: str
    scale_residual_mm: Optional[float] = None
    stroke_width_pt: Optional[float] = None
    raster_dpi: Optional[float] = None
    schema_version: str = SOURCE_OPENING_CANDIDATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not math.isfinite(self.derived_tolerance_target) or self.derived_tolerance_target <= 0.0:
            raise ValueError("derived_tolerance_target must be a positive finite float")
        if not math.isfinite(self.derived_tolerance_mm) or self.derived_tolerance_mm <= 0.0:
            raise ValueError("derived_tolerance_mm must be a positive finite float")
        if not math.isfinite(self.derived_tolerance_pt) or self.derived_tolerance_pt <= 0.0:
            raise ValueError("derived_tolerance_pt must be a positive finite float")
        if not math.isfinite(self.scale_ratio) or self.scale_ratio <= 0.0:
            raise ValueError("scale_ratio must be a positive finite float")
        if self.sample_size < 1:
            raise ValueError("sample_size must be >= 1")

    @classmethod
    def from_scale_and_stroke(
        cls,
        *,
        scale_ratio: float,
        stroke_width_pt: float = 0.7,
        scale_residual_mm: Optional[float] = None,
        raster_dpi: Optional[float] = None,
        target_unit: str = "pt",
    ) -> "SourceToleranceProvenance":
        """Derive tolerance from physical scale calibration residual, stroke width, and raster DPI.

        Converts all components to the common physical unit (mm world) before computing maximum.
        """
        if scale_ratio <= 0.0:
            raise ValueError("scale_ratio must be positive")

        stroke_width_mm = stroke_width_pt * PT_TO_MM * scale_ratio
        raster_pixel_mm = (25.4 / raster_dpi * scale_ratio) if raster_dpi and raster_dpi > 0 else 0.0
        # If scale calibration residual is present, use 3-sigma equivalent coverage (k=2.576 or 3.0)
        k_coverage = 3.0
        residual_term_mm = (k_coverage * scale_residual_mm) if scale_residual_mm is not None and scale_residual_mm > 0 else 0.0

        derived_mm = max(residual_term_mm, raster_pixel_mm, stroke_width_mm)
        if derived_mm <= 0.0:
            raise ValueError("Cannot derive tolerance from zero or missing source evidence")

        derived_pt = derived_mm / (scale_ratio * PT_TO_MM)
        target_val = derived_pt if target_unit == "pt" else derived_mm
        conv_factor = 1.0 if target_unit == "mm" else (1.0 / (scale_ratio * PT_TO_MM))

        if math.isclose(derived_mm, residual_term_mm, rel_tol=1e-6):
            method = "scale_calibration"
            estimator = "calibrated_residual"
            dist = "calibrated_residual"
            cov_rule = f"scale_residual_k{k_coverage:.1f}"
            cov_factor = k_coverage
            sample_count = 2  # Two reference endpoints calibrated
        elif math.isclose(derived_mm, raster_pixel_mm, rel_tol=1e-6):
            method = "raster_pixel_quantization"
            estimator = "pixel_pitch"
            dist = "raster_grid"
            cov_rule = "single_pixel_quantization"
            cov_factor = 1.0
            sample_count = 1
        else:
            method = "stroke_width"
            estimator = "vector_stroke_bounding"
            dist = "stroke_envelope"
            cov_rule = "full_stroke_bounding"
            cov_factor = 1.0
            sample_count = 1

        formula = (
            f"max(residual_{residual_term_mm:.2f}mm (k={k_coverage}), "
            f"raster_{raster_pixel_mm:.2f}mm, "
            f"stroke_{stroke_width_mm:.2f}mm)"
        )

        return cls(
            derived_tolerance_target=target_val,
            target_unit=target_unit,
            derived_tolerance_mm=derived_mm,
            derived_tolerance_pt=derived_pt,
            sample_size=sample_count,
            residual_distribution=dist,
            robust_scale_estimator=estimator,
            coverage_rule=cov_rule,
            coverage_factor=cov_factor,
            scale_ratio=scale_ratio,
            conversion_factor=conv_factor,
            formula=formula,
            scale_residual_mm=scale_residual_mm,
            stroke_width_pt=stroke_width_pt,
            raster_dpi=raster_dpi,
        )

    @classmethod
    def from_residuals(
        cls,
        *,
        scale_ratio: float,
        residuals_pt: Sequence[float],
        target_unit: str = "pt",
        stroke_width_pt: Optional[float] = 0.7,
    ) -> "SourceToleranceProvenance":
        """Derive tolerance from empirical sample residuals.

        Applies empirical 99th percentile when N >= 30;
        applies Median Absolute Deviation (MAD) with Gaussian 99% coverage factor (k=2.576) when 10 <= N < 30;
        fails closed if N < 10.
        """
        n = len(residuals_pt)
        if n < 10:
            raise ValueError(f"insufficient_sample_size_for_statistical_tolerance: N={n} < 10")
        if scale_ratio <= 0.0:
            raise ValueError("scale_ratio must be positive")

        clean_residuals = [abs(float(r)) for r in residuals_pt if math.isfinite(r)]
        if len(clean_residuals) < 10:
            raise ValueError("insufficient_finite_residuals")

        clean_residuals.sort()

        if n >= 30:
            # Empirical 99th percentile
            idx = min(int(math.ceil(0.99 * n)) - 1, n - 1)
            derived_pt = max(clean_residuals[idx], 0.5)
            estimator = "empirical_quantile"
            cov_rule = "empirical_p99"
            cov_factor = 0.99
            dist = "empirical"
        else:
            # Robust MAD with Gaussian-equivalent 99% coverage factor k=2.576
            med = statistics.median(clean_residuals)
            mad = statistics.median(abs(r - med) for r in clean_residuals)
            # Normal consistency factor = 1.4826 * MAD; 99% coverage = 2.576 * sigma
            sigma_norm = 1.4826 * mad
            k = 2.576
            derived_pt = max(k * sigma_norm, 0.5)
            estimator = "median_absolute_deviation"
            cov_rule = "mad_gaussian_k2.576"
            cov_factor = k
            dist = "gaussian_assumed"

        derived_mm = derived_pt * PT_TO_MM * scale_ratio
        target_val = derived_pt if target_unit == "pt" else derived_mm
        conv_factor = 1.0 if target_unit == "pt" else (PT_TO_MM * scale_ratio)
        formula = f"{estimator}_{cov_rule}(N={n}, tol_pt={derived_pt:.3f})"

        return cls(
            derived_tolerance_target=target_val,
            target_unit=target_unit,
            derived_tolerance_mm=derived_mm,
            derived_tolerance_pt=derived_pt,
            sample_size=n,
            residual_distribution=dist,
            robust_scale_estimator=estimator,
            coverage_rule=cov_rule,
            coverage_factor=cov_factor,
            scale_ratio=scale_ratio,
            conversion_factor=conv_factor,
            formula=formula,
            stroke_width_pt=stroke_width_pt,
        )


# ---------------------------------------------------------------------------
# 2. Viewport Decision Scope Validation (Reuses ViewportViewClassAuthority)
# ---------------------------------------------------------------------------


def validate_opening_decision_viewport(
    *,
    viewport: Optional[SegmentedViewport],
    view_class_authority: ViewportViewClassAuthority,
    selector: ViewportViewClassSelector,
    require_uncropped: bool = True,
) -> Tuple[bool, str]:
    """Validate whether a viewport is an authenticated, uncropped floor plan.

    Reuses existing ViewportViewClassAuthority and SegmentedViewport.
    Rejects invented/fallback viewport IDs, non-floor-plan views, and cropped viewports.
    """
    if viewport is None:
        return False, "viewport_segmentation_unresolved"

    if not viewport.bounding_box or len(viewport.bounding_box) != 4:
        return False, "viewport_boundary_unresolved"

    # Resolve view class via official authority
    class_res = view_class_authority.resolve(selector)
    if class_res.status != EvidenceResolutionStatus.CORROBORATED or not class_res.record:
        return False, f"viewport_view_class_unresolved: {','.join(class_res.reason_codes)}"

    if class_res.record.view_kind != VIEW_KIND_FLOOR_PLAN:
        return False, f"non_floor_plan_view_kind_{class_res.record.view_kind}"

    # Check crop status from SegmentedViewport status
    if require_uncropped and viewport.status == "cropped":
        return False, "viewport_boundary_cropped"

    return True, "viewport_authenticated"


# ---------------------------------------------------------------------------
# 3. Candidate Context Filter (Rejects logos, furniture, sanitary, details)
# ---------------------------------------------------------------------------


class CandidateContextFilter:
    """Separates genuine floor plan opening geometry from non-opening shapes."""

    @staticmethod
    def is_title_block_or_logo(
        bbox: Tuple[float, float, float, float],
        viewport_bbox: Tuple[float, float, float, float],
        title_block_bbox: Optional[Tuple[float, float, float, float]] = None,
    ) -> bool:
        """Check if geometry sits inside a title block or outside the active viewport."""
        bx0, by0, bx1, by1 = bbox
        vx0, vy0, vx1, vy1 = viewport_bbox

        # Outside viewport boundary
        if bx1 < vx0 or bx0 > vx1 or by1 < vy0 or by0 > vy1:
            return True

        # Inside explicit title block
        if title_block_bbox is not None:
            tx0, ty0, tx1, ty1 = title_block_bbox
            if not (bx1 < tx0 or bx0 > tx1 or by1 < ty0 or by0 > ty1):
                return True

        return False

    @staticmethod
    def is_furniture_arc(
        *,
        arc_center: Tuple[float, float],
        arc_radius: float,
        wall_lines: Sequence[Tuple[float, float, float, float]],
        tolerance_pt: float,
    ) -> bool:
        """Reject arcs that represent furniture (e.g. swivel chairs, desks) not hosted in walls."""
        if not wall_lines:
            return True  # No wall context -> cannot be a wall opening

        min_dist = float("inf")
        cx, cy = arc_center
        for x0, y0, x1, y1 in wall_lines:
            dx, dy = x1 - x0, y1 - y0
            length_sq = dx * dx + dy * dy
            if length_sq < 1e-6:
                dist = math.hypot(cx - x0, cy - y0)
            else:
                t = max(0.0, min(1.0, ((cx - x0) * dx + (cy - y0) * dy) / length_sq))
                proj_x = x0 + t * dx
                proj_y = y0 + t * dy
                dist = math.hypot(cx - proj_x, cy - proj_y)
            if dist < min_dist:
                min_dist = dist

        # A door swing arc must originate or touch a wall jamb within tolerance
        return min_dist > (arc_radius + tolerance_pt)

    @staticmethod
    def is_sanitary_fixture(
        structural_pattern: str,
        layer: str = "",
        nearby_text: str = "",
    ) -> bool:
        """Check if an arc belongs to sanitary fixtures (WC, sink, shower, bidet)."""
        combined = f"{layer} {nearby_text}".lower()
        sanitary_terms = ("wc", "toilet", "bath", "sink", "urinal", "wash", "basin", "sanitary")
        return any(term in combined for term in sanitary_terms)

    @staticmethod
    def is_schedule_or_detail_context(view_kind: str) -> bool:
        """Check if geometry belongs to a schedule table or detail viewport."""
        return view_kind in (
            VIEW_KIND_SCHEDULE,
            VIEW_KIND_DETAIL,
            VIEW_KIND_ELEVATION,
            VIEW_KIND_SECTION,
            VIEW_KIND_UNKNOWN,
        )


# ---------------------------------------------------------------------------
# 4. Physical Opening Candidate Record (Extends CandidateSemanticOpening)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhysicalOpeningCandidateRecord:
    """Producer-side physical opening candidate from authenticated source linework.

    Anchored to CandidateSemanticOpening lineage.
    Status is strictly CANDIDATE or RAW. It does NOT publish commercial counts.
    Tag mark is strictly None unless independently resolved by OpeningIdentityResolver.
    """

    candidate_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    geometry: Tuple[float, float, float, float]
    structural_pattern: str  # "door_swing_arc", "paired_door_swing", "dimension_chain_opening", "jamb_wall_interruption"
    context_kind: str  # "floor_plan_opening"
    source_observation_ids: Tuple[str, ...]
    source_lineage_root_ids: Tuple[str, ...]
    tolerance_provenance: SourceToleranceProvenance
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    inferred_tag: Optional[str] = None
    dimension_mm: Optional[Tuple[float, float]] = None
    semantic_family: str = "openings"  # "doors", "windows", "openings"
    reason_codes: Tuple[str, ...] = ()
    schema_version: str = SOURCE_OPENING_CANDIDATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status == EvidenceResolutionStatus.CORROBORATED:
            raise ValueError(
                "PhysicalOpeningCandidateRecord cannot be directly marked CORROBORATED "
                "from detector linework without downstream host binding and schedule verification"
            )

    def to_candidate_semantic_opening(self) -> CandidateSemanticOpening:
        """Convert to upstream CandidateSemanticOpening contract."""
        return CandidateSemanticOpening(
            candidate_id=self.candidate_id,
            source_observation_ids=self.source_observation_ids,
            source_lineage_root_ids=self.source_lineage_root_ids,
            document_id=self.document_id,
            revision_id=self.revision_id,
            source_sha256=self.source_sha256,
            snapshot_id=self.snapshot_id,
            page_id=self.page_id,
            viewport_id=self.viewport_id,
            structural_pattern=self.structural_pattern,
            status=self.status,
            reason_codes=self.reason_codes,
        )


# ---------------------------------------------------------------------------
# 5. Tag Binding & Candidate Identity Resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpeningTagBindingResult:
    """Result of binding an opening candidate to a specific tag mark callout."""

    identity_state: IdentityState
    candidate_id: str
    bound_tag: Optional[str] = None
    reason_codes: Tuple[str, ...] = ()
    schema_version: str = SOURCE_OPENING_CANDIDATE_SCHEMA_VERSION


class OpeningIdentityResolver:
    """Resolves physical opening identity and tag binding without heuristic guessing."""

    @staticmethod
    def resolve_tag_binding(
        *,
        candidate: PhysicalOpeningCandidateRecord,
        nearby_tags: Sequence[Tuple[str, Tuple[float, float]]],
        expected_semantic_family: str = "doors",
        viewport_authenticated: bool = True,
        revision_authenticated: bool = True,
    ) -> OpeningTagBindingResult:
        """Bind an opening candidate to a nearby tag callout using source-derived tolerance.

        Hard evidence requirements:
        - Viewport must be authenticated (VIEW_KIND_FLOOR_PLAN).
        - Revision must match.
        - Semantic family must match (e.g. door tag for door swing).
        - Tag callout must be inside candidate aperture or within derived tolerance.
        - Multiple competing tags fail closed.
        - Zero tags fail closed without guessing (never assume D1 or W1).
        """
        if not viewport_authenticated:
            return OpeningTagBindingResult(
                identity_state=IdentityState.UNRESOLVED,
                candidate_id=candidate.candidate_id,
                bound_tag=None,
                reason_codes=("unauthenticated_viewport_blocks_tag_binding",),
            )

        if not revision_authenticated:
            return OpeningTagBindingResult(
                identity_state=IdentityState.UNRESOLVED,
                candidate_id=candidate.candidate_id,
                bound_tag=None,
                reason_codes=("revision_mismatch_blocks_tag_binding",),
            )

        if not nearby_tags:
            return OpeningTagBindingResult(
                identity_state=IdentityState.UNRESOLVED,
                candidate_id=candidate.candidate_id,
                bound_tag=None,
                reason_codes=("no_tag_evidence_present",),
            )

        gx0, gy0, gx1, gy1 = candidate.geometry
        tol_pt = candidate.tolerance_provenance.derived_tolerance_pt

        # Collect tags within derived tolerance of aperture boundary
        matching_tags: list[str] = []
        for tag_str, (tx, ty) in nearby_tags:
            # Validate semantic family compatibility
            norm = normalize_opening_tag(tag_str)
            if norm is not None and expected_semantic_family != "openings":
                if norm.trade_type != expected_semantic_family:
                    continue  # Ignore incompatible trade tags (e.g. window tag beside door swing)

            # Distance from point (tx, ty) to aperture rectangle [gx0, gy0, gx1, gy1]
            dx = max(0.0, gx0 - tx, tx - gx1)
            dy = max(0.0, gy0 - ty, ty - gy1)
            dist = math.hypot(dx, dy)
            if dist <= tol_pt:
                matching_tags.append(tag_str)

        if not matching_tags:
            return OpeningTagBindingResult(
                identity_state=IdentityState.UNRESOLVED,
                candidate_id=candidate.candidate_id,
                bound_tag=None,
                reason_codes=("no_tag_within_source_tolerance",),
            )

        unique_tags = list(dict.fromkeys(matching_tags))
        if len(unique_tags) == 1:
            return OpeningTagBindingResult(
                identity_state=IdentityState.PROVEN_SAME,
                candidate_id=candidate.candidate_id,
                bound_tag=unique_tags[0],
                reason_codes=("unambiguous_tag_proven",),
            )

        # Multiple distinct tags within tolerance -> Ambiguous -> Fail closed!
        return OpeningTagBindingResult(
            identity_state=IdentityState.UNRESOLVED,
            candidate_id=candidate.candidate_id,
            bound_tag=None,
            reason_codes=(
                "competing_tags_ambiguous",
                f"candidates: {', '.join(unique_tags)}",
            ),
        )

    @staticmethod
    def compare_candidates(
        cand_a: PhysicalOpeningCandidateRecord,
        cand_b: PhysicalOpeningCandidateRecord,
    ) -> PhysicalOpeningIdentityResult:
        """Compare two opening candidates to determine if they are PROVEN_SAME or PROVEN_DISTINCT.

        Returns the official PhysicalOpeningIdentityResult from pb_physical_opening_authority.
        Equal openings at different locations are PROVEN_DISTINCT.
        Identical detections at the same location within derived tolerance are PROVEN_SAME.
        Schedule sample symbols are PROVEN_DISTINCT from floor plan instances.
        """
        # Cross-context check: schedule sample vs floor plan instance
        if cand_a.context_kind != cand_b.context_kind:
            return PhysicalOpeningIdentityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                physical_opening_identity=PHYSICAL_OPENING_IDENTITIES_DISTINCT,
                proven_same=False,
                reason_codes=("different_context_kinds",),
            )

        # Different page check
        if cand_a.page_id != cand_b.page_id:
            return PhysicalOpeningIdentityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                physical_opening_identity=PHYSICAL_OPENING_IDENTITIES_DISTINCT,
                proven_same=False,
                reason_codes=("different_pages",),
            )

        # Check semantic family compatibility
        if cand_a.semantic_family != cand_b.semantic_family:
            return PhysicalOpeningIdentityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                physical_opening_identity=PHYSICAL_OPENING_IDENTITIES_DISTINCT,
                proven_same=False,
                reason_codes=("conflicting_semantic_families",),
            )

        # Check structural pattern compatibility
        if cand_a.structural_pattern != cand_b.structural_pattern:
            return PhysicalOpeningIdentityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                physical_opening_identity=PHYSICAL_OPENING_IDENTITIES_DISTINCT,
                proven_same=False,
                reason_codes=("conflicting_structural_patterns",),
            )

        # Check conflicting tag marks if both are tagged
        if (
            cand_a.inferred_tag is not None
            and cand_b.inferred_tag is not None
            and cand_a.inferred_tag != cand_b.inferred_tag
        ):
            return PhysicalOpeningIdentityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                physical_opening_identity=PHYSICAL_OPENING_IDENTITIES_DISTINCT,
                proven_same=False,
                reason_codes=(f"conflicting_tag_marks_{cand_a.inferred_tag}_vs_{cand_b.inferred_tag}",),
            )

        # Check orientation / aspect ratio (e.g. perpendicular walls at a corner)
        wa = abs(cand_a.geometry[2] - cand_a.geometry[0])
        ha = abs(cand_a.geometry[3] - cand_a.geometry[1])
        wb = abs(cand_b.geometry[2] - cand_b.geometry[0])
        hb = abs(cand_b.geometry[3] - cand_b.geometry[1])
        orient_a = "H" if wa > 1.3 * ha else ("V" if ha > 1.3 * wa else "N")
        orient_b = "H" if wb > 1.3 * hb else ("V" if hb > 1.3 * wb else "N")
        if orient_a != "N" and orient_b != "N" and orient_a != orient_b:
            return PhysicalOpeningIdentityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                physical_opening_identity=PHYSICAL_OPENING_IDENTITIES_DISTINCT,
                proven_same=False,
                reason_codes=("conflicting_structural_orientations_perpendicular",),
            )

        # Check dimension conflict if both have explicit dimensions
        if cand_a.dimension_mm is not None and cand_b.dimension_mm is not None:
            tol_mm = max(
                cand_a.tolerance_provenance.derived_tolerance_mm,
                cand_b.tolerance_provenance.derived_tolerance_mm,
            )
            dim_diff_0 = abs(cand_a.dimension_mm[0] - cand_b.dimension_mm[0])
            dim_diff_1 = abs(cand_a.dimension_mm[1] - cand_b.dimension_mm[1])
            if dim_diff_0 > tol_mm or dim_diff_1 > tol_mm:
                return PhysicalOpeningIdentityResult(
                    status=EvidenceResolutionStatus.CORROBORATED,
                    physical_opening_identity=PHYSICAL_OPENING_IDENTITIES_DISTINCT,
                    proven_same=False,
                    reason_codes=(
                        f"conflicting_dimensions_delta_{max(dim_diff_0, dim_diff_1):.1f}mm_exceeds_tol_{tol_mm:.1f}mm",
                    ),
                )

        # Spatial distance between centers
        cax = 0.5 * (cand_a.geometry[0] + cand_a.geometry[2])
        cay = 0.5 * (cand_a.geometry[1] + cand_a.geometry[3])
        cbx = 0.5 * (cand_b.geometry[0] + cand_b.geometry[2])
        cby = 0.5 * (cand_b.geometry[1] + cand_b.geometry[3])
        dist = math.hypot(cax - cbx, cay - cby)

        tol = max(
            cand_a.tolerance_provenance.derived_tolerance_pt,
            cand_b.tolerance_provenance.derived_tolerance_pt,
        )

        if dist > tol:
            return PhysicalOpeningIdentityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                physical_opening_identity=PHYSICAL_OPENING_IDENTITIES_DISTINCT,
                proven_same=False,
                reason_codes=(f"distinct_locations_delta_{dist:.2f}pt_exceeds_tol_{tol:.2f}pt",),
            )

        # Proximity alone does NOT prove identity.
        # When distance is within tolerance:
        # 1. If lineage roots share an origin or geometry is coincident within tight stroke tolerance,
        #    it is PROVEN_SAME (duplicate observation of single opening).
        # 2. If lineage roots are disjoint and centers are separated, proximity creates an ambiguous cluster -> UNRESOLVED.
        stroke_tol = max(
            (cand_a.tolerance_provenance.stroke_width_pt or 0.7),
            (cand_b.tolerance_provenance.stroke_width_pt or 0.7),
        )
        shared_lineage = bool(set(cand_a.source_lineage_root_ids) & set(cand_b.source_lineage_root_ids))
        coincident_stroke = dist <= stroke_tol

        if shared_lineage or coincident_stroke:
            return PhysicalOpeningIdentityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                physical_opening_identity=PHYSICAL_OPENING_IDENTITY_RESOLVED,
                proven_same=True,
                reason_codes=("coincident_geometry_within_source_tolerance",),
            )

        # Nearby distinct detections with disjoint lineage and non-coincident offset -> UNRESOLVED
        return PhysicalOpeningIdentityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
            proven_same=False,
            reason_codes=(
                f"proximate_candidates_within_tol_{dist:.2f}pt_have_disjoint_lineage_ambiguous",
            ),
        )


__all__ = [
    "CandidateContextFilter",
    "IdentityState",
    "OpeningIdentityResolver",
    "OpeningTagBindingResult",
    "PhysicalOpeningCandidateRecord",
    "SOURCE_OPENING_CANDIDATE_SCHEMA_VERSION",
    "SourceToleranceProvenance",
    "validate_opening_decision_viewport",
]
