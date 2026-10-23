# Architecture: roof drainage must not invent COLORBOND or PVC

## Observed repository behavior

`GutterSpec.material` defaults to COLORBOND steel. `DownpipeSpec.material` defaults to PVC. `parse_gutter_annotation` falls back to COLORBOND when the annotation names no material.

## Inference

Typical roof-drainage products are not owned evidence.

## Proposed change

Omitted material is `UNKNOWN` on specs and parse fallback.

## Benchmark observations that must not influence implementation

Expected gutter lengths and project names are not inputs.
