# Item 17 — Net-wall Boolean Union & Gross Wall Geometry Authority V1

This layer is downstream of authenticated gross wall geometry, authenticated physical opening voids, authenticated opening deduction applicability, and the complete opening universe. It derives authenticated net wall geometry and net wall area without double-subtracting overlapping opening voids.

## 1. Required Inputs & Authorities

A positive net-wall result requires:

1. Authenticated gross wall geometry (`GrossWallGeometryAuthority`) for the exact physical wall in wall-local Euclidean coordinates `(u, z)` in metres;
2. Authenticated physical opening voids (`PhysicalOpeningVoidAuthority`) in the same wall-local frame;
3. Producer-owned opening deduction authorization (`OpeningDeductionAuthority`) joining physical void, host binding, complete universe, and target applicability for the specified trade scope;
4. Producer-owned complete opening universe (`OpeningUniverseCompletenessAuthority`) for the decision scope;
5. Lineage consistency across all participating authorities: matching `document_id`, `revision_id`, `source_sha256`, and `snapshot_id`.

## 2. Geometry Rule

For an exact wall-local 2D gross domain $G = [0, \text{length\_m}] \times [0, \text{height\_m}]$ and authorized void geometries $V_i$:

$$U = \text{unary\_union}(V_i)$$
$$N = G.\text{difference}(U)$$

Net area is measured directly from the resulting geometry $N$ in square metres.
Scalar double subtraction (`gross - sum(void.area)`) is strictly forbidden and never used.

## 3. Identity and Duplication Semantics

- **Duplicate observations of one physical opening** do not duplicate deductions: deduplicated by `opening_identity_id`.
- **Distinct equal-size physical openings** remain distinct inputs and both participate in the union.
- **Overlapping openings** are unioned geometrically before difference; the overlap area is deducted once.
- **Wrong-wall voids** (hosted on another physical wall) are excluded from the target wall's union.
- **Non-applicable openings** (e.g. trade scope mismatch or RETAIN decision) are not deducted.

## 4. Fail-Closed Safeguards

- Void geometry extending partially or completely outside the gross wall boundary fails closed with `NET_WALL_VOID_UNRESOLVED`.
- Mismatched coordinate frames (`wall_local_frame_id`) fail closed with `NET_WALL_FRAME_MISMATCH`.
- Incomplete opening universe fails closed with `NET_WALL_OPENING_UNIVERSE_INCOMPLETE`.
- Gross area survival: blocking net-wall authority preserves the independently authenticated gross wall geometry reference with `net_area_m2 = None`.
