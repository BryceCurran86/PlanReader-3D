# Architecture: baseplates must not invent 4-M24 bolts with 450 mm embedment

## Observed repository behavior

`SteelBaseplateSpec` defaults `bolt_count=4`, `bolt_diameter_mm=24`, and `bolt_embedment_depth_mm=450`. The parser falls back to the same values when the annotation has no bolt figures.

## Inference

A typical holding-down bolt cage is not owned evidence.

## Proposed change

Omitted bolt count is `0`. Omitted diameter and embedment are `0.0`. Parser fallbacks match.

## Benchmark observations that must not influence implementation

Expected bolt counts and project names are not inputs.
