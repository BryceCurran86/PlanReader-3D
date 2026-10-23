# Architecture: operable acoustic walls must not invent retractable seals

## Observed repository behavior

`OperableWallSpec.has_retractable_seals` and `parse_callout` default to `True`. `evaluate_operable_walls` then hardcodes `has_retractable_seals=True` even when the callout did not own seals.

Traced: `OperableWallSpec`, `SourceOperableAcousticWallShadowAuthority.parse_callout`, `SourceOperableAcousticWallShadowAuthority.evaluate_operable_walls`.

## Inference

Typical retractable seals are not owned evidence.

## Proposed change

Omitted seals stay `False`. Evaluate copies the parsed/item flag instead of forcing True. Callout text that names retractable seals still sets True. Status stays `CANDIDATE`; `takeoff_eligible` stays `False`.

## Authority boundaries

Shadow module only. No live extractor, W10, commercial rows, or `benchmarks/frozen_holdout/full_plan_v2/**`.

## Expected abstentions

Callout `"OPERABLE WALL"` and a bare spec keep `has_retractable_seals is False`.

## Benchmark observations that must not influence implementation

Expected seal counts and project names are not inputs.
