# Architecture: balustrades must not invent 1000 mm post centres

## Observed repository behavior

`BalustradeRunSpec.post_spacing_mm` defaults to `1000.0`. Evaluate also floors spacing at 0.5 m, so omitted centres still mint posts.

## Inference

A typical 1000 mm post grid is not owned evidence. This is the same class as the prior 600 mm hatch fail-closed.

## Proposed change

Omitted post spacing stays `0.0`. Evaluate contributes zero posts when spacing is omitted.

## Benchmark observations that must not influence implementation

Expected post counts and project names are not inputs.
