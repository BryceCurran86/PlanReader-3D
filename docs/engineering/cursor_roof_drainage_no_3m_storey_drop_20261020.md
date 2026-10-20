# Architecture: downpipes must not invent a 3.0 m storey drop

## Observed repository behavior

`DownpipeSpec.height_drop_m` defaults to `3.0`. Omitted drops therefore contribute 3.0 m of pipe length.

## Inference

A typical storey height is not owned evidence. This is the same class as the 3.0 m storey default already fail-closed elsewhere.

## Proposed change

Omitted `height_drop_m` is `0.0`. Callers that pass an explicit drop stay unchanged.

## Benchmark observations that must not influence implementation

Expected downpipe lengths and project names are not inputs.
