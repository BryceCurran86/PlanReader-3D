# Architecture: gutter sheet area must not invent 100 mm of flanges

## Observed repository behavior

`evaluate_roof_drainage` computes girth as `width + 2*depth + 100` mm, inventing two 50 mm flanges on every gutter.

## Inference

Typical developed-girth allowances are not owned evidence.

## Proposed change

Girth is `width + 2*depth` only. Callers that pass explicit width and depth stay the source of those sizes.

## Benchmark observations that must not influence implementation

Expected sheet areas and project names are not inputs.
