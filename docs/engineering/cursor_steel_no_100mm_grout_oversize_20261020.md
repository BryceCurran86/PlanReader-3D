# Architecture: grout beds must not invent +100 mm oversize

## Observed repository behavior

`SourceSteelBaseplateGroutBoltShadowAuthority.evaluate_connections` adds 100 mm to plate width and length for grout footprint even when no oversize is owned.

## Inference

A typical 50 mm all-around grout projection is not owned evidence.

## Proposed change

`grout_oversize_mm` defaults to 0. Takeoff that owns +100 mm passes it explicitly.

## Benchmark observations that must not influence implementation

Expected grout volumes and project names are not inputs.
