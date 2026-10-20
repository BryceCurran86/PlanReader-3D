# Architecture: stair voids must not assume a horizontal plan run

## Observed repository behavior

`compute_straight_flight` defaults `is_horizontal_run=True`, so omitted callers publish an X-axis void rectangle.

## Inference

A typical plan-north run direction is not owned evidence. Defaulting False would invent the other axis.

## Proposed change

Omitted `is_horizontal_run` is `None` and the void polygon is empty. Callers that pass True or False stay unchanged.

## Benchmark observations that must not influence implementation

Expected stair counts and project names are not inputs.
