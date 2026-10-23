# Architecture: baseplates must not invent 350 x 350 x 25 mm

## Observed repository behavior

`SteelBaseplateSpec` defaults plate 350 x 350 x 25 mm. `parse_baseplate_annotation` falls back to the same sizes when the annotation has no plate figures.

## Inference

A typical column baseplate is not owned evidence.

## Proposed change

Omitted plate width, length, and thickness are `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected steel masses and project names are not inputs.
