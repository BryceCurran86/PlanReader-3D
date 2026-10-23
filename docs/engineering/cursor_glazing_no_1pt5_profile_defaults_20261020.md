# Architecture: glazing subframes must not invent 1.5 pt profiles

## Observed repository behavior

`partition_window_subframe` defaults frame, mullion, and transom profile sizes to `1.5` pt.

## Inference

A typical aluminium profile width is not owned evidence.

## Proposed change

Omitted profile sizes are `0.0`. Callers that pass explicit sizes stay unchanged.

## Benchmark observations that must not influence implementation

Expected lite counts and project names are not inputs.
