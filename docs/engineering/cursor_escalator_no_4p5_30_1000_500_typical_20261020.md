# Architecture: escalators must not invent 4.5 m rise, 30 deg, 1000 mm pallets, or 500 mm baffles

## Observed repository behavior

`EscalatorVoidSpec` and `parse_callout` default 4.5 m rise, 30 deg incline, 1000 mm pallet width, and 500 mm smoke baffles when those figures are omitted.

## Inference

Typical commercial escalator catalogue sizes are not owned evidence.

## Proposed change

Omitted rise, incline, pallet width, and baffle depth stay 0. Explicit DEG and millimetre text still parse.

## Benchmark observations that must not influence implementation

Expected travel lengths and project names are not inputs.
