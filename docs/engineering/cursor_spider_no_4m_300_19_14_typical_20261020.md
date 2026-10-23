# Architecture: spider fins must not invent 4.0 m x 300 mm x 19 mm or M14 rotules

## Observed repository behavior

`GlassFinSpec` and `parse_fin_callout` default 4.0 m height, 300 mm depth, and 19 mm thickness. `SpiderFittingSpec` and `parse_spider_callout` default M14 rotules.

## Inference

Typical point-supported facade catalogue sizes are not owned evidence.

## Proposed change

Omitted fin size and rotule diameter stay 0.

## Benchmark observations that must not influence implementation

Expected fin areas and project names are not inputs.
