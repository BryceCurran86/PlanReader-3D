# Architecture: operable sashes must not assume an insect screen exists

## Observed repository behavior

`OperableSashSpec.has_insect_screen` defaults to `True`. Omitted callers therefore count a flyscreen.

## Inference

Typical flyscreen provision is not owned evidence. Existence stays fail-closed.

## Proposed change

Default `has_insect_screen=False`. Explicit True remains valid.

## Benchmark observations that must not influence implementation

Expected screen counts and project names are not inputs.
