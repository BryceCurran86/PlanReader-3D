# Architecture: acoustic walls must not invent two lining layers per side

## Observed repository behavior

`AcousticWallSpec` defaults `side_a_layers=2` and `side_b_layers=2`. `parse_acoustic_wall_tag` falls back to `2, 2` when the tag has no layer figures.

## Inference

A typical double-layer lining is not owned evidence.

## Proposed change

Omitted layer counts are `0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected board areas and project names are not inputs.
