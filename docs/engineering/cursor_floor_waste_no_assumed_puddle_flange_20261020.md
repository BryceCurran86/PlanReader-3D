# Architecture: floor wastes must not assume a puddle flange exists

## Observed repository behavior

`compute_floor_waste` defaults `has_puddle_flange=True`. Compile receipts therefore count a flange whenever the caller omits the flag.

## Inference

A typical wet-area flange is not owned evidence. Existence stays fail-closed until a caller supplies it.

## Proposed change

Default `has_puddle_flange=False`. Explicit True remains valid. No FIRM or takeoff change.

## Benchmark observations that must not influence implementation

Expected drain counts and project names are not inputs.
