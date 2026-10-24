# Architecture: suspended ceilings must not invent a 100 mm minimum plenum

## Observed repository behavior

`evaluate_ceilings` uses `max(0.1, soffit - AFFL)` so omitted ceiling and soffit datums still publish 0.1 m hanger-wire length per hanger.

## Inference

A typical 100 mm plenum is not owned evidence.

## Proposed change

Plenum depth is `max(0.0, soffit - AFFL)`. Omitted datums contribute zero wire length.

## Benchmark observations that must not influence implementation

Expected hanger lengths and project names are not inputs.
