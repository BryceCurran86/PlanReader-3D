# Net-wall Boolean Union V1 — Validator Foundation

**Status:** TEST-ONLY / EXPECTED-RED / DO NOT MERGE

**Base:** `5b5d92583ef8a8695da90209bf05f84b7385a77a`

This layer is downstream of authenticated gross-wall geometry, authenticated
physical-opening voids, and opening-deduction applicability. Its job is to derive
net wall geometry/area without double-subtracting overlapping voids.

The existing scalar formula `gross - sum(deduction areas)` is not sufficient once
physical void geometry is available. Distinct authorized voids can overlap and
must be unioned geometrically before subtraction.

## 1. Required inputs

A positive net-wall result requires:

1. authenticated gross wall geometry / gross area for one exact physical wall;
2. producer-owned complete opening universe for the exact wall decision scope;
3. every relevant opening resolved to authenticated physical identity;
4. every relevant opening uniquely hosted to this exact wall;
5. every relevant authorized deduction linked to an authenticated physical void;
6. every relevant void represented in the same wall-local coordinate frame;
7. no unresolved relevant opening / void / host / applicability.

Wrong-wall voids must not enter the union.

## 2. Geometry rule

For an exact wall-local 2D domain `G` and authorized void geometries `V_i`:

`U = unary_union(V_i)`

`N = G.difference(U)`

Net area is measured from the resulting geometry in the authenticated physical unit
system. Do not replace this with `gross_area - sum(void.area)` when more than one
void may overlap.

`shapely.ops.unary_union` belongs only in this geometry layer after authority has
established which void geometries participate. Shapely must not be used to infer
host identity, opening identity, completeness, applicability, or missing geometry.

## 3. Identity / duplication semantics

- duplicate observations of one physical opening must not create a second void;
- repeated copies of the same authorized void geometry must not change union area;
- two same-size distinct physical openings remain distinct inputs;
- two distinct openings that overlap geometrically remain distinct identities but
  their geometric subtraction is the union, not scalar double subtraction;
- split/unsplit equivalent wall representations must resolve to the same physical
  wall proposition before net-wall geometry can be positive.

## 4. Fail-closed attack matrix

| Attack | Required result |
| --- | --- |
| overlapping void polygons | union once; never scalar double subtraction |
| duplicate void record | no area change |
| duplicate observation of same opening | no area change |
| disjoint openings | union contains both; subtraction equals sum only because disjoint |
| same-size distinct openings | both retained by identity |
| wrong-wall void | rejected / ignored only with explicit scope mismatch; never subtracted |
| unresolved relevant opening | net result BLOCKED / `None` |
| unresolved relevant void | net result BLOCKED / `None` |
| incomplete opening universe | net result BLOCKED / `None` |
| split vs unsplit equivalent wall | same physical net proposition |
| reversed wall baseline | invariant under deterministic wall-local transform |
| translated / rotated drawing | invariant under deterministic frame transform |
| caller raw area / caller polygon | cannot mint authority |
| caller opening list/count/complete flag | cannot mint completeness |
| gross area available but net blocked | gross survives unchanged; net remains `None` |
| empty caller list | unknown, not evidenced zero deductions |

## 5. Gross-area survival

Blocking net-wall authority must not erase an independently authenticated gross wall
quantity. A consumer may still display or diagnose gross area while net area is
`None` / blocked because opening resolution is incomplete.

## 6. Dependency state

At this validator base, the current `pb_wall_net_area_quantity.py` intentionally
fails closed and still contains scalar deduction arithmetic behind an unreachable
positive path. Physical Opening Void V2 and producer-owned Opening Deduction
Authority do not yet exist.

Therefore Net-wall Boolean Union production is intentionally unavailable. This
foundation may not be called frozen until the real void/deduction chain exists,
all attacks above execute against production, and an independent reviewer accepts
the exact validator blob.
