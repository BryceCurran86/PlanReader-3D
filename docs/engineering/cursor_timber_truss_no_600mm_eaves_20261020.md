# Architecture: timber trusses must not invent a 600 mm eaves overhang

## Observed repository behavior

`TimberRoofTrussSpec.eaves_overhang_mm` defaults to `600.0`. `parse_truss_annotation` falls back to `600.0` when the annotation has no overhang figure.

## Inference

A typical eaves overhang is not owned evidence. This is the same class as the prior 600 mm hatch fail-closed.

## Proposed change

Omitted eaves overhang is `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected timber lengths and project names are not inputs.
