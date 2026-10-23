# Architecture: firestops must not invent 100 mm pipe diameters

## Observed repository behavior

`FirestopDeviceSpec` and `parse_callout` default `nominal_pipe_dia_mm` to 100.0 when no diameter is owned.

## Inference

A typical DN100 penetration is not owned evidence.

## Proposed change

Omitted pipe diameter stays 0.

## Benchmark observations that must not influence implementation

Expected collar counts and project names are not inputs.
