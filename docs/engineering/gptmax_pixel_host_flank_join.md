# GPT MAX — original G17 flank versus shadow pixel source census

## Engineering scope

A source-verified Lot16 run has 23 original opening existence records, 14
authenticated hosts and nine frames. The original #2260 source ancestry check
found seven missing host flanks with no qualifying normal W2 source parent.
Merged #2301 and draft #2340 identify original-positive pixels inside
pre-snap detector components excluded by the existing aspect/length gates;
draft #2356 provides an independently nominated **read-only** source-record
census and experimental W2/W4 ancestry for those complete pixel runs.

This tool does **not** decide that a dark run is a wall. It joins three
separately generated, explicitly nonpublishing diagnostic files:

1. The original opening/source ancestry report produced by
   `tools/diag_gptmax_raster_host_source_membership.py`.
2. Its exact-byte SHA-bound required-flank report from
   `tools/diag_gptmax_required_flank_source.py`.
3. The shadow pixel-source report from draft #2356
   `tools/diag_gptmax_raster_positive_pixel_source.py` with the experimental
   W2/W4 trace enabled.

The CLI independently SHA-checks the given original PDF bytes, checks source
and page consistency, rejects mismatched input report bytes, duplicated IDs,
invalid metric/coordinate types, changed pixel receipts, false visibility
claims, and incoherent experimental W2 parent association. It replays the
existing fail-closed flank projection geometry helper and existing numeric
tolerances, lists *all* matching run alternatives for each reported left/right
flank and preserves their W2 and experimental W4 alternative addresses.
Only the source pixel receipt was authenticated upstream; the JSON join is not
fresh provenance authority and reports
`source_receipts_freshly_reauthenticated=false`.

Every diagnostic row retains `host_publication_allowed=false`; absence from
the input files does not prove complete wall-source coverage. A matching pixel
run cannot grant visible-segment authority, physical equivalence, a host,
opening count, QuantityEvidence or benchmark score.

## Usage after both upstream reports are independently source-proven

```bash
PYTHONPATH=. python tools/diag_gptmax_pixel_host_flank_join.py \
  --pdf /path/to/original-lot16.pdf \
  --original-source-report original-ancestry.json \
  --required-flank-report required-flanks.json \
  --pixel-source-report original-pixel-shadow.json \
  --expected-source-sha 10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844 \
  --output nonpublishing-flank-pixel-join.json
```

The source input files and their SHA are provided by the runner, not looked up
from frozen V2 truth or the reference denominator. Do not use the joined
output as an authenticated source-ownership receipt. Mainline release is
blocked until Python 3.13/3.14 and full CI pass, the upstream pixel producer
has exact-original-PDF source retention proofs, and the real seven missing
flanks have been reviewed against the full original evidence.

## Protected production contract

No changes to `pb_*.py`, host-binding equivalence, opening-count logic,
source visibility, source PDFs, source topology geometry, frozen holdout
reference/universe/manifests, evaluator, denominator, tolerances, performance
gates or the 20,000-source-primitive hard limit. No verified accuracy
improvement is claimed.
