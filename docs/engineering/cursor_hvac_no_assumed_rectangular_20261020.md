# Architecture: HVAC dampers must not assume RECTANGULAR when profile is omitted

## Observed repository behavior

`parse_damper_annotation` defaults to `RECTANGULAR` when the annotation has no circular word. `evaluate_dampers` treats every non-circular damper as rectangular.

## Inference

A typical rectangular fire-damper profile is not owned evidence.

## Proposed change

Omitted profile is `UNKNOWN` and contributes zero airflow, opening, flange, and firestop. Explicit CIRCULAR/DIA/ROUND or owned width x height still resolve.

## Benchmark observations that must not influence implementation

Expected damper counts and project names are not inputs.
