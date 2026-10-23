# Architecture: skylights must not invent safety mesh

## Observed repository behavior

`SkylightVentSpec` defaults `has_safety_mesh` to True, and smoke-vent parse also sets True when no mesh text is owned.

## Inference

Typical fall-arrest mesh is not owned evidence.

## Proposed change

Omitted mesh stays False. Explicit SAFETY MESH text still parses.

## Benchmark observations that must not influence implementation

Expected mesh counts and project names are not inputs.
