# Architecture: timber trusses must not invent a 22.5 degree pitch

## Observed repository behavior

`TimberRoofTrussSpec.pitch_deg` defaults to `22.5`. `parse_truss_annotation` falls back to `22.5` when the annotation has no pitch figure.

## Inference

A typical roof pitch is not owned evidence.

## Proposed change

Omitted pitch is `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected timber lengths and project names are not inputs.
