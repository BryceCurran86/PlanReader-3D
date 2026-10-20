# Architecture: wall-junction deductions stay CANDIDATE

## Observed repository behavior

`evaluate_t_junction` and `evaluate_l_junction` return `CORROBORATED` when caller-supplied thicknesses and height pass local numeric bounds. Commercial flags are already False.

## Inference

Caller numbers that survive a range check are not independently re-resolved wall-pair / W4 junction ownership. Geometric gap width and assumed height are not measurement authority.

## Proposed change

Return `CANDIDATE` on the success path. Invalid bounds still `ABSTAINED`. Overlap arithmetic is unchanged.

## Benchmark observations that must not influence implementation

Expected wall volumes, project names, and frozen BOQ deductions are not inputs.
