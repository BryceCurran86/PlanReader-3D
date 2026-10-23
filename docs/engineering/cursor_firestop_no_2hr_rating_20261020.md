# Architecture: firestops must not invent a 2-hour fire rating

## Observed repository behavior

`FirestopDeviceSpec` and `parse_callout` default `fire_rating_hours` to 2 when no rating is owned.

## Inference

A typical 2-hour penetration rating is not owned evidence.

## Proposed change

Omitted fire rating stays 0.

## Benchmark observations that must not influence implementation

Expected FRL counts and project names are not inputs.
