# Architecture: operable acoustic walls must not invent a 2.5 m parking stack

## Observed repository behavior

`OperableWallSpec.parking_stack_track_length_m` and `parse_callout` default to `2.5` when no stack length is owned. Evaluate then adds that length to overhead track.

Traced: `OperableWallSpec`, `SourceOperableAcousticWallShadowAuthority.parse_callout`, `SourceOperableAcousticWallShadowAuthority.evaluate_operable_walls`.

## Inference

A typical parking-stack length is not owned evidence.

## Proposed change

Omitted stack length stays `0`. Explicit STACK/PARKING callouts still parse. Status stays `CANDIDATE`; `takeoff_eligible` stays `False`.

## Authority boundaries

Shadow module only. No live extractor, W10, commercial rows, or `benchmarks/frozen_holdout/full_plan_v2/**`.

## Expected abstentions

Callout `"OPERABLE WALL"` and a bare spec keep `parking_stack_track_length_m == 0`.

## Benchmark observations that must not influence implementation

Expected track lengths and project names are not inputs.
