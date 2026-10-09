# Ordered whole-wall frame projection

Observed: `OpeningHostFrameProducer.publish` re-proves opening/host lineage and attempts `_raster_whole_wall_frame`, then `_shared_host_frame`. `_record_projection` previously reduced a wall path to projected minimum/maximum and average offset. `_candidate_axis_data` validates segment orientation but canonicalizes each direction, so collinear backtracking can still pass the whole-wall host-role predicate. A path (20,55) -> (180,55) -> (100,55) -> (220,55) incorrectly produced the same frame as one straight run. Synthetic regressions reproduce the positive frame before the change.

Inference: extrema cannot prove one ordered physical wall run. No claim is made that a real Lot16 frame is affected.

Change: require each consecutive projected step to be strictly positive, or each strictly negative, using the existing coordinate tolerance. Reject backtracking and repeated positions; preserve globally reversed and split straight paths. Retain source ancestry, equivalence, host selection, scope completeness and all frame gates. No source interval is enlarged and no dimension/count/quantity is published.

Trace: source visibility -> physical opening/physical wall producers -> host binding -> opening host frame -> canonical opening void. Changes stop at source-space frame projection. Quantity, scale, semantic material, reconciliation, benchmark truth and denominator code remain untouched; the 20,000-primitive cap remains unchanged.

Proof: negative forward/reverse retracing and repeated vertices; positive split runs under reversal, translation, rotation and scaling; no mutation. Real-source workflow compares exact binding records and all existing positive frame records with immutable verified prerequisite artifacts (run 37830114626), requiring matching SHA and cap and rejecting duplicate IDs. The PR is a focused delta on clean #2057, not the old compact-source stack. Keep draft until latest-head production verification passes.

Benchmark observations do not set any geometry threshold or expected answer. No complete universe, additional object recovery, metric quantity or accuracy improvement is claimed.
