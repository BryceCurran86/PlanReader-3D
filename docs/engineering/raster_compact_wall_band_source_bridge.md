# Compact raster wall-band source bridge

## Observed repository behavior

Read the repository contract, engineering playbook, adopted topology notes,
wall/room specification, retired benchmark notice and CI workflow. The traced
source path is `SourceVisibilityProducer.augment_with_raster_opening_primitives`
→ `detect_raster_opening_source_primitives` → producer-owned G17 receipts.
The W4 path independently uses `augment_with_raster_visible_segments` →
`detect_axis_aligned_raster_segments` → `_native_page_segments` → W2/W4 →
`_resolve_raster_source_band_host_from_records`.

G17 retains short solid rectangles with four source edges. The ordinary line
detector requires a minimum run and a 3:1 morphology component aspect ratio.
A solid wall return can therefore exist in the sealed G17 source inventory
without a W4 line observation. Host binding correctly abstains when the exact
source flank has no usable W4 owner. A longer flank displaced by overlaid ink
is a separate failure and must not be repaired by loosening tolerances.

## Inference

The first two failures are missing candidate geometry at source capture,
rather than absent source wall paint. A compact filled rectangle may support
a candidate line; it does not independently prove a physical wall or host.

## Proposed change and authority boundary

First expose a shadow detector for compact filled bands. Reuse the existing
G17 detector, render policy, primitive safety cap and ordinary line-component
eligibility. Require both parallel faces, both exact end edges, a completely
painted one-pixel-inset core and all pixels supporting the exact centerline,
including its endpoints. The outermost antialiased corner pixels do not prove
or disprove the centerline's paint. Emit only the rectangle's exact
axis centerline where ordinary line-component eligibility rejects that band.
Do not interpolate missing edges, extend endpoints or rank alternatives.
Publication additionally requires those core and centerline pixels to match
the full PDF render exactly at the same producer-owned DPI. Native occlusion
or changed visible paint leaves the image-only hypothesis out of visibility.
The compact primitive reference and sealed receipt retain both image-only and
full-render hashes. Both visibility readers validate that linkage, including
after receipt/cache damage. The ordinary primitive reference grammar is intact.

After synthetic and source shadow proof, an additive producer-owned source
capture bridge may publish these lines into the existing W4 candidate seam.
It must use its own render/version namespace while preserving every historical
ordinary raster index. Existing host, equivalence, boundary, frame, metric and
quantity gates remain responsible for promotion. Original candidates remain
available. No geometry becomes a firm measurement or default count.

Required verification: compact positive cases, hollow/open/thin look-alikes,
ordinary long-band exclusion, rotations/translations/scales, deterministic
ordering, immutable input bytes, replay and source-integrity failures. A real
source replay must preserve prior opening identities and sealed quantities.

## Benchmark observations that must not influence implementation

The published Lot16 source proof has three residual swing-host failures. Two
have compact solid flanks with no ordinary raster line; the third's ordinary
line is displaced outside its source band. These observations reveal a generic
capture mismatch only. Source coordinates, printed words, project identity,
the 27-object denominator and expected quantities never enter the detector.
Frozen truth, scoring, tolerances, source PDFs, commercial writers and W10
eligibility defaults are outside this change.

## Implemented bridge and verification

The additive detector now publishes authenticated compact centerlines through
the existing source visibility producer. It uses the bounded G17 inventory,
exact closed rectangle edges and unchanged historical morphology gate.
Image-only support is insufficient: matching visible core and centerline paint
in the full render is required before publication. The sealed primitive reference
binds both render hashes, its detector version and DPI. Both visibility readers
reject missing or damaged linkage. Unsupported native page rotations retain
ordinary visibility without introducing supplemental lines. Cap failures leave
the producer retryable without publishing a partial result.

The focused workflow suite passes 497 tests, including 40 new compact-band
cases covering occlusion, source/receipt damage, transforms, replay, cap failure
and end-to-end conservative host binding. Provider isolation and frozen V2
integrity checks pass. The SHA-pinned Lot16 source replay adds seven visible
compact lines and resolves swing hosts from 4/7 to 6/7. Swing frames remain 4/7;
10/14 raster framed openings have hosts. All 21 raster physical identities and
all seven sealed quantity identities remain unchanged against the published
parent. Sealed areas remain 0.54, 0.90, 1.26, 1.80, 2.16, 2.16 and 10.08 m².

One swing host still lacks an authenticated left source primitive. The two
newly bound hosts retain frame failures for an unproven connected edge and
inconsistent aligned band geometry. Widths, heights and count completeness
remain unresolved. These abstentions are retained; the implementation changes
neither frame tolerances nor measurement or quantity promotion. GitHub CI and
its independent source artifact must verify the published tree separately.
