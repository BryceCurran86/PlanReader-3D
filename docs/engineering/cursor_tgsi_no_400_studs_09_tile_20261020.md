# Architecture: TGSI zones must not invent 400 studs/m2, 0.09 m2 tiles, or 1.0 x 0.6 m pads

## Observed repository behavior

`TGSIZoneSpec` and `parse_callout` default 1.0 m x 0.6 m pads, and evaluate multiplies area by 400 studs/m2 or divides by 0.09 m2 tiles when those densities are omitted.

## Inference

Typical AS 1428.4 module sizes and stud densities are not owned evidence.

## Proposed change

Omitted pad size and density stay 0. Takeoff that owns 400 studs/m2 or 0.09 m2 tiles passes them explicitly.

## Benchmark observations that must not influence implementation

Expected stud counts and project names are not inputs.
