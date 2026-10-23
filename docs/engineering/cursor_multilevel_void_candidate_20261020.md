# Architecture: multilevel vertical voids stay CANDIDATE

## Observed repository behavior

`evaluate_vertical_void` returns `CORROBORATED` when the caller supplies matching token strings. `compute_level_net_floor_area` deducts those voids and mints `CORROBORATED` whenever `gross_floor_area_sqm > 0`. Commercial flags are already False.

## Inference

Caller token strings such as `STAIR VOID` are not independently re-resolved native-text ownership. A positive caller gross area is not net-floor-area authority. Candidate voids must not be deducted.

## Proposed change

Return `CANDIDATE` on the void success path. Takeoff status is `CANDIDATE` when gross area is positive, else `ABSTAINED`. Deduction still includes only `CORROBORATED` voids, so candidate voids do not change net area.

## Benchmark observations that must not influence implementation

Expected floor areas and project names are not inputs.
