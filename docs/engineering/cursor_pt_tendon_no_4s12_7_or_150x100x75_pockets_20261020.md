# Architecture: PT tendons must not invent 4S12.7 strands or 150x100x75 mm pockets

## Observed repository behavior

`TendonRunSpec` defaults to 4 strands of 12.7 mm. `AnchoragePocketSpec` defaults to 150 x 100 x 75 mm. `parse_tendon_annotation` falls back to `4` and `12.7` when the annotation has no `nSdia` figure. Omitted diameter still used the 12.7 mm unit mass.

## Inference

Typical PT strand packs and stressing-pocket sizes are not owned evidence.

## Proposed change

Omitted strand count, diameter, and pocket dimensions stay 0. Parse fallbacks match. Steel mass is 0 when count or diameter is omitted.

## Benchmark observations that must not influence implementation

Expected PT tonnage and project names are not inputs.
