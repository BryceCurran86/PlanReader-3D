# 3Laurel p3 wall-authority gate trace (read-only reproduction scripts)

These scripts back Addendum A of `../3laurel_p3_wall_universe_architecture_report_v1.md`. They are evidence tooling for
reviewers, **not production code and not run in CI**. They never write to the checkout: counterfactual modes swap module
attributes inside the running process only.

Inputs: a checkout of `main` (the numbers below were produced on `294f8530`/`5b2f464e`, which share the wall-composition and
scale code) and the original 3Laurel plan set, SHA-256 `014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e`
(page 3, 1-based).

```
PYTHONPATH=. python trace_tainted_walls.py <repo> "<3LAUREL pdf>" 014e9f68...e9e2e 3 out/
for m in baseline eligible eligible_wall_layer scale boundary_scale; do
  PYTHONPATH=. python counterfactual_stage.py <repo> "<3LAUREL pdf>" 3 $m out/stage_$m.json out/walls_meta.json
done
python summarize_counterfactuals.py out/
PYTHONPATH=. python scale_probe.py <repo> "<3LAUREL pdf>" 3
```

Each stage run takes about 70 s on a laptop. Expected output on the original page (these are the measured numbers):

| mode | tainted walls | authenticated hosts | scope complete | pair classes (ambiguous / distinct / same) |
|---|---|---|---|---|
| baseline | 114 | 1 | no | 36,529 / 554 / 53 |
| eligible | 4 | 2 (the extra one is a false positive, see the report) | no | unchanged |
| eligible_wall_layer | 89 | 1 | no | unchanged |
| scale | 114 | 1 | no | unchanged (scale still unavailable) |
| boundary_scale | 4 | 2 | no | unchanged |

`scale_probe.py` shows `physical_scale_viewport_required` / `physical_scale_viewport_unavailable` in production and
`physical_scale_bar_unavailable` even when the viewport bbox is forced.
