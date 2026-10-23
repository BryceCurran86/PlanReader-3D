# Architecture: operable sashes must not invent a 45° or 15° opening

## Observed repository behavior

`OperableSashSpec.opening_angle_deg` defaults to `45.0`. Casement ventilation then clamps with `max(15.0, angle)`, inventing a 15° minimum.

## Inference

Typical casement opening angles are not owned evidence. This is the same class as the prior assumed 90° handing fail-closed.

## Proposed change

Omitted opening angle is `0.0`. Casement ventilation uses the supplied angle with no 15° minimum. Zero angle stays zero area.

## Benchmark observations that must not influence implementation

Expected ventilation areas and project names are not inputs.
