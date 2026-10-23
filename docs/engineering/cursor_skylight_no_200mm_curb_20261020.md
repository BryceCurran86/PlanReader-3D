# Architecture: skylights must not invent 200 mm curbs

## Observed repository behavior

`SkylightVentSpec` and `parse_callout` default `curb_height_mm` to 200.0 when no curb height is owned.

## Inference

A typical 200 mm upstand is not owned evidence.

## Proposed change

Omitted curb height stays 0. Explicit millimetre curb text still parses.

## Benchmark observations that must not influence implementation

Expected curb perimeters and project names are not inputs.
