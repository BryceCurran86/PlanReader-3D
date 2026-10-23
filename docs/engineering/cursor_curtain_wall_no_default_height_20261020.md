# Architecture: curtain-wall bays must not invent 900/2400 mm vision heights

## Observed repository behavior

`compute_curtain_wall_bay` defaults bay width ~1500 mm, storey ~3600 mm, sill ~900 mm, head ~2400 mm, insulation ~50 mm, and a ceramic-frit finish, all at an assumed 1:100 scale.

## Inference

Typical curtain-wall geometry is not owned evidence. Invented vision head height is the same class as invented door/window height.

## Proposed change

Omitted dimensions default to `0.0`. Omitted finish stays empty. Callers that pass explicit values are unchanged.

## Benchmark observations that must not influence implementation

Expected glazing areas and project names are not inputs.
