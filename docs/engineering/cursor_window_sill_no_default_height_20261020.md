# Architecture: window sill/head must not invent 900/2100 mm

## Observed repository behavior

`compute_window_vertical_partition` defaults `sill_height_pt=25.5` (~900 mm at 1:100) and `head_height_pt=59.5` (~2100 mm at 1:100) when the caller omits them.

## Inference

Typical window sill and head heights are not owned evidence. The contract forbids inventing door/window height and forbids giving assumed 2.8 m-class defaults authority. The 1:100 scale comment is not a scale resolver.

## Proposed change

Omitted sill and head default to `0.0`. Existing callers that pass explicit heights are unchanged. Receipt status stays CANDIDATE.

## Benchmark observations that must not influence implementation

Expected window areas and project names are not inputs.
