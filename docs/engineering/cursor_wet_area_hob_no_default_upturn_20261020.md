# Architecture: wet-area hob must not invent 150 mm waterproofing upturn

## Observed repository behavior

`evaluate_hob` defaults `waterproofing_upturn_h_m=0.15`. `compute_wet_area_takeoff` defaults `waterproof_upturn_height_m=0.15`.

## Inference

Typical 150 mm upturn is not owned evidence.

## Proposed change

Omitted upturn heights default to `0.0`. Callers that pass explicit heights are unchanged.

## Benchmark observations that must not influence implementation

`FT2` and expected wet-area BOQ quantities are not inputs.
