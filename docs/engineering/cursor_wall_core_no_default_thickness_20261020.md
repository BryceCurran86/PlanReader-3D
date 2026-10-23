# Architecture: wall-core decomposition must not invent 110/90 mm leaves

## Observed repository behavior

`decompose_cavity_brick` defaults 110/50/110 pt leaves. `decompose_brick_veneer` defaults 90/40/110 pt. `compile_decomposition_receipt` currently calls `decompose_cavity_brick()` with no thicknesses.

## Inference

Typical brick and stud thicknesses are not owned evidence. A missing assembly must not become a 270 pt cavity wall.

## Proposed change

Omitted leaf thicknesses default to `0.0`. Callers that pass explicit thicknesses are unchanged.

## Benchmark observations that must not influence implementation

Expected wall thicknesses and project names are not inputs.
