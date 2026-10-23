# Architecture: timber trusses must not assume FINK when type is omitted

## Observed repository behavior

`parse_truss_annotation` defaults to `TrussProfileType.FINK` when the annotation has no type word.

## Inference

A typical Fink truss is not owned evidence.

## Proposed change

Omitted type is `UNKNOWN`. Explicit FINK / HOWE / MONO / GIRDER / HIP words still resolve.

## Benchmark observations that must not influence implementation

Expected truss counts and project names are not inputs.
