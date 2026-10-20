# Architecture: timber trusses must not invent 900 mm centres

## Observed repository behavior

`TimberRoofTrussSpec.spacing_centers_mm` defaults to `900.0`. `parse_truss_annotation` falls back to `900.0` when the annotation has no centres figure.

## Inference

A typical 900 mm truss grid is not owned evidence. This is the same class as the prior 600 mm hatch fail-closed.

## Proposed change

Omitted spacing is `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected truss counts and project names are not inputs.
