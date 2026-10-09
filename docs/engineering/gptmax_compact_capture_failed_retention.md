# Blocked compact capture experiment

This branch is a reproducible failed hypothesis, not an integration candidate.
Never merge it or publish quantities from its net host gain. The source report
beside this note records the actual failed gate without changing frozen truth.

Baseline: current GitHub main `0fe54c3dec256260e8aaa9aef7d50399f79ba3ae`.
Retain the unique compact/terminal capture delta from #2032 without its old
stack. Ordinary source observations and the 20,000 primitive cap are unchanged.

Observed path: `SourceVisibilityProducer.augment_with_raster_visible_segments`
publishes source-painted compact/terminal observations; W2 splits and snaps the
source graph; W4 assembles host candidates; opening host/frame authority decides
whether the local geometry and ancestry are authenticated. Pixel capture does
not supply an opening, host, physical scale, metric dimension or count.

Two duplicate-capture hypotheses were tested. Complete nominal compact extent
coverage passed 100 targeted tests but failed original all-source Lot16: main
23 existence identities / 14 hosts / 9 frames became 23 / 17 / 8. The ordinary
parent starts inside the high-resolution band at a different pixel phase.

The revised hypothesis compares the fully painted inset core with registered
ordinary source-pixel footprints. It uses the original render DPI, not a new
metric/snapping/angular tolerance. Original terminal capture stays unchanged.
All 105 compact/terminal/source-registration regressions pass; source SHA,
decode coverage and all 23 physical/canonical identity and support/root sets
remain identical. Real Lot16 nevertheless remains 23 / 17 / 8 and FAILS.

The second hypothesis restores the ordinary `:1567` ancestor and its complete
297..349 point local extent. W2 introduces an intermediate snapped vertex at
(380.64, 342.72); the old path has no such vertex. The local source fragments
retain only that original straight ancestor, but have a 336.75..338.75 point
gap. Existing conservative source-edge projection does not prove continuous
local ownership across this gap. The host/frame for physical opening
`38c03575cd66ed19cae7f9e4489f1609` is still lost. Do not flatten this path,
bridge the unproven local ownership gap, attach a remote owner or loosen the
existing five-degree predicate to make a retention assertion pass.

Exact first remaining repair: authenticate W2 source-edge/junction locality
and candidate ownership while retaining the original physical host/frame.
The added capture must not silently replace a source-supported host. New
positive, negative, ambiguity, provenance and real-source proofs are required.
The known net gain of three hosts does not authorize integration.

Reproduce with repository-pinned dependencies and:

```sh
PYTHONPATH=. python -m pytest -q tests/test_compact_local_source_duplicate.py tests/test_raster_compact_wall_band_segments.py tests/test_raster_terminal_wall_band_segments.py tests/test_raster_supplemental_source_registration.py
PYTHONPATH=. python tools/diag_gptmax_source_authority_stages.py --pdf 'documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf' --page-id 3 --source-all-pages --output /tmp/compact-capture-source.json
```

Benchmark truth/evaluators/tolerances/denominators, GPT1 quantity implementation,
GPT2 material semantics, GPT3 reconciliation and commercial publication remain
untouched. The original #2032 remains draft and blocked.
