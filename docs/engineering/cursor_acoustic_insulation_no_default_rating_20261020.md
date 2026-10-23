# Architecture: acoustic insulation must not invent 90 mm, R2.5, or Rw50

## Observed repository behavior

`compute_wall_insulation` defaults `cavity_thickness_pt=2.55` (~90 mm at 1:100), `r_value=2.5`, `rw_rating=50`, and `insulation_material="HIGH_DENSITY_GLASSWOOL_BATTS"`.

## Inference

Typical batt thickness and acoustic ratings are not owned evidence.

## Proposed change

Omitted cavity thickness, R-value, and Rw default to `0`. Omitted material stays empty. Callers that pass explicit values are unchanged.

## Benchmark observations that must not influence implementation

Expected insulation quantities and project names are not inputs.
