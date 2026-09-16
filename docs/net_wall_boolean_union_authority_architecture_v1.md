# Net-wall Boolean Union Authority — Validator Foundation v1

**TEST-FIRST DESIGN ONLY.** This document does not grant net-wall authority and does not change the live extraction path.

Exact foundation base: `5b5d92583ef8a8695da90209bf05f84b7385a77a`.

## Proposition

The future authority may prove only:

> for this authenticated physical wall / exact trade scope, the authoritative net wall face is the gross wall-local face minus the geometric union of every applicable authenticated physical-opening void.

This proposition is downstream of physical opening existence, exact opening identity, host binding, physical void, complete opening universe, wall/trade applicability and gross wall geometry. It is not a shortcut around any of them.

## Geometry layer

Authoritative subtraction is performed in wall-local `(u,z)` geometry. A rectangular wall face is a wall-local polygon; each rectangular opening void is also a wall-local polygon. The authoritative void deduction geometry is the polygon union, not a scalar list of areas.

At the geometry layer, use `shapely.ops.unary_union` over the authenticated wall-local void polygons and subtract that union from the authenticated gross wall polygon. Scalar `sum(void.area)` is not an authority operation because overlaps and duplicates can otherwise be double-counted.

The existing `pb_wall_net_area_quantity.py` remains a legacy fail-closed scalar readiness path. It may retain provisional/diagnostic arithmetic, but it must not be relabelled as the Boolean-union authority.

## Public authority boundary

Ordinary consumers address a sealed record by selector only. A public selector may contain lineage / scope identifiers such as document, revision, source SHA, snapshot, page, decision scope, physical wall identity, assembly/trade scope and record identity as needed.

A public resolver must not accept caller-authored:

- polygons or coordinates;
- raw void areas;
- opening/deduction lists;
- completeness booleans/counts;
- `deductible=True` flags;
- caller host IDs;
- nearest/first/radius/confidence knobs;
- precomputed union or net areas.

Authenticated voids and gross-wall geometry are consumed behind the sealed producer boundary.

## Required attacks

1. **Overlapping void polygons** — overlap is deducted once; scalar area summation is forbidden.
2. **Duplicate voids** — replay/duplicate observations of the same authenticated physical opening do not double-deduct.
3. **Disjoint openings** — union preserves the sum when polygons truly do not overlap.
4. **Same-size distinct openings** — equal dimensions do not imply identity; two distinct physical openings at different `u` positions remain two voids.
5. **Wrong-wall void** — a void bound to another physical wall cannot be silently subtracted.
6. **Unresolved relevant opening** — if the complete applicable opening universe contains a relevant opening whose physical void is unresolved, net wall authority is blocked. Gross wall authority survives independently.
7. **Split/unsplit wall representation** — physically equivalent wall representations must not change net area or duplicate deductions; unresolved physical equivalence blocks authority rather than choosing a representation.
8. **Reversed wall baseline** — reversing the wall-local `u` axis changes coordinates but not the physical result/area.
9. **Translation** — translating all geometry preserves net area.
10. **Rotation** — rotating all geometry preserves net area.
11. **Deterministic serialization** — equivalent input ordering and duplicate observations produce a stable record fingerprint after identity-based deduplication and geometric normalization.
12. **Gross-area survival** — net may be `None`/ABSTAINED while an independently firm gross area remains available; blocked net must never erase or mutate gross authority.

## Identity and deduplication

Deduplicate repeated evidence by authenticated physical-opening identity before authoritative void consumption. Never deduplicate merely because two openings have the same width, height, area, tag or schedule type.

Geometric union is still required after identity deduplication because two distinct physical openings may geometrically overlap in the wall-local face. The union handles physical overlap; identity deduplication handles repeated representation of the same opening. These are separate propositions.

## Fail-closed states

Unknown remains unknown (`None` / ABSTAINED), never zero. Zero opening deduction is authoritative only when the complete applicable opening universe positively proves there are no applicable physical voids for the exact wall/trade scope.

Wrong source/revision/page/snapshot/scope, unresolved host, unresolved physical void, incomplete opening universe, ambiguous wall equivalence, wrong assembly/trade applicability, unsupported void profile or invalid polygon topology must all block net authority.

## Dependency status at foundation time

- #381 corrected host-binding production is technically green but still requires independent review/merge.
- Physical-opening Void V2 production is blocked by the external opening-height / vertical-placement prerequisite.
- Opening-deduction authority production is downstream of physical void and is not yet frozen/merged.

Therefore this PR is only a validator foundation. It must remain **DRAFT / TEST-ONLY / DO NOT MERGE** until its upstream contracts exist and the full attack suite can be executed against a real production authority.