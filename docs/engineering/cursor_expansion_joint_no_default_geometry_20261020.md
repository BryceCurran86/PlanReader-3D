# Architecture: expansion joints must not invent 10 mm gap or 2700 mm length

## Observed repository behavior

`compute_movement_joint` defaults `gap_width_pt=0.28` (~10 mm at 1:100), `joint_length_pt=76.5` (~2700 mm), and a 12 mm backing-rod spec.

## Inference

Typical joint geometry is not owned evidence. Geometric gap width is not measurement authority.

## Proposed change

Omitted gap and length default to `0.0`. Omitted backing-rod spec stays empty. Callers that pass explicit values are unchanged.

## Benchmark observations that must not influence implementation

Expected sealant volumes and project names are not inputs.
