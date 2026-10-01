"""Tests for AG-15: Benchmark vs Customer Runtime Parity Harness.

Verifies that the parity harness accurately validates parity and catches:
1. Benchmark-only authority
2. Customer-only fallback
3. Different opening deduction logic
4. Different wall identity
5. Different quantity basis
"""
from __future__ import annotations

import unittest
from pb_benchmark_customer_parity_harness import (
    AuthorityTrace,
    BenchmarkCustomerParityHarness,
    ParityDivergenceType,
)


class TestBenchmarkCustomerParityHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = BenchmarkCustomerParityHarness()

    def test_identical_authority_and_quantities_pass_parity(self) -> None:
        """Prove that when customer runtime consumes the same authority as benchmark, parity is verified."""
        bm_trace = AuthorityTrace(
            path_name="benchmark",
            primary_authority="pb_live_physical_net_wall_integration",
            is_fallback=False,
            wall_identities={"wall_N01", "wall_S01"},
            opening_deductions_m2={"wall_N01": 3.60, "wall_S01": 2.10},
            quantity_basis={"wall_N01": "net_physical_wall", "wall_S01": "net_physical_wall"},
            published_quantities={"wall_N01": 23.40, "wall_S01": 24.90},
        )
        cust_trace = AuthorityTrace(
            path_name="customer",
            primary_authority="pb_live_physical_net_wall_integration",
            is_fallback=False,
            wall_identities={"wall_N01", "wall_S01"},
            opening_deductions_m2={"wall_N01": 3.60, "wall_S01": 2.10},
            quantity_basis={"wall_N01": "net_physical_wall", "wall_S01": "net_physical_wall"},
            published_quantities={"wall_N01": 23.40, "wall_S01": 24.90},
        )

        result = self.harness.compare_traces(bm_trace, cust_trace)
        self.assertTrue(result.is_in_parity)
        self.assertEqual(len(result.divergences), 0)
        self.assertIn("PARITY PROVEN", result.summary())

    def test_detects_customer_only_fallback(self) -> None:
        """Catch when benchmark uses authenticated authority but customer runtime uses fallback."""
        bm_trace = AuthorityTrace(
            path_name="benchmark",
            primary_authority="pb_live_physical_net_wall_integration",
            is_fallback=False,
            wall_identities={"wall_N01"},
            published_quantities={"wall_N01": 23.40},
        )
        cust_trace = AuthorityTrace(
            path_name="customer",
            primary_authority="perimeter_heuristic_fallback",
            is_fallback=True,
            wall_identities={"wall_N01"},
            published_quantities={"wall_N01": 27.00},
        )

        result = self.harness.compare_traces(bm_trace, cust_trace)
        self.assertFalse(result.is_in_parity)
        types = [d["type"] for d in result.divergences]
        self.assertIn(ParityDivergenceType.CUSTOMER_ONLY_FALLBACK.value, types)

    def test_detects_different_opening_deduction_logic(self) -> None:
        """Catch when benchmark and customer runtime calculate different opening deduction quantities."""
        bm_trace = AuthorityTrace(
            path_name="benchmark",
            primary_authority="pb_opening_deduction_v174",
            is_fallback=False,
            wall_identities={"wall_N01"},
            opening_deductions_m2={"wall_N01": 3.60},
            published_quantities={"wall_N01": 23.40},
        )
        cust_trace = AuthorityTrace(
            path_name="customer",
            primary_authority="pb_opening_deduction_v174",
            is_fallback=False,
            wall_identities={"wall_N01"},
            opening_deductions_m2={"wall_N01": 1.80},  # Under-deducted
            published_quantities={"wall_N01": 25.20},
        )

        result = self.harness.compare_traces(bm_trace, cust_trace)
        self.assertFalse(result.is_in_parity)
        types = [d["type"] for d in result.divergences]
        self.assertIn(ParityDivergenceType.DIFFERENT_OPENING_DEDUCTION.value, types)
        ded_issue = next(d for d in result.divergences if d["type"] == ParityDivergenceType.DIFFERENT_OPENING_DEDUCTION.value)
        self.assertEqual(ded_issue["wall_id"], "wall_N01")
        self.assertEqual(ded_issue["benchmark_deduction_m2"], 3.60)
        self.assertEqual(ded_issue["customer_deduction_m2"], 1.80)

    def test_detects_different_wall_identity_collapse(self) -> None:
        """Catch when customer runtime collapses distinct wall identities into generic 'wall'."""
        bm_trace = AuthorityTrace(
            path_name="benchmark",
            primary_authority="pb_live_physical_net_wall_integration",
            is_fallback=False,
            wall_identities={"wall_N01", "wall_N02", "wall_E01"},
            published_quantities={"wall_N01": 12.0, "wall_N02": 11.4, "wall_E01": 15.0},
        )
        cust_trace = AuthorityTrace(
            path_name="customer",
            primary_authority="pb_live_physical_net_wall_integration",
            is_fallback=False,
            wall_identities={"wall"},  # Collapsed into single "wall"
            published_quantities={"wall": 38.4},
        )

        result = self.harness.compare_traces(bm_trace, cust_trace)
        self.assertFalse(result.is_in_parity)
        types = [d["type"] for d in result.divergences]
        self.assertIn(ParityDivergenceType.DIFFERENT_WALL_IDENTITY.value, types)

    def test_detects_different_quantity_basis(self) -> None:
        """Catch when benchmark and customer runtime use incompatible quantity formulas."""
        bm_trace = AuthorityTrace(
            path_name="benchmark",
            primary_authority="pb_live_physical_net_wall_integration",
            is_fallback=False,
            wall_identities={"wall_N01"},
            quantity_basis={"wall_N01": "net_physical_wall_boolean_union"},
            published_quantities={"wall_N01": 23.40},
        )
        cust_trace = AuthorityTrace(
            path_name="customer",
            primary_authority="pb_live_physical_net_wall_integration",
            is_fallback=False,
            wall_identities={"wall_N01"},
            quantity_basis={"wall_N01": "gross_perimeter_estimation"},
            published_quantities={"wall_N01": 27.00},
        )

        result = self.harness.compare_traces(bm_trace, cust_trace)
        self.assertFalse(result.is_in_parity)
        types = [d["type"] for d in result.divergences]
        self.assertIn(ParityDivergenceType.DIFFERENT_QUANTITY_BASIS.value, types)


if __name__ == "__main__":
    unittest.main()
