# Architecture: balcony drainage must not invent 1:100 fall or 50 mm threshold

## Observed repository behavior

`compute_balcony_drainage` defaults `fall_ratio_1_in_n=100.0`, `threshold_stepdown_pt=1.42` (~50 mm at 1:100), and `screed_min_thickness_pt=0.71` (~25 mm). `max(1.0, ratio)` would invent 1:1 if the ratio were zeroed without a guard.

## Inference

Typical falls and assumed 1:100 scale are not owned evidence.

## Proposed change

Omitted ratio, threshold, and screed min default to `0.0`. Vertical fall is `0.0` unless the caller supplies a positive ratio. Callers that pass explicit values are unchanged.

## Benchmark observations that must not influence implementation

Expected balcony screed volumes and project names are not inputs.
