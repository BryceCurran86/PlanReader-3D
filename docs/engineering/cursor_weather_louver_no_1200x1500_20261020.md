# Architecture: weather louvers must not invent 1200 x 1500 mm apertures

## Observed repository behavior

`WeatherLouverSpec.width_mm` and `height_mm` default to `1200.0` and `1500.0`. `parse_louver_annotation` falls back to those figures when the annotation has no width x height.

## Inference

A typical louver bank size is not owned evidence.

## Proposed change

Omitted louver width and height stay `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected louver areas and project names are not inputs.
