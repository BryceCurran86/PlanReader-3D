# Architecture: elevator landing doors must not invent 1000x2100 mm

## Observed repository behavior

`ElevatorLandingDoorSpec` defaults `width_mm=1000.0` and `height_mm=2100.0`.

## Inference

Typical lift-door size is not owned evidence. The contract forbids inventing door height.

## Proposed change

Omitted width and height default to `0.0`. Callers that pass explicit sizes are unchanged.

## Benchmark observations that must not influence implementation

Expected shaft volumes and project names are not inputs.
