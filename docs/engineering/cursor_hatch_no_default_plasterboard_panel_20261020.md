# Architecture: ceiling hatches must not invent a plasterboard infill panel

## Observed repository behavior

`compute_access_hatch` defaults `panel_type="PLASTERBOARD_INFILL_FLUSH"`.

## Inference

A typical hatch panel construction is not owned evidence.

## Proposed change

Omitted panel type is empty. Callers that pass an explicit type stay unchanged.

## Benchmark observations that must not influence implementation

Expected hatch sizes and project names are not inputs.
