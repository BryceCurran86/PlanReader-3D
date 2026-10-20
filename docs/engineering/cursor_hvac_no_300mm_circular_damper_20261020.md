# Architecture: HVAC dampers must not invent a 300 mm circular diameter

## Observed repository behavior

`parse_damper_annotation` falls back to `300.0` when a circular/DIA annotation has no diameter figure, and the diameter regex treated any digit as optional DIA/MM.

## Inference

A typical circular fire-damper diameter is not owned evidence.

## Proposed change

Omitted circular diameter stays `0.0`. Diameter is read only from an explicit DIA or MM figure.

## Benchmark observations that must not influence implementation

Expected damper counts and project names are not inputs.
