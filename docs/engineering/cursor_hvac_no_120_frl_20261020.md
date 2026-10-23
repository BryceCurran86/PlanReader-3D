# Architecture: HVAC dampers must not invent a -/120/120 FRL

## Observed repository behavior

`FireDamperSpec.frl_rating` defaults to `"-/120/120"`. `parse_damper_annotation` falls back to that rating when the annotation has no FRL figure.

## Inference

A typical 120-minute fire-damper rating is not owned evidence. This is the same class as the prior 90-minute FRL fail-closed.

## Proposed change

Omitted FRL stays empty on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected FRL schedules and project names are not inputs.
