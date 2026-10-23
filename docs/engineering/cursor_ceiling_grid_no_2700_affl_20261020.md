# Architecture: suspended ceilings must not invent 2700 AFFL or a 600 mm plenum

## Observed repository behavior

`SuspendedCeilingSpec` defaults `finished_ceiling_level_mm=2700` and `slab_soffit_level_mm=3300`. `parse_ceiling_annotation` falls back to 2700 AFFL and adds 600 mm plenum when those figures are omitted.

## Inference

A typical finished-ceiling datum and plenum depth are not owned evidence. 2700 mm is the same class as the prior 2.8 m / 3.0 m storey defaults.

## Proposed change

Omitted ceiling and soffit levels are `0.0`. Parser FCL fallback is `0.0`. Omitted plenum does not add 600 mm.

## Benchmark observations that must not influence implementation

Expected ceiling areas and project names are not inputs.
