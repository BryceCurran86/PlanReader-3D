# Architecture: skirting must not invent a timber MDF profile

## Observed repository behavior

`compute_room_skirting` defaults `profile=SkirtingMaterialProfile.TIMBER_MDF_BEVELLED`.

## Inference

A typical timber-MDF bevel is not owned evidence.

## Proposed change

Omitted profile is `UNKNOWN`. Callers that pass an explicit profile stay unchanged.

## Benchmark observations that must not influence implementation

Expected skirting product names and project names are not inputs.
