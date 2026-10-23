# Architecture: steel bracing must not invent 75x75x6 EA at 6.81 kg/m

## Observed repository behavior

`BracingMemberSpec` defaults to `"75x75x6 EA"` at `6.81` kg/m. `parse_bracing_annotation` falls back to those figures when the annotation has no section.

## Inference

A typical equal-angle brace is not owned evidence.

## Proposed change

Omitted section stays empty and omitted mass stays `0.0`, including parse fallbacks.

## Benchmark observations that must not influence implementation

Expected brace tonnes and project names are not inputs.
