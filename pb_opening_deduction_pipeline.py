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
  3. A wall whose deduction is incomplete (any unresolved or unbound
     opening) has an UNKNOWN net area, not an evidenced zero-deduction net
     area -- see WallDeductionResult.net_area_evidence. Publication is
     blocked (quantity=None) rather than silently treating the unknown as
     the gross value.
  4. Zero generic fenestration percentages (never assume 10%, 15%, etc.).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

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
    trade_type: str = "windows"  # "windows", "doors", "opening"
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
        s = self.single_area_m2
        if s is not None and self.quantity > 0:
            return round(s * self.quantity, 4)
        return None

    @property
    def is_valid_deduction(self) -> bool:
        """True only if dimensions are strictly positive and wall binding exists."""
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
class WallDeductionResult:
    """Comprehensive deduction result for a wall, including audit breakdown.

    ``net_area_m2`` is retained for backward compatibility and always carries
    the best-known numeric estimate (gross minus whatever WAS deductible),
    even when incomplete -- it must never be treated as final on its own.
    ``net_area_evidence`` is the authoritative proposition: a true evidenced
    zero (``abstained=False, value=0.0``) is a different state from an
    unknown/incomplete deduction (``abstained=True, value=None``). Consumers
    that care whether net area is actually final must check
    ``net_area_evidence.abstained``, not just read ``net_area_m2``.
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
    """Orchestrates opening-to-wall binding, opening area computation, and net wall area derivation."""

    def __init__(self) -> None:
        pass

    def bind_openings_to_walls(
        self,
        openings: Sequence[OpeningInstance],
        walls: Sequence[WallInstance],
        *,
        authenticated_host_bindings: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Bind openings to walls ONLY from an independently authenticated source.

        No heuristic binding is performed here. Specifically REMOVED, and not
        replaced with any new heuristic:
        - trusting a caller-populated ``opening.bound_wall_id`` at face value
          (a caller asserting a binding is not proof of one);
        - the "exactly one wall exists" shortcut (co-incidentally binding
          every opening to the sole wall is not evidence that opening
          actually pierces that wall);
        - bounding-box intersection as a proxy for physical hosting;
        - any nearest/first/proximity fallback.

        ``authenticated_host_bindings`` is the ONLY trusted source: a mapping
        of ``opening_id -> wall_id`` where each entry has already been
        independently proven by a reconciled host-binding authority (see
        pb_opening_host_binding_authority.py) elsewhere, before this method
        is ever called. Until that authority is wired up here, no caller
        supplies this mapping, so every opening is correctly
        PROVISIONAL_UNBOUND -- fail closed rather than guess. Mutates
        opening.bound_wall_id and opening.status.
        """
        wall_ids = {w.wall_id for w in walls}
        bindings = authenticated_host_bindings or {}

        for op in openings:
            candidate_wall_id = bindings.get(op.opening_id)
            if candidate_wall_id and candidate_wall_id in wall_ids:
                op.bound_wall_id = candidate_wall_id
                continue

            op.bound_wall_id = None
            op.status = OpeningDeductionStatus.PROVISIONAL_UNBOUND
            op.notes = (
                "No independently authenticated host-wall binding available "
                "for this opening; refusing heuristic binding."
            )

    def calculate_wall_deductions(
        self,
        wall: WallInstance,
        openings: Sequence[OpeningInstance],
    ) -> WallDeductionResult:
        """Calculate total opening deductions and net wall area for a specific wall.

        Enforces strict fail-closed behavior:
        - Unknown width or height -> 0.0 deduction, recorded as UNRESOLVED_MISSING_DIMENSIONS.
        - Non-positive dimensions -> 0.0 deduction, recorded as INVALID_DIMENSIONS.
        - Unbound openings -> 0.0 deduction, recorded as PROVISIONAL_UNBOUND.
        """
        applied: List[Dict[str, Any]] = []
        unresolved: List[Dict[str, Any]] = []
        unbound: List[Dict[str, Any]] = []
        total_deduction = 0.0

        for op in openings:
            if op.bound_wall_id != wall.wall_id:
                if op.bound_wall_id is None:
                    op.status = OpeningDeductionStatus.PROVISIONAL_UNBOUND
                    unbound.append(op.to_dict())
                continue

            # Fail-closed check: missing dimensions
            if op.width_m is None or op.height_m is None:
                op.status = OpeningDeductionStatus.UNRESOLVED_MISSING_DIMENSIONS
                op.notes = "Missing figured width or height; fail-closed without guessing deduction."
                unresolved.append(op.to_dict())
                continue

            # Fail-closed check: non-positive dimensions
            if op.width_m <= 0.0 or op.height_m <= 0.0 or op.quantity <= 0.0:
                op.status = OpeningDeductionStatus.INVALID_DIMENSIONS
                op.notes = "Non-positive dimension or quantity; deduction rejected."
                unresolved.append(op.to_dict())
                continue

            # Valid evidenced opening
            op.status = OpeningDeductionStatus.APPLIED
            op_area = op.total_area_m2 or 0.0
            total_deduction += op_area
            applied.append(op.to_dict())

        total_deduction = round(total_deduction, 2)
        net_area = round(max(0.0, wall.gross_area_m2 - total_deduction), 2)

        abstained = bool(unresolved) or bool(unbound)
        blocking_reasons = tuple(
            f"unresolved_dimensions:{entry['opening_id']}" for entry in unresolved
        ) + tuple(f"unbound:{entry['opening_id']}" for entry in unbound)
        net_area_evidence = QuantityEvidence(
            quantity_id=stable_contract_id(
                "wall_net_area",
                {
                    "wall_id": wall.wall_id,
                    "gross_area_m2": wall.gross_area_m2,
                    "applied_openings": applied,
                    "unresolved_openings": unresolved,
                    "unbound_openings": unbound,
                },
            ),
            family="wall_net_area",
            semantic_key=wall.wall_id,
            value=None if abstained else net_area,
            unit="m2",
            input_entity_ids=(wall.wall_id,) + tuple(op.opening_id for op in openings),
            formula="gross_area_m2 - sum(applied_opening_areas)",
            authority="pb_opening_deduction_pipeline.calculate_wall_deductions",
            status="abstained" if abstained else "corroborated",
            abstained=abstained,
            blocking_reasons=blocking_reasons,
            reason_codes=("opening_deduction_incomplete",) if abstained else ("opening_deduction_complete",),
        )

        return WallDeductionResult(
            wall_id=wall.wall_id,
            gross_area_m2=round(wall.gross_area_m2, 2),
            total_deducted_area_m2=total_deduction,
            net_area_m2=net_area,
            net_area_evidence=net_area_evidence,
            applied_openings=applied,
            unresolved_openings=unresolved,
            unbound_openings=unbound,
        )

    def deduct_openings_for_all_walls(
        self,
        walls: Sequence[WallInstance],
        openings: Sequence[OpeningInstance],
        *,
        authenticated_host_bindings: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, WallDeductionResult]:
        """Perform opening-to-wall binding and compute deduction results for all walls."""
        self.bind_openings_to_walls(
            openings, walls, authenticated_host_bindings=authenticated_host_bindings
        )
        results: Dict[str, WallDeductionResult] = {}
        for w in walls:
            results[w.wall_id] = self.calculate_wall_deductions(w, openings)
        return results

    def propagate_to_predictions(
        self,
        predictions: Sequence[Any],
        results: Dict[str, WallDeductionResult],
    ) -> List[Any]:
        """Propagate net wall area and audit metadata to walling and wall finish predictions.

        Propagates to:
        - perimeter_walling (or masonry/block walling)
        - internal_plaster
        - internal_paint
        - external_key_pointing
        - external_render
        """
        # Collect primary envelope wall deduction result (if available)
        primary_res = (
            results.get("perimeter_walling")
            or results.get("external_walling")
            or (list(results.values())[0] if results else None)
        )

        if not primary_res:
            return list(predictions)

        # An unresolved or unbound opening contributes zero to
        # total_deducted_area_m2 (see calculate_wall_deductions), so
        # net_area_m2 is only the gross area minus whatever COULD be
        # deducted, not minus everything that SHOULD be -- an unknown
        # deduction, not an evidenced zero one. net_area_evidence.abstained
        # is the authoritative signal (see WallDeductionResult docstring);
        # a bare numeric net_area_m2 must never be trusted as final on its
        # own. When abstained, publish quantity=None rather than silently
        # converting the unknown back to a number -- this is itself already
        # a recognized block signal (see extracted_prediction_publication_blocked's
        # own `pred.quantity is None` check in pb_planreader_pdf_extractor.py),
        # and is reinforced with the same publication_blocked/
        # reconciliation_status convention used elsewhere in that file. The
        # best-known (unreliable) figure is retained under a clearly
        # provisional-only key for diagnostics, never under net_area_m2 or
        # quantity.
        evidence = primary_res.net_area_evidence
        abstained = evidence.abstained if evidence is not None else (
            bool(primary_res.unresolved_openings) or bool(primary_res.unbound_openings)
        )

        out_preds = []
        for p in predictions:
            p_tag = p.tag if hasattr(p, "tag") else p.get("tag", "")
            p_trade = p.trade_type if hasattr(p, "trade_type") else p.get("trade_type", "")

            is_walling = p_tag in ("perimeter_walling", "external_walling", "masonry_walling", "block_walling")
            is_wall_finish = p_tag in (
                "internal_plaster",
                "internal_paint",
                "external_key_pointing",
                "external_render",
            )

            if is_walling or is_wall_finish:
                gross_val = p.quantity if hasattr(p, "quantity") else p.get("quantity", 0.0)
                meta = p.metadata if hasattr(p, "metadata") else p.get("metadata", {})

                # A wall-finish prediction with its own independently-derived
                # gross area (e.g. a genuine internal-face area computed from
                # real wall-thickness evidence, distinct from the external
                # wall's gross area) still needs the SAME openings deducted
                # -- they pierce the same wall regardless of which face is
                # being measured -- but must not be silently overwritten
                # with the external wall's net_area_m2 as if it were a copy.
                independent_gross = meta.get("independent_gross_area_m2")
                if independent_gross is not None:
                    provisional_net = round(independent_gross - primary_res.total_deducted_area_m2, 4)
                else:
                    provisional_net = primary_res.net_area_m2

                meta["gross_area_m2"] = independent_gross if independent_gross is not None else primary_res.gross_area_m2
                meta["total_deducted_opening_area_m2"] = primary_res.total_deducted_area_m2
                meta["applied_openings"] = primary_res.applied_openings
                meta["unresolved_openings"] = primary_res.unresolved_openings
                meta["unbound_openings"] = primary_res.unbound_openings

                if abstained:
                    net_val = None
                    meta["net_area_m2"] = None
                    meta["provisional_net_area_m2"] = provisional_net
                    meta["publication_blocked"] = True
                    meta["reconciliation_status"] = "ambiguous_unresolved"
                    meta["blocking_reason"] = (
                        "opening_deduction_incomplete: one or more openings on this "
                        "wall are unresolved or unbound, so the true net area is "
                        "unknown, not zero -- provisional_net_area_m2 is a diagnostic "
                        "estimate only, never a final quantity"
                    )
                else:
                    net_val = provisional_net
                    meta["net_area_m2"] = net_val

                if hasattr(p, "quantity"):
                    p.quantity = net_val
                    p.metadata = meta
                    out_preds.append(p)
                else:
                    p["quantity"] = net_val
                    p["metadata"] = meta
                    out_preds.append(p)
            else:
                out_preds.append(p)

        return out_preds
