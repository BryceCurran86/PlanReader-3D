# Architecture: gutters must not invent a 1:100 fall

## Observed repository behavior

`GutterSpec.fall_ratio` defaults to `0.01` (1:100).

## Inference

A typical gutter fall is not owned evidence. This is the same class as the prior 1:100 balcony-fall fail-closed.

## Proposed change

Omitted `fall_ratio` is `0.0`.

## Benchmark observations that must not influence implementation

Expected gutter lengths and project names are not inputs.
