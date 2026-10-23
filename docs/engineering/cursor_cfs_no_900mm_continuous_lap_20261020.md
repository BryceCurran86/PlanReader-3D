# Architecture: CFS members must not invent 900 mm laps from CONTINUOUS

## Observed repository behavior

`parse_callout` assigns `lap_length_mm = 900.0` when the callout says LAPPED or CONTINUOUS but owns no lap length.

## Inference

A typical 900 mm CFS lap is not owned evidence.

## Proposed change

Omitted lap length stays 0. Explicit millimetre lap text still parses.

## Benchmark observations that must not influence implementation

Expected purlin mass and project names are not inputs.
