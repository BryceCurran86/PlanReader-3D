# Architecture: wall-core decomposition must not invent brick materials

## Observed repository behavior

`decompose_cavity_brick` defaults inner/outer materials to COMMON_BRICK / FACE_BRICK and hardcodes cavity `AIR_OR_INSULATION`. `decompose_brick_veneer` defaults stud/veneer materials and hardcodes `AIR_CAVITY_WITH_WALL_TIES`. `decompose_solid_monolithic` defaults `PRECAST_CONCRETE`.

## Inference

Typical masonry product names are not owned evidence.

## Proposed change

Omitted materials are empty strings. Hardcoded cavity fills are empty unless a caller supplies them.

## Benchmark observations that must not influence implementation

Expected wall thicknesses and project names are not inputs.
