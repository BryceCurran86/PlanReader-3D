# Architecture: wet-area waterproofing must not invent 150/2000 mm upstands

## Observed repository behavior

`compute_wet_area_waterproofing` defaults `general_upstand_height_pt=4.25` (~150 mm at 1:100) and `shower_tanking_height_pt=56.69` (~2000 mm at 1:100).

## Inference

Assumed tanking heights and an assumed 1:100 scale are not owned evidence. Defaults must not become membrane-area authority.

## Proposed change

Omitted upstand and tanking heights default to `0.0`. Callers that pass explicit heights are unchanged.

## Benchmark observations that must not influence implementation

Expected membrane areas and project names are not inputs.
