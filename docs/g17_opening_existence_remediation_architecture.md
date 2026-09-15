# G17 physical-opening existence remediation architecture

Base: `5bd671d08c87b8c0c6aaadcbae52c74ce4be9425` (current main after merged PR #318)

This is the refreshed architecture report required by `AGENTS.md` before production mutation.

## OBSERVED repository behavior

1. `SourceObservationProducer.ingest_native_pdf_bytes()` creates producer-owned native PDF observations from immutable source bytes. Native observations are page-owned and currently have `viewport_id=None`.
2. `publish_derived_observation()` verifies parent membership but lets the trusted caller supply child page, viewport, observation kind, primitive reference, and geometry. It does not recompute child geometry from parents or prove child scope from transitive roots.
3. Merged PR #319 permits `PHYSICAL_OPENING_EXISTS` from derived `wall_face_interruption` / `opening_jamb_boundary` records with independent native roots. The roots prove ancestry, not that the derived geometry was actually generated from those roots.
4. Merged PR #318 adds path/item/edge provenance and clip metadata, but current main still collapses known-no-active-clip and unknown clip association into `clip_present=False`, and `page_coords_present` can still remain true for non-finite floating-point coordinates. These Priority-1 residuals remain unresolved.
5. Current `extract_native_page()` exposes source segment coordinates plus clip metadata but does not expose the separate proven `visible_segments` authority path validated on stale PR #308. Therefore raw native segment existence is not equivalent to visible physical linework: fully clipped or unresolved-clip geometry must not become semantic opening authority.
6. PR #308 demonstrated a generic source-integrity design that separates raw source primitives from proven rectangular-clipped visible geometry, blocks unresolved non-rectangular clipping, preserves Form/CTM provenance, and keeps degenerate primitives auditable. It is now stale/conflicting because merged #318 also modified `pb_vector_geometry_v130.py`; it must be rebuilt rather than blindly merged.
7. PR #319 remains unwired from live prediction, opening identity, dimensions, host binding, completeness, deductions, commercial rows, and JobHub publication. The controlled benchmark therefore remains 50.82% (31/61) and this remediation must not claim a score gain.

## INFERRED authority defects

A positive physical-opening existence decision is unsafe today for three independent reasons:

- derived structural geometry can self-certify unrelated native lineage;
- derived records can launder page/viewport ownership not proven by roots;
- raw native geometry is not yet a proven visible-geometry universe under clipping/source-integrity hazards.

Lineage proves provenance, not geometry truth. Raw primitive presence proves source content, not necessarily visible physical linework.

## PROPOSED remediation order

### Gate A — complete Priority-1 provenance residuals

Before any new positive opening existence route:

- distinguish clip association knowledge from active clip presence;
- reject/non-certify non-finite native coordinates;
- preserve known absence separately from unknown where the PDF API supports that distinction;
- keep historical IDs and live predictions unchanged.

### Gate B — restore visible-geometry source integrity

Rebuild the validated #308 concepts on top of current main after Gate A:

- retain raw source primitives for audit;
- provide a separately typed/proven visible-segment view only when visibility is resolvable;
- apply rectangular clipping deterministically;
- unresolved/non-rectangular clip state must block affected semantic geometry rather than approximate it;
- preserve Form/XObject/CTM provenance and fail closed on explicit recursion/integrity hazards;
- do not use raw source primitives as substitutes for visible geometry.

### Gate C — native-only structural opening proof

Only after Gates A and B are green may G17 positive semantic existence be rebuilt.

The positive proof must consume producer-owned, integrity-resolved visible native segments only. Generic derived observations may be diagnostic/candidate evidence but cannot establish `PHYSICAL_OPENING_EXISTS`.

A positive opening must deterministically prove from eligible visible native segments:

- two locally consistent opposing wall-face runs;
- simultaneous interruption on both faces;
- real flanking wall material on both sides of the gap on both faces;
- source-native jamb support spanning the wall thickness at both gap boundaries;
- one unambiguous structural interpretation in the eligible local universe.

A rectangle made from two parallel lines plus two connectors without flanking wall runs is insufficient.

### Gate D — capability firewall

Until Gate C passes independent review:

- existing downstream promotion capabilities remain unavailable;
- no opening identity, dimensions, host identity/binding, universe completeness, physical void, net-wall deduction, FIRM quantity, live extractor output, commercial row, or JobHub publication may rely on #319 existence;
- semantic existence, once repaired, must remain separate from downstream promotion permissions.

## Required adversarial proof

At minimum:

1. unrelated native roots + fabricated perfect derived opening -> fail closed;
2. page-2 roots -> page-1 child -> fail closed;
3. viewport-none roots -> child claiming a viewport -> no viewport authority;
4. fully clipped/invisible structural lines -> cannot prove opening;
5. unresolved non-rectangular clip -> block affected proof;
6. two parallel lines + two connectors without flanking material -> fail closed;
7. native two-face gap without both jambs -> candidate only;
8. derived tags/schedules/swing arcs/detector labels cannot establish existence;
9. snapshot re-resolution/integrity failure blocks;
10. competing structural interpretations -> conflict/ambiguous;
11. translation/rotation and segment-splitting metamorphics preserve decisions;
12. input order, unrelated content, and page expansion cannot strengthen authority;
13. deterministic replay gives stable IDs;
14. no input mutation;
15. identity/dimensions/host/completeness/void/net-area/commercial gates stay closed.

## Ownership boundaries

Cursor owns Gate A and then repository-ordered Priority 2 wall identity work. GPT-2 should independently red-team the G17 boundary and add test-first attack coverage without changing production authority. ChatGPT owns the source-integrity / visibility review and the later G17 remediation integration once prerequisites are genuinely green.

## BENCHMARK firewall

The current controlled development baseline remains **50.82% (31/61 accepted)**. Development expected values, project identities, benchmark mappings, scoring tolerances, or score deltas must not select algorithms or thresholds. Infrastructure/authority-only work may legitimately remain 50.82% -> 50.82%.