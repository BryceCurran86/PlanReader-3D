"""Benchmark vs Customer Runtime Authority Parity Harness (AG-15).

Answers the core integration question:
"For the same source drawing/evidence, did the benchmark path and customer runtime
consume the same production authority?"

Catches:
1. Benchmark-only authority (benchmark used an authority that customer runtime failed to consume)
2. Customer-only fallback (customer fell back to heuristics when authenticated evidence existed)
3. Different opening deduction logic (opening deduction discrepancy between benchmark and customer)
4. Different wall identity (inconsistent or collapsed wall references across paths)
5. Different quantity basis (discrepancy in measurement formula or calculation basis)

Core Invariant:
Zero modification to benchmark truth, golden quantities, scoring, or acceptance rules.
This is a diagnostic verification and integration harness.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


class ParityDivergenceType(Enum):
    BENCHMARK_ONLY_AUTHORITY = "benchmark_only_authority"
    CUSTOMER_ONLY_FALLBACK = "customer_only_fallback"
    DIFFERENT_OPENING_DEDUCTION = "different_opening_deduction"
    DIFFERENT_WALL_IDENTITY = "different_wall_identity"
    DIFFERENT_QUANTITY_BASIS = "different_quantity_basis"


@dataclass
class AuthorityTrace:
    """Execution trace of an extraction or takeoff path (benchmark or customer)."""
    path_name: str                             # "benchmark" or "customer"
    primary_authority: str                     # e.g. "pb_live_physical_net_wall_integration"
    is_fallback: bool                          # True if fallback heuristics were used
    wall_identities: Set[str] = field(default_factory=set)
    opening_deductions_m2: Dict[str, float] = field(default_factory=dict)
    quantity_basis: Dict[str, str] = field(default_factory=dict)
    published_quantities: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParityComparisonResult:
    """Diagnostic comparison between benchmark authority and customer runtime."""
    is_in_parity: bool
    divergences: List[Dict[str, Any]] = field(default_factory=list)
    benchmark_authority: str = ""
    customer_authority: str = ""
    matched_walls: Set[str] = field(default_factory=set)
    quantity_differences: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        if self.is_in_parity:
            return "PARITY PROVEN: Benchmark and Customer runtime consumed the same production authority."
        issues = [f"{d['type']}: {d['message']}" for d in self.divergences]
        return f"PARITY DIVERGENCE DETECTED ({len(self.divergences)} issue(s)):\n  - " + "\n  - ".join(issues)


class BenchmarkCustomerParityHarness:
    """Parity auditor comparing benchmark authority traces with customer runtime traces."""

    def compare_traces(
        self,
        benchmark_trace: AuthorityTrace,
        customer_trace: AuthorityTrace,
        tolerance_m2: float = 0.05,
    ) -> ParityComparisonResult:
        """Compare two execution traces on the same source drawing/evidence."""
        divergences: List[Dict[str, Any]] = []

        # 1. Check for Benchmark-Only Authority
        if benchmark_trace.primary_authority and not benchmark_trace.is_fallback:
            if customer_trace.is_fallback:
                divergences.append({
                    "type": ParityDivergenceType.CUSTOMER_ONLY_FALLBACK.value,
                    "message": (
                        f"Customer path used fallback heuristics while benchmark consumed authenticated authority "
                        f"'{benchmark_trace.primary_authority}'."
                    ),
                    "benchmark_authority": benchmark_trace.primary_authority,
                    "customer_authority": customer_trace.primary_authority,
                })
            elif (
                benchmark_trace.primary_authority != customer_trace.primary_authority
                and "legacy" in customer_trace.primary_authority.lower()
            ):
                divergences.append({
                    "type": ParityDivergenceType.BENCHMARK_ONLY_AUTHORITY.value,
                    "message": (
                        f"Benchmark consumed '{benchmark_trace.primary_authority}' but customer runtime used "
                        f"legacy authority '{customer_trace.primary_authority}'."
                    ),
                })

        # 2. Check for Inconsistent Wall Identities
        bm_walls = benchmark_trace.wall_identities
        cust_walls = customer_trace.wall_identities
        if bm_walls and cust_walls:
            if "wall" in cust_walls and len(bm_walls) > 1 and "wall" not in bm_walls:
                divergences.append({
                    "type": ParityDivergenceType.DIFFERENT_WALL_IDENTITY.value,
                    "message": (
                        f"Customer runtime collapsed distinct physical walls {sorted(bm_walls)} into a generic 'wall' identifier."
                    ),
                })
            elif not bm_walls.intersection(cust_walls):
                divergences.append({
                    "type": ParityDivergenceType.DIFFERENT_WALL_IDENTITY.value,
                    "message": (
                        f"Wall identities do not overlap: benchmark found {sorted(bm_walls)}, customer found {sorted(cust_walls)}."
                    ),
                })

        # 3. Check for Different Opening Deduction Logic
        common_walls = bm_walls.intersection(cust_walls) if (bm_walls and cust_walls) else set(benchmark_trace.opening_deductions_m2.keys()).intersection(customer_trace.opening_deductions_m2.keys())
        for wall_id in common_walls:
            bm_ded = float(benchmark_trace.opening_deductions_m2.get(wall_id, 0.0))
            cust_ded = float(customer_trace.opening_deductions_m2.get(wall_id, 0.0))
            if abs(bm_ded - cust_ded) > tolerance_m2:
                divergences.append({
                    "type": ParityDivergenceType.DIFFERENT_OPENING_DEDUCTION.value,
                    "wall_id": wall_id,
                    "message": (
                        f"Opening deduction mismatch on {wall_id}: benchmark deducted {bm_ded:.2f} m², "
                        f"customer deducted {cust_ded:.2f} m² (difference: {abs(bm_ded - cust_ded):.2f} m²)."
                    ),
                    "benchmark_deduction_m2": bm_ded,
                    "customer_deduction_m2": cust_ded,
                })

        # 4. Check for Different Quantity Basis
        for wall_id in common_walls:
            bm_basis = benchmark_trace.quantity_basis.get(wall_id, "")
            cust_basis = customer_trace.quantity_basis.get(wall_id, "")
            if bm_basis and cust_basis and bm_basis.lower() != cust_basis.lower():
                divergences.append({
                    "type": ParityDivergenceType.DIFFERENT_QUANTITY_BASIS.value,
                    "wall_id": wall_id,
                    "message": (
                        f"Quantity basis divergence on {wall_id}: benchmark used '{bm_basis}', customer used '{cust_basis}'."
                    ),
                })

        # 5. Check Published Quantities
        qty_diffs: Dict[str, float] = {}
        for item_key, bm_qty in benchmark_trace.published_quantities.items():
            if item_key in customer_trace.published_quantities:
                cust_qty = customer_trace.published_quantities[item_key]
                diff = round(abs(bm_qty - cust_qty), 2)
                if diff > tolerance_m2:
                    qty_diffs[item_key] = diff
                    divergences.append({
                        "type": ParityDivergenceType.DIFFERENT_QUANTITY_BASIS.value,
                        "item_key": item_key,
                        "message": (
                            f"Published quantity mismatch for '{item_key}': benchmark produced {bm_qty:.2f}, "
                            f"customer produced {cust_qty:.2f} (diff: {diff:.2f})."
                        ),
                    })

        is_parity = len(divergences) == 0
        return ParityComparisonResult(
            is_in_parity=is_parity,
            divergences=divergences,
            benchmark_authority=benchmark_trace.primary_authority,
            customer_authority=customer_trace.primary_authority,
            matched_walls=common_walls,
            quantity_differences=qty_diffs,
        )
