# Architecture: weather louvers must not invent 35/45/50/52 percent free area

## Observed repository behavior

`WeatherLouverSpec.free_area_ratio` defaults to `0.50`. `parse_louver_annotation` invents `0.45` / `0.35` / `0.52` / `0.50` from blade-type lookup when the annotation has no percent figure.

## Inference

Typical manufacturer free-area percentages are not owned evidence.

## Proposed change

Omitted free-area ratio stays `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected aerodynamic areas and project names are not inputs.
