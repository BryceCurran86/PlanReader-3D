# Architecture: skylights must not invent 1200 x 2400 mm openings

## Observed repository behavior

`SkylightVentSpec` and `parse_callout` default opening width and length to 1200 mm and 2400 mm when no dimensions are owned.

## Inference

A typical smoke-vent opening size is not owned evidence.

## Proposed change

Omitted opening dimensions stay 0.

## Benchmark observations that must not influence implementation

Expected throat areas and project names are not inputs.
