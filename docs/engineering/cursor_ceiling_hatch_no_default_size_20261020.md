# Architecture: ceiling hatches must not invent 600 mm size or 450 mm code

## Observed repository behavior

`compute_access_hatch` defaults `width_pt`/`length_pt` to 17.01 (~600 mm at 1:100) and `min_code_dimension_pt` to 12.75 (~450 mm), then sets `is_code_compliant` from that invented code minimum.

## Inference

Typical hatch size and an assumed code clearance are not owned evidence. Code compliance must not become True from a default.

## Proposed change

Omitted width and length default to `0.0`. `min_code_dimension_pt` defaults to `None`; `is_code_compliant` stays False until a caller supplies an explicit minimum.

## Benchmark observations that must not influence implementation

Expected hatch counts and project names are not inputs.
