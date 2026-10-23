# Architecture: drop panels must not invent 2000 x 2000 x 150 mm when dimensions are omitted

## Observed repository behavior

`parse_drop_panel_annotation` falls back to `2000.0, 2000.0, 150.0` when the annotation has fewer than two figures.

## Inference

A typical 2 m square 150 mm drop is not owned evidence.

## Proposed change

Omitted parse dimensions stay `0.0`.

## Benchmark observations that must not influence implementation

Expected drop volumes and project names are not inputs.
