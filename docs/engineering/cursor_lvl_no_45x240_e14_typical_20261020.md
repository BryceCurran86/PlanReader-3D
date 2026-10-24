# Architecture: LVL beams must not invent 45 x 240 mm e14 typicals

## Observed repository behavior

`TimberBeamSpec` and `parse_callout` default ply width 45 mm, depth 240 mm, and stress grade e14 when those figures are omitted.

## Inference

Typical LVL catalogue sizes and grades are not owned evidence.

## Proposed change

Omitted ply width, depth, and grade stay 0 / empty.

## Benchmark observations that must not influence implementation

Expected timber volumes and project names are not inputs.
