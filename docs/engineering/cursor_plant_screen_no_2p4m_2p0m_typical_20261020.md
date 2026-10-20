# Architecture: plant screens must not invent 2.4 m height or 2.0 m post spacing

## Observed repository behavior

`PlantScreenSpec` and `parse_callout` default 2.4 m screen height and 2.0 m post spacing when those figures are omitted. Evaluate then divides length by that spacing.

## Inference

Typical rooftop screen catalogue sizes are not owned evidence.

## Proposed change

Omitted height and spacing stay 0. Posts stay 0 when spacing is not owned.

## Benchmark observations that must not influence implementation

Expected screen areas and project names are not inputs.
