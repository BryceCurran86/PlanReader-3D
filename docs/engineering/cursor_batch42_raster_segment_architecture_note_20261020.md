# Batch42 — `raster_segment:` digit-tail vs opening parents

## Observed

- Lot16 usable W4 candidates on page 3: **2094 usable / 0 unusable**.
- Segment-parent line IDs: `raster_opening_primitive:…:{kind}:{n}` (8 per unhosted).
- W4 primitives include both `d{n}i0` (~213) and `raster_segment:…:{n}` (~2035).
- Digit-tail collisions for 6 unhosted openings are **almost entirely** against `raster_segment:` tails (counts 8/7/8/7/8/6), with `dNi0` overlap at most 1.
- Exact / visible-strip intersections remain 0.
- Parent kinds remain 48× `raster_opening_primitive_segment`.
- Kind-supported tokens: door×7 / window×7; all eight single-figured labels are **870 mm** (width-only; height still refused).
- GPT MAX #3412 tightens local W2-fragment end-reach ownership; complementary, not a Cursor host grant.

## Inference (not authority)

- Shared trailing integers between opening-primitive refs and wall `raster_segment` refs are **namespace-coincident**, not authenticated identity.
- Promoting digit-tail to host would violate AGENTS.md (no nearest/heuristic authority).

## Proposed (shadow only)

- Keep `digit_tail_collision_ambiguous_abstain` and retain both ID forms with `selected_id=null`.
- Do not merge GPT MAX end-reach fragment fixes as measurement authority from this Cursor lane.

## Benchmark that must not drive algorithms

- Expected BOQ / V2 scores; signed area values (IDs only).
