# Architecture: steel bracing must not assume SINGLE_DIAGONAL when config is omitted

## Observed repository behavior

`parse_bracing_annotation` defaults to `SINGLE_DIAGONAL` when the annotation has no config word.

## Inference

A typical single-diagonal brace is not owned evidence.

## Proposed change

Omitted config is `UNKNOWN`. Explicit X / CHEVRON / K / TIE / DIAGONAL / SINGLE words still resolve.

## Benchmark observations that must not influence implementation

Expected brace counts and project names are not inputs.
