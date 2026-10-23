# Architecture: HVAC dampers must not invent a 25 mm annular gap

## Observed repository behavior

`FireDamperSpec.annular_gap_mm` defaults to `25.0`. Omitted gap still inflates rough opening area and firestop mortar volume around a zero-size duct.

## Inference

A typical firestop packing gap is not owned evidence.

## Proposed change

Omitted annular gap stays `0.0`. Rough opening equals the duct when the gap is omitted.

## Benchmark observations that must not influence implementation

Expected firestop volumes and project names are not inputs.
