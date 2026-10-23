# Architecture: baseplates must not invent a 35 mm grout bed

## Observed repository behavior

`SteelBaseplateSpec.grout_thickness_mm` defaults to `35.0`. `parse_baseplate_annotation` falls back to `35.0` when the annotation has no grout figure.

## Inference

A typical grout-bed thickness is not owned evidence.

## Proposed change

Omitted grout thickness is `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected grout volumes and project names are not inputs.
