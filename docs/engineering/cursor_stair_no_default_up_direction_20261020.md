# Architecture: stair flights must not invent an UP direction

## Observed repository behavior

`compute_straight_flight` defaults `direction="UP"`. Omitted callers therefore publish an ascending flight.

## Inference

A typical stair direction is not owned evidence.

## Proposed change

Omitted direction is empty. Callers that pass an explicit direction stay unchanged.

## Benchmark observations that must not influence implementation

Expected stair counts and project names are not inputs.
