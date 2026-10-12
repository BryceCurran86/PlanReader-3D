# Raster swing bridge legacy work — architecture and retention review

Observed on main 8df13e08: `OpeningHostBindingProducer.publish` consumes an
already producer-authenticated physical opening; `_opening_geometry` accepts
both established raster wall-band patterns and preserves finite/non-square/
span-to-thickness guards. `OpeningHostFrameProducer._raster_whole_wall_frame`
accepts the same two patterns through current source/whole-wall/equivalence
proofs. `_gap_span_for_opening` uses the sealed raster aperture only for spatial
source-label ownership. `OpeningLabelDimensionProducer.publish_scope` and the
independent semantic producer still authenticate text, ownership and legend
meaning before measurement. Native/vector patterns cannot borrow the raster
bbox. These traces cover the substantive bridge deltas in legacy #1566/#1595.

The seven archived swing-specific label geometry/invalid-box assertions in
#1566's separate test file are not all retained under that filename. Fresh
execution of the exact archived assertions against current main passes 7/7.
Existing main already retains swing host geometry and the larger producer-owned
raster label/frame test suites. Proposed: retain those seven unique assertions
as tests only; change their historical EXPECTED RED wording to current contract
language. Production/authority code remains untouched.

Legacy #1645's entire original raster-detector function inventory (12 functions)
is AST-identical to current main, including anisotropic registration. Its
old unconditional compact-code meaning regex was superseded by independently
authenticated source legend semantics; it must not be reintroduced. This
retention review does not assert source completeness, width/height ordering,
additional hosts, or an accuracy gain.

Expected negatives remain invalid/square/zero-area/nonfinite apertures, native
bbox borrowing, unowned semantics and ambiguous source evidence. Original
production replay still retains 21 hypotheses / 14 hosts / nine frames. Keep
all seven unresolved raster hosts, missing frame proofs and count/measurement
gates open. Frozen benchmark truth, evaluator, tolerances/denominators, 20k cap,
W10 and commercial writers remain untouched. Merge the retained tests only
when current-head required CI passes, then close superseded legacy PRs without
claiming that their remaining host/measurement work is complete.
