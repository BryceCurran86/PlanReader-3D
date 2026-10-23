# Architecture: stair flights must not invent riser/tread geometry

## Observed repository behavior

`compute_straight_flight` defaults `riser_count=16`, `riser_height_pt=4.96` (~175 mm), `tread_going_pt=7.09` (~250 mm), and `flight_width_pt=28.35` (~1000 mm) at an assumed 1:100 scale. `tread_count = max(1, riser_count - 1)` invents a tread when riser count is 0.

## Inference

Typical stair geometry is not owned evidence. A missing flight must not become a 16-riser stair.

## Proposed change

Numeric defaults become `0`. `tread_count` is `max(0, riser_count - 1)`. Callers that pass explicit geometry are unchanged.

## Benchmark observations that must not influence implementation

Expected stair voids and project names are not inputs.
