# Architecture: steel baseplates must not assume GRADE_8_8 when bolt grade is omitted

## Observed repository behavior

`SteelBaseplateSpec.bolt_grade` defaults to `GRADE_8_8`.

## Inference

A typical 8.8 anchor-bolt grade is not owned evidence.

## Proposed change

Omitted bolt grade is `UNKNOWN`.

## Benchmark observations that must not influence implementation

Expected bolt counts and project names are not inputs.
