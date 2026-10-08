# Exact native text ownership of raster render fragments

Observed: `SourceVisibilityProducer.augment_with_raster_visible_segments`
detects lines in the full PDF page render, then restricts them to embedded image
regions. Native text painted over those regions can therefore generate raster
line observations. W4 retains those observations; connected raster host frames
correctly abstain when aligned alternatives lack positive DISTINCT evidence.
Source geometry is not deleted before W2.

Source-only inspection of the five aligned fragments blocking the current
Lot16 connected frames shows: the full render has ink; the images-only render
is exactly white; the full render pixels equal a text-only render; and each
fragment lies wholly inside one native word. These observations locate the
defect and must not supply project coordinates, numeric values or target counts
to production logic. Bounding-box membership alone is insufficient.

Inference: an exact authenticated raster primitive whose complete source
component region is explained by one native word's text paint, with no image
or graphic ink or differing
full-page pixels, has source text ownership. That proposition can oppose its
physical wall role without asserting universal non-existence or wall identity.

Proposed shadow proof: extend the existing authenticated native page renderer
with mutually exclusive text-only and graphics-only layer views.
SourceVisibilityProducer must
authenticate the exact revision, snapshot, raster visibility receipt, raw
primitive reference and native text receipt. Its full render hash must match
the raster receipt. Require one trusted native word to contain the complete
primitive's full morphology component, no competing word overlapping it, white
images-only and graphics-only pixels throughout its component region, and exact
full/text-only
pixel equality throughout that region. Reconstruct every compatible source
component using the original detector's exact perpendicular coordinate and
existing endpoint snap budgets (two horizontal passes, one vertical pass).
Require complete coverage of all those alternatives; never rank them. Checking
the entire word is unnecessarily broad because independent vector dimension
lines may cross other parts of its bounding box. A graphics-only view also
rejects coincident native line art even if text paint hides its pixel difference
in the full render. Retain all source geometry and return existing candidate
`symbol` EvidenceAtoms with opposing polarity and complete support coverage.
Missing, stale, tampered, overlapping, mixed-raster or mixed-vector evidence
cannot prove this role. No decoded numeric value enters the rule.

After synthetic and real-source proof, a connected raster frame may exclude an
aligned alternative only if this producer-owned role proof covers every source
primitive of that candidate. Otherwise its existing DISTINCT requirement
remains. Retain the opposing atoms on the frame receipt. Do not fabricate a
DISTINCT equivalence relation, mutate W4, discard G17 hypotheses, enlarge pixel
budgets, change metric authority, or promote counts. Native-only alternatives
and mixed physical/text candidates remain blocking.

Traced boundary: immutable PDF renderer -> raster visibility/text authentication
-> exact source-role atoms -> connected-frame extent exclusion. Existing opening
and host reproofs, complete W4 scope, simple path and uniform band requirements
stay mandatory. Semantic enumeration, commercial quantities, V2 truth,
denominator, scoring and tolerances remain untouched. The user's continuation
authorizes implementation without a review checkpoint.

Synthetic proof covers translation, scale, all PDF quarter-turn rotations,
unrelated content, arbitrary text, overlapping words, image and vector mixing,
coincident native graphics hidden by identical text pixels, missing or tampered
geometry/visibility/text/source receipts, stale revisions, replay, input order
and no mutation. Renderer layer views reject contradictory flags and caller
clips. Complete connected frames retain the opposing atoms; independent native
wall competitors and damaged text receipts still block. Metric quantities are
absent in the synthetic frame examples. The focused suite passes 457 tests.

An initial real source replay recovered swing frames from 1/7 to 4/7, retained
all 14 framed and seven swing physical identities and the seven sealed areas.
The final implementation additionally rejects graphics-layer ink, including a
synthetic case where full and text-only pixels are identical. The published
GitHub source run must repeat the complete handoff with this final guard and
retain the frame's source-role atoms in its diagnostic artifact. Hosts remain
4/7; widths/heights remain unresolved. Counts and the 27-object reconciliation
are not inferred from these local geometric improvements.

Final four-layer source-role replay proves all five blocking raster primitives
as native text, including full morphology support and absent native graphics
ink. No coordinate or printed word is supplied to the production rule.

The complete final local handoff confirms four of seven swing host frames,
three frames carrying five unique complete four-layer source-role atoms,
all 21 prior raster physical identities preserved, and seven sealed opening
areas unchanged. Source SHA is
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`.
The sealed areas are 0.54, 0.90, 1.26, 1.80, 2.16, 2.16 and 10.08 m2.
Native positives remain 44; framed/swing positives remain 14/7; swing/framed
hosts remain 4/10. Swing width and height resolutions remain zero. This source
proof does not close the candidate universe or produce a V2 accuracy score.

Publication status: the prior closure correction passed full GitHub CI on both
Python 3.13 and 3.14. This final source-role implementation passes 457 focused
tests and the complete local source handoff. Automatic approval review rejected
publishing it to the existing PR #1953, including after verification of the
existing destination and the ten-file code/test/workflow/report-only diff.
The reviewer explicitly requires renewed user approval. No source PDF,
customer output or benchmark truth is included in that diff. Final GitHub CI
must run after publication is approved.
