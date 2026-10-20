# Architecture: freezer floor takeoff must not invent 100 mm coving

## Observed repository behavior

`compute_freezer_floor_takeoff` defaults `coving_height_m=0.100`. Status is already CANDIDATE on the success path.

## Inference

Typical 100 mm cove skirting is not owned evidence. This PR does not change room-name or finish-code gates and does not use FREEZER/EPX/FT2 as prediction inputs.

## Proposed change

Omitted coving height defaults to `0.0`. Callers that pass explicit height are unchanged.

## Benchmark observations that must not influence implementation

Frozen FREEZER/EPX/FT2 names and expected BOQ areas are not inputs.
