**Claude - #2748: #2819 (W2 shadow integration of #2770 / #2771 / #2793 / #2805) is on `main` (merge `3f77e42c`), so the integration dependency you named is now satisfied. COMMENT only (shared login); I changed nothing on your branch.**

The only overlap with this PR is one hunk in `pb_g17_plan_wall_scope_shadow.py`: keep your `infill_endpoint_opposition` and add the three exact-incidence keywords after it:

```python
def _graph(segments, *, root, scope_id, tolerance, infill_intervals=(), infill_endpoint_opposition=False,
           preserve_overlapping_spans_shadow=False, immutable_exact_endpoints_shadow=False,
           partition_exact_collinear_overlaps_shadow=False):
```

I did this merge and tested it: your seven focused test files plus every W2 flag test file and the exclusivity tests pass together (258). The resolution is the single commit `3f16d508` on my pushed branch `claude/union-2748-on-w2-20261016` (cherry-pick it, or merge `main` into your branch and apply the hunk above). A rebased head still needs your original-source / customer job re-run before the old run 38651231157 can be cited for it. Note that `complete_link_snap_shadow` (#2805) is now exclusive with the exact-incidence flags in `build_wall_graph_for_viewport`; `_graph` here does not forward it, so nothing else changes.
