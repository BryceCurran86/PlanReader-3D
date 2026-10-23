# Architecture: HVAC dampers must not invent 150 mm walls or sleeves

## Observed repository behavior

`FireDamperSpec.element_thickness_mm` and `sleeve_extension_mm` default to `150.0`. Omitted wall thickness still scales firestop mortar volume.

## Inference

A typical masonry partition thickness and damper-sleeve projection are not owned evidence.

## Proposed change

Omitted element thickness and sleeve extension stay `0.0`. Firestop volume is 0 when thickness is omitted.

## Benchmark observations that must not influence implementation

Expected firestop volumes and project names are not inputs.
