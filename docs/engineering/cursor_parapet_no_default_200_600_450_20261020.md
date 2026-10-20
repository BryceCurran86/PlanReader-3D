# Architecture: parapets must not invent 200 / 600 / 450 mm sizes

## Observed repository behavior

`ParapetSegmentSpec` defaults wall 200 mm, upstand 600 mm, girth 450 mm, and membrane turnup 200 mm. The parser falls back to 200 / 600 / thickness+200 / 200 when those figures are omitted.

## Inference

Typical parapet construction sizes are not owned evidence.

## Proposed change

Omitted parapet sizes are `0.0` on both the spec and the parser fallbacks.

## Benchmark observations that must not influence implementation

Expected flashing lengths and project names are not inputs.
