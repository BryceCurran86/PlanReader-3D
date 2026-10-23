# Architecture: steel baseplates must not invent a 75 mm nut/thread extension

## Observed repository behavior

`evaluate_connections` always adds 75 mm of nut/thread projection to every anchor rod, even when no extension is owned.

## Inference

A typical nut/thread stick-through is not owned evidence.

## Proposed change

Rod length uses owned `nut_thread_extension_mm`, default `0.0`.

## Benchmark observations that must not influence implementation

Expected rod lengths and project names are not inputs.
