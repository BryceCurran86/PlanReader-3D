# Architecture: fire penetrations must not invent 90-minute FRL or damper rating

## Observed repository behavior

`create_fire_wall` defaults `frl_rating="90/90/90"` and `boundary_type="INTER_TENANCY_PARTY_WALL"`. `create_penetration` defaults `penetration_type="FIRE_DAMPER"`, `service_dimension_pt=10.0`, and `damper_rating_min=90`.

## Inference

Typical FRL and damper ratings are not owned evidence.

## Proposed change

Omitted ratings and types stay empty or 0. Callers that pass explicit values are unchanged.

## Benchmark observations that must not influence implementation

Expected fire ratings and project names are not inputs.
