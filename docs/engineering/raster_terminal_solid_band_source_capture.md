# Terminal solid raster-band source capture

## Observed repository behavior

Read `AGENTS.md`, the engineering playbook, adopted topology architecture,
wall/room specification, retired benchmark notice and CI contract. The traced
capture path is `SourceVisibilityProducer.augment_with_raster_visible_segments`
→ `detect_axis_aligned_raster_segments` → `_native_page_segments` → W2/W4.
G17 independently captures closed band boxes through `_band_boxes` and
`_band_edge_primitives` in `pb_raster_opening_source_primitives.py`.
`_resolve_raster_source_band_host_from_records` requires each exact visible
primitive and its local W4 chain to lie inside the authenticated source flank.
`OpeningHostFrameProducer._raster_binding_nodes` separately re-proves both
local owners before attempting a connected frame.

The existing compact bridge requires a wholly painted inset core across the
entire closed box. A source band may instead have a thinner leading portion
and a solid terminal portion. The ordinary connected-component centerline
can be displaced by other paint connected to the band; G17's box centerline
is then absent from W4. The compact bridge correctly rejects that whole box
because some leading core pixels are unpainted. Neither existing detector
captures the fully painted terminal subinterval as an independent candidate.

## Inference

A maximal contiguous solid terminal subinterval can nominate exact candidate
geometry without filling the thinner portion or moving an existing line.
Source paint supports that subinterval; it does not independently establish
a physical wall, opening host, whole-wall frame, measurement or count.

## Proposed change and authority boundary

Expose the existing closed-box assembly as a shared perception helper, retaining
all historical compact rules and identities. A separate shadow detector may
emit maximal contiguous rows/columns whose entire inset cross-section is dark,
provided the run reaches an original G17 end and includes every centerline
pixel. Emit only proper subintervals of nonuniform boxes; retain gaps and both
terminal runs when present. Reuse the historical minimum line length/aspect
gate and existing G17 classification and 20,000 primitive cap. Never extend,
average, rank or interpolate through an incomplete core.

Publication requires exact image-only/full-render equality of the candidate's
core and complete centerline, including both endpoints. Use an independent
terminal-band namespace; references and sealed receipts bind both render
hashes, DPI and detector version. Preserve every ordinary and compact index.
Both visibility readers must reject damaged linkage. Image-derived lines
cannot be discarded as native text. Unsupported page frames and occlusion
retain abstention. Existing host, equivalence, frame, metric, count and quantity
gates alone decide promotion.

Required proof includes full-solid exclusion, tapered positives, interior gaps,
thin/hollow look-alikes, two retained terminal runs, missing source edges,
occlusion, source/receipt tampering, transform/order/split invariance, cap failure,
idempotent source replay and unchanged historical source identities. A source
shadow replay precedes live authority review.

## Benchmark observations that must not influence implementation

The remaining Lot16 swing host has a source flank with a completely painted
terminal core and complete centerline, both unchanged in the full render. Its
leading core is incomplete. This is evidence of the generic capture omission,
not an algorithm input. Coordinates, printed values, project/benchmark identity,
the 27-object denominator and expected quantities never enter the detector.
Frozen truth/scoring/tolerances, source PDFs, commercial writers, measurement
defaults and W10 eligibility remain outside this change.

## Implementation and authority review

The shared box assembly preserves the historical compact detector's source
edges, sorting, core/centerline predicates and identities. The terminal detector
rejects boxes with fully painted inset cores, so ordinary full solid bands and
compact returns remain on their established paths. For nonuniform boxes it
retains only long, eligible maximal painted terminal runs. Both terminal runs
are retained when a core gap separates them. No incomplete core is filled.

The producer publishes terminal lines through a separate identity/detector
namespace after exact full-render paint agreement. Both visibility readers
validate full/image hash linkage and DPI/version. Mixed image/native requests
still authenticate every ordinary receipt before declining native-text exclusion.
Failures in the bounded terminal detector do not consume the page attempt or
publish partial observations. Unsupported page rotations keep ordinary capture.
Host/frame/measurement/count/quantity authority implementations are unchanged.

Forty new regressions cover these rules, transformed synthetic host recovery,
missing leaf/arc evidence, source-integrity damage and unchanged old observation
identities. The exact focused workflow passes 537 tests. Provider isolation,
frozen V2 integrity, compile and whitespace checks pass.

The SHA-pinned source replay resolves swing hosts from 6/7 to 7/7; swing frames
remain 4/7 and framed-opening hosts remain 10/14. All 21 raster physical IDs,
all seven sealed quantity IDs/values and all seven prior compact observation
IDs/references are preserved. The source visibility audit publishes three
terminal lines with both render hashes bound. Widths/heights remain 0/7 and
count completeness remains unresolved. The three remaining frame abstentions
are one unproven connected edge and two inconsistent aligned-band geometries.
Published GitHub CI and its independent source artifact are still required.
