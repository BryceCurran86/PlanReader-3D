# Architecture: firestops must not invent 60 mm collar heights

## Observed repository behavior

`FirestopDeviceSpec` defaults `collar_height_mm` to 60.0, and evaluate falls back to 60.0 when no collar height is owned.

## Inference

A typical 60 mm cast-in collar is not owned evidence.

## Proposed change

Omitted collar height stays 0.

## Benchmark observations that must not influence implementation

Expected collar geometry and project names are not inputs.
