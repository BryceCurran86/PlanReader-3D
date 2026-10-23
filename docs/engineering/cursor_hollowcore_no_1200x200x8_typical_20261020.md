# Architecture: hollowcore planks must not invent 1200 x 200 x 8.0 m typicals

## Observed repository behavior

`HollowcorePlankSpec` and `parse_callout` default width 1200 mm, depth 200 mm, length 8.0 m, area 9.6 m2, and topping 65 mm when those figures are omitted.

## Inference

Typical extruded plank catalogue sizes are not owned evidence.

## Proposed change

Omitted plank dimensions stay 0.

## Benchmark observations that must not influence implementation

Expected plank areas and project names are not inputs.
