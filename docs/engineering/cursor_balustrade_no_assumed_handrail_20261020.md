# Architecture: balustrades must not assume a continuous handrail exists

## Observed repository behavior

`BalustradeRunSpec.has_continuous_handrail` defaults to `True`. `parse_balustrade_annotation` also forces True for stairs and ramps even when the annotation has no handrail word.

## Inference

A typical continuous handrail is not owned evidence. This is the same class as the prior insect-screen / bird-mesh fail-closed.

## Proposed change

Omitted handrail is `False`. Parse records a handrail only from an explicit HANDRAIL or RAIL word.

## Benchmark observations that must not influence implementation

Expected handrail lengths and project names are not inputs.
