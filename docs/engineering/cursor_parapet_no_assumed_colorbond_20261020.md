# Architecture: parapets must not assume COLORBOND when capping material is omitted

## Observed repository behavior

`ParapetSegmentSpec.capping_material` and `parse_parapet_annotation` default to `COLORBOND_STEEL` when the annotation is silent.

## Inference

A typical COLORBOND capping is not owned evidence.

## Proposed change

Omitted capping material is `UNKNOWN`. Explicit COLORBOND / ALUMINIUM / ZINC / COPPER / PRECAST / STONE words still resolve.

## Benchmark observations that must not influence implementation

Expected flashing areas and project names are not inputs.
