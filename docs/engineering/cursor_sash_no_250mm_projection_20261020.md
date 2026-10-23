# Architecture: operable sashes must not invent a 250 mm awning projection

## Observed repository behavior

`OperableSashSpec.max_projection_mm` defaults to `250.0`. Awning ventilation uses that figure when projection is omitted.

## Inference

A typical awning chain-winder projection is not owned evidence.

## Proposed change

Omitted max projection stays `0.0`. Awning ventilation is 0 when projection is omitted.

## Benchmark observations that must not influence implementation

Expected ventilation areas and project names are not inputs.
