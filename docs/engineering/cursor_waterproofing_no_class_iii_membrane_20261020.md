# Architecture: wet-area waterproofing must not invent CLASS III polyurethane

## Observed repository behavior

`compute_wet_area_waterproofing` defaults `membrane_spec="CLASS_III_POLYURETHANE_MEMBRANE"`.

## Inference

A typical membrane product class is not owned evidence.

## Proposed change

Omitted membrane spec is empty. Callers that pass an explicit spec stay unchanged.

## Benchmark observations that must not influence implementation

Expected membrane areas and project names are not inputs.
