# Full Plan Takeoff V2 Architecture

Full Plan V2 is PlanReader's only active benchmark / validation framework.

## Objective

Build independently source-closed truth that can validate the future canonical editable building model, not detached quantity answers alone.

`SOURCE DOCUMENT → SOURCE EVIDENCE → PHYSICAL OBJECT → CANONICAL OBJECT → VERIFIED GEOMETRY → VERIFIED QUANTITY → CUSTOMER OUTPUT`

## Core principles

1. Preserve atomic physical-object identity when the source supports it.
2. Preserve document, sheet/page and source-evidence provenance.
3. Never infer information solely because future VR/editing would benefit from it.
4. Distinguish existence, identification, verified geometry, verified quantity and full source closure.
5. Validate lifecycle coverage from detection through customer publication.
6. Keep truth-family tests scoped to their own object refs rather than project-wide item counts.
7. Keep V2 truth and production code in separate PRs.
8. Fail closed when project/surface/object universes are incomplete.

## Active scoreboard

See `manifest.json` for the authoritative list of V2 metrics. No single legacy percentage is an active headline.

## Canonical building milestone

`V2_CANONICAL_BUILDING_CORE` targets:

`UPLOAD → EVIDENCE → BUILDING → STOREYS → ROOMS → WALLS → OPENINGS → DOORS/WINDOWS → SLABS/FLOORS → CEILINGS → QUANTITIES → CUSTOMER OUTPUT`

Stable identity, geometry, relationships and provenance are the bridge into costing, VR/3D editing, constructability, drawings and JobHub.

## Integrity

- `.gitattributes` forces V2 JSON to LF for cross-platform byte stability.
- `scripts/check_full_plan_v2_integrity.py` validates V2 manifests, committed reference truth and object refs.
- `scripts/check_v2_truth_separation.py` prevents V2 truth from being bundled with production changes.

Legacy benchmark systems are historical only and must not be restored into this architecture.
