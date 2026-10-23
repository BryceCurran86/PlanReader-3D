# Architecture: skirting must not invent four internal corners

## Observed repository behavior

`compute_room_skirting` defaults `internal_corners_count=4`. Compile receipts that omit corners therefore report four mitres.

## Inference

A rectangular-room mitre count is a typical-construction default, not owned evidence.

## Proposed change

Omitted internal corners default to `0`. Callers that pass an explicit count stay unchanged.

## Benchmark observations that must not influence implementation

Expected skirting lengths and project names are not inputs.
