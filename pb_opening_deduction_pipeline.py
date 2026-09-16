"""pb_opening_deduction_pipeline.py — Generic Opening Deduction Pipeline.

PR F.9: Deducts evidenced door and window opening areas from walling and wall finishes.

CRITICAL ARCHITECTURAL BOUNDARY:
- Strictly generic, deterministic geometry and schedule evidence.
- Zero knowledge of benchmark IDs, ground truth BOQs, or project-specific answers.
- Inputs must come ONLY from:
  1. parsed wall geometry (length, perimeter, height)
  2. parsed opening width/height (figured dimensions or schedule dimensions)
  3. counted schedule / tag quantities
  4. wall/opening spatial binding or envelope membership
  5. valid drawing scale.
- FAIL CLOSED:
  1. If opening height or width is unknown: that opening's own deduction is
     0.0, marked unresolved. Do not guess.
  2. Opening-to-wall binding is accepted ONLY from an independently
     authenticated source (see bind_openings_to_walls); nothing here
     performs heuristic binding, so until a reconciled host-binding
     authority supplies one, every opening is provisional/unbound.
  3. Caller-populated ``bound_wall_id`` may be used by the explicitly
     provisional arithmetic helper, but it can never establish authority.
     The public authority-producing path abstains until producer-owned host
     binding is wired.
  4. A wall whose deduction authority is unavailable or incomplete has an
     UNKNOWN net area, not an evidenced zero-deduction net area. Publication
     is blocked (quantity=None) rather than silently treating a diagnostic
     arithmetic result as final.
  5. Zero generic fenestration percentages (never assume 10%, 15%, etc.).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from pb_migration_contracts import QuantityEvidence, stable_contract_id


class OpeningDeductionStatus(str, Enum):
    """Lifecycle status for opening deduction processing."""

    APPLIED = "applied"
    PROVISIONAL_UNBOUND = "provisional_unbound"
    UNRESOLVED_MISSING_DIMENSIONS = "unresolved_missing_dimensions"
    INVALID_DIMENSIONS = "invalid_dimensions"


@dataclass
class OpeningInstance:
    """An individual opening or opening group (e.g. W1, D1) from schedule/callouts."""

    opening_id: str
    trade_type: str = "windows"
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    quantity: float = 1.0
    bound_wall_id: Optional[str] = None
    source_page: Optional[int] = None
    bounding_box: Optional[List[float]] = None
    status: OpeningDeductionStatus = OpeningDeductionStatus.PROVISIONAL_UNBOUND
    notes: str = ""

    @property
    def single_area_m2(self) -> Optional[float]:
        """Gross area of a single opening in square meters."""
        if (
            self.width_m is not None
            and self.height_m is not None
            and self.width_m > 0.0
            and self.height_m > 0.0
        ):
            return round(self.width_m * self.height_m, 4)
        return None

    @property
    def total_area_m2(self) -> Optional[float]:
        """Total area of this opening type across its quantity in square meters."""
        single = self.single_area_m2
        if single is not None and self.quantity > 0:
            return round(single * self.quantity, 4)
        return None

    @property
    def is_valid_deduction(self) -> bool:
        """Arithmetic eligibility only; this property does not prove host authority."""
        return (
            self.width_m is not None
            and self.height_m is not None
            and self.width_m > 0.0
            and self.height_m > 0.0
            and self.quantity > 0.0
            and self.bound_wall_id is not None
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opening_id": self.opening_id,
            "trade_type": self.trade_type,
            "width_m": self.width_m,
            "height_m": self.height_m,
            "quantity": self.quantity,
            "bound_wall_id": self.bound_wall_id,
            "single_area_m2": self.single_area_m2,
            "total_area_m2": self.total_area_m2,
            "status": self.status.value,
            "source_page": self.source_page,
            "bounding_box": self.bounding_box,
            "notes": self.notes,
        }


@dataclass
class WallInstance:
    """A wall element or aggregate perimeter walling envelope."""

    wall_id: str
    length_m: Optional[float] = None
    height_m: Optional[float] = None
    gross_area_m2: float = 0.0
    bounding_box: Optional[List[float]] = None
    trade_type: str = "walls"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wall_id": self.wall_id,
            "length_m": self.length_m,
            "height_m": self.height_m,
            "gross_area_m2": round(self.gross_area_m2, 2),
            "bounding_box": self.bounding_box,
            "trade_type": self.trade_type,
        }


@dataclass
class ProvisionalWallDeductionArithmetic:
    """Deterministic diagnostic arithmetic with deliberately no authority field.

    Callers may supply synthetic ``bound_wall_id`` values to exercise arithmetic
    mutations.  This object is not a quantity-evidence contract and cannot be
    propagated as final net-wall authority.
    """

    wall_id: str
    gross_area_m2: float
    total_deducted_area_m2: float
    net_area_m2: float
    applied_openings: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_openings: List[Dict[str, Any]] = field(default_factory=list)
    unbound_openings: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class WallDeductionResult:
    """Wall deduction result plus an explicit authority proposition.

    ``net_area_m2`` is always only the best-known arithmetic estimate.  It is
    authoritative only when ``net_area_evidence`` says so.  On the current
    architecture there is no producer-owned host-binding integration here, so
    this public result always carries ABSTAINED evidence and ``value=None``.
    """

    wall_id: str
    gross_area_m2: float
    total_deducted_area_m2: float
    net_area_m2: float
    net_area_evidence: Optional[QuantityEvidence] = None
    applied_openings: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_openings: List[Dict[str, Any]] = field(default_factory=list)
    unbound_openings: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wall_id": self.wall_id,
            "gross_area_m2": round(self.gross_area_m2, 2),
            "total_deducted_area_m2": round(self.total_deducted_area_m2, 2),
            "net_area_m2": round(self.net_area_m2, 2),
            "net_area_evidence": asdict(self.net_area_evidence) if self.net_area_evidence else None,
            "applied_openings": self.applied_openings,
            "unresolved_openings": self.unresolved_openings,
            "unbound_openings": self.unbound_openings,
        }


class GenericOpeningDeductionPipeline:
    """Orchestrates fail-closed opening deductions and publication gating."""

    def bind_openings_to_walls(
        self,
        openings: Sequence[OpeningInstance],
        walls: Sequence[WallInstance],
    ) -> None:
        """Refuse every caller/heuristic host claim until host-binding v3 exists."""
        del walls
        for opening in openings:
            opening.bound_wall_id = None
            opening.status = OpeningDeductionStatus.PROVISIONAL_UNBOUND
            opening.notes = (
                "No producer-owned host-binding authority result available; "
                "refusing self-certified or heuristic binding."
            )

    def calculate_provisional_wall_deductions(
        self,
        wall: WallInstance,
        openings: Sequence[OpeningInstance],
    ) -> ProvisionalWallDeductionArithmetic:
        """Calculate arithmetic only; never mint quantity or host authority.

        This helper intentionally permits synthetic ``bound_wall_id`` values so
        deterministic arithmetic remains unit-testable.  A caller-provided
        binding is treated only as an arithmetic routing instruction here.
        """
        applied: List[Dict[str, Any]] = []
        unresolved: List[Dict[str, Any]] = []
        unbound: List[Dict[str, Any]] = []
        total_deduction = 0.0

        for opening in openings:
            if opening.bound_wall_id != wall.wall_id:
                if opening.bound_wall_id is None:
                    opening.status = OpeningDeductionStatus.PROVISIONAL_UNBOUND
                    unbound.append(opening.to_dict())
                continue

            if opening.width_m is None or opening.height_m is None:
                opening.status = OpeningDeductionStatus.UNRESOLVED_MISSING_DIMENSIONS
                opening.notes = "Missing figured width or height; fail-closed without guessing deduction."
                unresolved.append(opening.to_dict())
                continue

            if opening.width_m <= 0.0 or opening.height_m <= 0.0 or opening.quantity <= 0.0:
                opening.status = OpeningDeductionStatus.INVALID_DIMENSIONS
                opening.notes = "Non-positive dimension or quantity; deduction rejected."
                unresolved.append(opening.to_dict())
                continue

            opening.status = OpeningDeductionStatus.APPLIED
            opening.notes = (
                "Applied to provisional arithmetic only; host authority has not been established."
            )
            opening_area = opening.total_area_m2 or 0.0
            total_deduction += opening_area
            applied.append(opening.to_dict())

        total_deduction = round(total_deduction, 2)
        net_area = round(max(0.0, wall.gross_area_m2 - total_deduction), 2)
        return ProvisionalWallDeductionArithmetic(
            wall_id=wall.wall_id,
            gross_area_m2=round(wall.gross_area_m2, 2),
            total_deducted_area_m2=total_deduction,
            net_area_m2=net_area,
            applied_openings=applied,
            unresolved_openings=unresolved,
            unbound_openings=unbound,
        )

    def calculate_wall_deductions(
        self,
        wall: WallInstance,
        openings: Sequence[OpeningInstance],
    ) -> WallDeductionResult:
        """Public authority-producing calculation; currently always abstains.

        The arithmetic is still exposed for diagnostics, but neither a
        caller-populated ``bound_wall_id`` nor an empty/local opening set can
        establish producer-owned host binding or opening-universe completeness.
        A future integration may replace this blocker only with sealed
        producer-owned host-binding v3 evidence.
        """
        provisional = self.calculate_provisional_wall_deductions(wall, openings)
        blocking_reasons = (
            "producer_owned_host_binding_authority_unavailable",
            *(
                f"unresolved_dimensions:{entry['opening_id']}"
                for entry in provisional.unresolved_openings
            ),
            *(f"unbound:{entry['opening_id']}" for entry in provisional.unbound_openings),
        )
        evidence = QuantityEvidence(
            quantity_id=stable_contract_id(
                "wall_net_area",
                {
                    "wall_id": wall.wall_id,
                    "gross_area_m2": wall.gross_area_m2,
                    "provisional_total_deducted_area_m2": provisional.total_deducted_area_m2,
                    "opening_ids": tuple(opening.opening_id for opening in openings),
                    "authority_available": False,
                },
            ),
            family="wall_net_area",
            semantic_key=wall.wall_id,
            value=None,
            unit="m2",
            input_entity_ids=(wall.wall_id,) + tuple(opening.opening_id for opening in openings),
            formula="gross_area_m2 - sum(provisional_opening_areas)",
            authority="pb_opening_deduction_pipeline.calculate_wall_deductions",
            status="abstained",
            abstained=True,
            blocking_reasons=tuple(dict.fromkeys(blocking_reasons)),
            reason_codes=("producer_owned_host_binding_required",),
        )
        return WallDeductionResult(
            wall_id=provisional.wall_id,
            gross_area_m2=provisional.gross_area_m2,
            total_deducted_area_m2=provisional.total_deducted_area_m2,
            net_area_m2=provisional.net_area_m2,
            net_area_evidence=evidence,
            applied_openings=provisional.applied_openings,
            unresolved_openings=provisional.unresolved_openings,
            unbound_openings=provisional.unbound_openings,
        )

    def deduct_openings_for_all_walls(
        self,
        walls: Sequence[WallInstance],
        openings: Sequence[OpeningInstance],
    ) -> Dict[str, WallDeductionResult]:
        """Refuse host self-certification, then compute blocked diagnostics."""
        self.bind_openings_to_walls(openings, walls)
        return {wall.wall_id: self.calculate_wall_deductions(wall, openings) for wall in walls}

    def propagate_to_predictions(
        self,
        predictions: Sequence[Any],
        results: Dict[str, WallDeductionResult],
    ) -> List[Any]:
        """Propagate only authoritative net area; otherwise publish ``None``.

        Until host-binding v3 is integrated, results produced by this module
        are ABSTAINED and only their provisional arithmetic is retained in
        diagnostic metadata.
        """
        primary_res = (
            results.get("perimeter_walling")
            or results.get("external_walling")
            or (list(results.values())[0] if results else None)
        )
        if not primary_res:
            return list(predictions)

        evidence = primary_res.net_area_evidence
        abstained = evidence is None or evidence.abstained

        out_preds = []
        for prediction in predictions:
            tag = prediction.tag if hasattr(prediction, "tag") else prediction.get("tag", "")
            is_walling = tag in (
                "perimeter_walling",
                "external_walling",
                "masonry_walling",
                "block_walling",
            )
            is_wall_finish = tag in (
                "internal_plaster",
                "internal_paint",
                "external_key_pointing",
                "external_render",
            )
            if not (is_walling or is_wall_finish):
                out_preds.append(prediction)
                continue

            metadata = prediction.metadata if hasattr(prediction, "metadata") else prediction.get("metadata", {})
            independent_gross = metadata.get("independent_gross_area_m2")
            if independent_gross is not None:
                provisional_net = round(
                    independent_gross - primary_res.total_deducted_area_m2, 4
                )
            else:
                provisional_net = primary_res.net_area_m2

            metadata["gross_area_m2"] = (
                independent_gross if independent_gross is not None else primary_res.gross_area_m2
            )
            metadata["total_deducted_opening_area_m2"] = primary_res.total_deducted_area_m2
            metadata["applied_openings"] = primary_res.applied_openings
            metadata["unresolved_openings"] = primary_res.unresolved_openings
            metadata["unbound_openings"] = primary_res.unbound_openings

            if abstained:
                net_value = None
                metadata["net_area_m2"] = None
                metadata["provisional_net_area_m2"] = provisional_net
                metadata["publication_blocked"] = True
                metadata["reconciliation_status"] = "ambiguous_unresolved"
                metadata["blocking_reason"] = (
                    "opening_deduction_authority_unavailable: producer-owned host binding "
                    "and complete opening scope are not yet established; "
                    "provisional_net_area_m2 is diagnostic only"
                )
            else:
                net_value = provisional_net
                metadata["net_area_m2"] = net_value

            if hasattr(prediction, "quantity"):
                prediction.quantity = net_value
                prediction.metadata = metadata
            else:
                prediction["quantity"] = net_value
                prediction["metadata"] = metadata
            out_preds.append(prediction)

        return out_preds
