# Sealed raster swing apertures for schedule tag ownership

## Observed repository behavior

Traced `compose_live_physical_opening_voids` →
`ScheduleOpeningInstanceBindingProducer.publish_scope` →
`_opening_aperture_for_physical_opening`, and `OpeningHeightProducer`'s
independent schedule row binding and explicit row-height gates. The aperture
helper recognizes sealed raster framed openings but not sealed raster swings.
Swing primitives are intentionally isolated from ordinary visible geometry,
so the fallback six-visible-line reconstruction cannot authenticate them.

The page-3 source diagnostic stops earlier at partial document coverage. A
separate native decode of all 13 source pages, with no failed pages, gets past
that gate and all seven swing schedule bindings abstain at geometry unavailable.
This is an implementation omission, independent of whether the actual source
contains a governing schedule row.

## Inference and proposed change

Use the same producer-sealed aperture bbox for the swing pattern. This proves
only spatial ownership of a contained plan tag. Complete source coverage,
G17 existence, finite positive bbox, trusted text, unique normalized contained
tag and unique matching schedule row remain mandatory. A parsed pair or a
door-like aspect ratio cannot establish width/height order. Explicit source
headings and row-height authority remain responsible for metric dimensions.

Synthetic proof must include a real raster swing with a native contained tag
and schedule row, missing/outside/competing tags, duplicate rows, incomplete
source coverage, invalid bboxes, stale selectors and transform/replay checks.
The source-only all-page audit must then reveal the next actual gate without
changing the main proof's snapshot or quantities. The user authorized continuous
work, so the routine architecture review pause is waived; evidence review is not.

## Benchmark observations excluded from implementation

The development drawing has seven detected swings. Neither that count, printed
values, coordinates, source/project names nor expected quantities enter the
generic change. Frozen V2 truth, scoring, denominator, source PDFs, defaults,
count completeness and commercial publication remain unchanged. This change
does not promise that the drawing has schedule or height authority.

## Implementation, full-source audit and remaining gates

The existing bbox path now recognizes both sealed raster patterns. Twelve real
source tests include explicit rough-opening height publication through the two
independent authorities, translation/scale, replay, missing/outside/competing
tags, duplicate rows, partial decode, stale selectors and rejection of generic
schedule numbers as metric opening heights. Invalid bbox regressions cover both
patterns. All native/vector behavior and row authority requirements are retained.

`tools/diag_gptmax_lot16_dimension_count_gates.py` independently decodes all 13
native source pages with zero failures and captures raster opening evidence on
page 3. It does not build W4, change the main proof snapshot, publish quantities
or feed any data back to an authority. With complete document decode, all seven
swings reach `schedule_opening_instance_binding_no_contained_tag`; none has an
authenticated contained schedule mark. All seven widths retain
`opening_dimension_witness_topology_required`. Six callout pairs are owned and
one remains conflicting; pairs do not establish axis order.

The same source-only audit retains 115 residual native observations and physical
conflict, as well as `semantic_opening_raster_candidate_closure_unproven` and
unproven exhaustiveness. Its physical opening universe is incomplete. Decoding
every page and enumerating known detector patterns cannot supply a commercial
count completeness seal. Existing semantic/count gates are deliberately retained.
Published CI must independently reproduce this audit before its validation is final.

Local validation: 632 expanded focused regressions pass, including the schedule
binding and row/opening-height authority suites. Provider isolation and frozen
V2 integrity pass. Published source and full CI verification are pending.
