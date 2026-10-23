# Architecture: weather louvers must not assume bird mesh exists

## Observed repository behavior

`WeatherLouverSpec.has_bird_mesh` defaults to `True`, so omitted tags still publish bird-mesh area equal to the gross aperture.

## Inference

A typical bird-mesh screen is not owned evidence. This is the same class as the prior operable-sash insect-screen fail-closed.

## Proposed change

Omitted bird mesh is `False` and contributes zero mesh area.

## Benchmark observations that must not influence implementation

Expected mesh areas and project names are not inputs.
