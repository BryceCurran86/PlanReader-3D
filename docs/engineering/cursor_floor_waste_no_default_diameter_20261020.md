# Architecture: floor wastes must not invent 80 mm pipe or 25 mm sleeve

## Observed repository behavior

`compute_floor_waste` defaults `pipe_diameter_pt=2.27` (~80 mm at 1:100), `sleeve_oversize_pt=0.71` (~25 mm), and `grate_finish="CHROME_ROUND_GRATE"`.

## Inference

Typical waste-pipe size is not owned evidence. The 1:100 scale comment is not a scale resolver.

## Proposed change

Omitted diameter and sleeve default to `0.0`. Omitted grate finish stays empty. Callers that pass explicit values are unchanged. Puddle-flange True default is a separate fail-open.

## Benchmark observations that must not influence implementation

Expected drain counts and project names are not inputs.
