# Batch40b host lever — architecture note (stop for review)

## Observed repository behavior

- Production `_authenticated_raster_source_lines` accepts only `RASTER_PDF_VISIBLE_SEGMENT`.
- Lot16 unhosted G17 support parents resolve as `raster_opening_primitive_segment` (48/48 in prior parent-kind census).
- Segment-parent line shadow authenticates 8 segment lines per unhosted opening, but segment raw IDs are disjoint from W4 `source_primitive_ids` (`raster_opening_primitive:…` vs `d*i0`).
- End-reach disposition remains `source_primitive_unmapped`; host is not granted.
- FACE/END census on original SHA `10109b4b…` p3: face×24, end×12 across 6 unhosted openings.
- Page `visible_observation_ids` sibling search found 0 visible-segment siblings for those openings.
- Signed-eight quantity IDs retained across multi-gate / remaining-gate / deep census attaches.

## Inference (not authority)

- A producer-owned bridge from segment-parent geometry to W4 primitive identity (or promotion of segment parents into the visible-line assembler under authenticated identity) is the likely host lever.
- Geometric proximity alone must not become host authority.

## Proposed change (shadow only until authority review)

- Keep segment-parent + ID-intersection + FACE/END + sibling search in shadow.
- Do not change production `_authenticated_raster_source_lines` in this PR.
- Do not grant host, FIRM, seal, or score from Cursor lanes.

## Benchmark observations that must not influence implementation

- Expected BOQ / Full Plan V2 match counts.
- Signed-eight area values (IDs only may be retained).
- Filenames / project keys / development scores.
