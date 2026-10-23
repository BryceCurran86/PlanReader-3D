# Architecture: weather louvers must not invent a 100 mm frame depth

## Observed repository behavior

`WeatherLouverSpec.frame_depth_mm` defaults to `100.0`. Blade-count evaluation subtracts a hardcoded 100 mm from height even when frame depth is omitted.

## Inference

A typical louver frame depth is not owned evidence.

## Proposed change

Omitted frame depth stays `0.0`. Blade count uses the owned `frame_depth_mm` instead of a hardcoded 100 mm.

## Benchmark observations that must not influence implementation

Expected blade counts and project names are not inputs.
