# Architecture: operable sashes must not invent 900 x 1200 mm

## Observed repository behavior

`parse_sash_annotation` falls back to `900.0 x 1200.0` when the annotation has no dimensions.

## Inference

A typical awning-sash size is not owned evidence. This is the same class as the prior 900/2100 mm sill/head fail-closed.

## Proposed change

Omitted parse width and height are `0.0`.

## Benchmark observations that must not influence implementation

Expected window sizes and project names are not inputs.
