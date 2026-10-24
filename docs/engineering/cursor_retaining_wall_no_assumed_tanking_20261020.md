# Architecture: retaining walls must not assume tanking membrane exists

## Observed repository behavior

`RetainingWallSpec.has_tanking_membrane` defaults to `True`. Omitted callers therefore count tanking area.

## Inference

Typical retaining-wall tanking is not owned evidence. Existence stays fail-closed.

## Proposed change

Default `has_tanking_membrane=False`. Explicit True remains valid.

## Benchmark observations that must not influence implementation

Expected membrane areas and project names are not inputs.
