# Block-style scale bar evidence (shadow): the sheet states its scale at every metre, and the producer does not see it

Status: **shadow-only detector.** `pb_scale_block_bar_shadow.py` (15 tests in `tests/test_scale_block_bar_shadow.py`, 6 of 7 single-rule mutants killed; the seventh, "labels need not start at zero", is
equivalent because the run builder already forces the progression to start at zero). It does not call or replace `pb_physical_scale_authority`, accepts no ratio as a scale, grants no authority and is not
called by any live path. Claude integration lane, 2026-10-16.

## Observed
`pb_physical_scale_authority` accepts one bar model: a baseline with exactly one perpendicular tick crossing each endpoint, a `0` at one end and a physical label at the other; it refuses rectangle corners as ticks on purpose.
The 3Laurel floor plan (p3) carries a **block bar**: eleven numerals `0 1 2 ... 10m` and a vertical block edge under each. The producer reports `physical_scale_bar_unavailable` for it
(`docs/engineering/3laurel_p3_wall_authority_gate_trace/scale_probe.py` reproduces that even with the viewport forced).

## What the shadow measures (original PDFs)
Numerals forming `0, s, 2s ... N s` on one baseline, equally spaced, with one physical unit on a label of the run, and a block edge within 1 pt of at least 70 % of them. Reported with residuals, not as a decision.
| page | bar | span | points per mm | label / edge residual | printed ratio |
|---|---|---|---|---|---|
| 3Laurel p3 | `0 ... 10m` | 283.462 pt = 10,000 mm | 0.028346241 | 0.005 / 0.011 pt | `1:100`, relative difference 8e-6 |
| 3Laurel p2 (site plan) | `0 ... 10m` | | 0.014172741 | 0.005 / 0.011 pt | 1:200 |
Every page of the five primary PDFs (Lot16 architecture and structure, 3Laurel, Maryborough, Q5446) was scanned: **no other bar and no false positive**; the Lot16, Maryborough and Q5446 sheets state a ratio only.

## Counterfactual through the unchanged scale producer (3Laurel p3)
I injected the detector's candidates into `_bar_candidates` in a running process (nothing written). The injection finds **0 bars because the producer's trusted-word list for the page is empty**: every one of the 1,215 native words
is abstained by the text-integrity authority (`text_glyph_mapping_unverified`; see `docs/engineering/text_integrity_coverage_20261016.md`). So accepting block bars is necessary and not sufficient: the numerals must first be trusted or
corroborated. The bar's own geometry (11 block edges at 28.3462 pt spacing) is source-native and independent of that, which is why the shadow takes words as input and reports whether they sit on the edges.

## Not claimed
No scale authority, no points-per-millimetre for any consumer, no change to wall, host, opening or quantity results. A plausible bar is not a measurement authority until the existing scale producer (or its reviewed successor) accepts it
and the numerals pass text integrity or an approved corroboration.

## Reproduce
```python
from pb_scale_block_bar_shadow import detect_block_scale_bars
detect_block_scale_bars(segments, words)   # segments: native segment dicts; words: {"id", "text", "bbox"}
```
