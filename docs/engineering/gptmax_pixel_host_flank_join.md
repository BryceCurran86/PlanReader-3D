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

## Exact original-source progress — seven absent visible raster flanks

Authenticated source references only; these are not benchmark expected
quantities or project-specific runtime predicates:

- Lot16 original PDF SHA: `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`.
- Archived [source/G17-W4 run #38111200641](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38111200641), artifact
  `11691794534`: exact original ancestry JSON digest
  `b557a9061509f5a8058ea5d09bccc05f4a400534b062eef80e1a36572fecfb66`
  and exact required-flank digest
  `3100908d00529376c33b3b6daa08590d551370ba23af35640e724adb2cbab99f`.
- Archived [pixel producer run #38116673934](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38116673934),
  artifact `11695374575`: pixel report SHA
  `a078f369abdbb3a2428750f1e0989094d21c13717e99a7341501bb44dd5de289`.
  All source and retention checks passed on source producer #2356, merged at
  `c1953a55e4a54a8f0e0ff7b03d5ca9257f302ef2`. It nominated
  1,952 original-positive run records and retained 23 opening existence
  proofs, 14 host bindings and nine frames unchanged.

An independent **offline diagnostic projection** of every full positive run
onto the seven G17 opening-flank geometry receipts, using only the existing
production 2.5pt snap allowance and dual-render 0.74pt pixel allowance,
found the following candidate counts. These are *matching source-pixel runs*,
not source-visible wall segments, physical hosts or verified equivalent walls.
W4 counts are from the separate **full-page experimental** W2/W4 trace,
which has no authenticated production floor-plan viewport.

| Opening source identity (short prefix) | Original missing side | Matching positive runs on that side | Experimental W4 alternatives on that side |
| --- | --- | ---: | ---: |
| `2b2a91e8` | left | 0 | 0 |
| `33d277d4` | left | 2 | 0 |
| `81a45c3a` | right | 6 | 2 |
| `a68d0b7d` | left | 0 | 0 |
| `b2489726` | left | 0 | 0 |
| `ba7f75a2` | left | 0 | 0 |
| `f8197523` | left | 6 | 2 |

**Actual next gates:** The two candidates for `33d277d4` reach W2 but not
experimental W4. `81a45c3a` and `f8197523` have multiple alternative
experimental W4 candidates; their original source-visible identity,
authenticated page-viewport membership, positive structural-wall
classification, physical equivalence and both flank owner closure remain
unproved. Zero candidates for the other four missing flanks does not prove
there is no wall: it means the independent rejected-component source-run
inventory cannot presently nominate that missing segment. No nearest wall,
W4 first-owner selection or manufactured counterpart is permissible.

The remaining two of the original **nine unhosted physical opening
identities** are `415d34ddc0c7591b181ddadc11aefe1d` and
`b222d5310a7df1d632d5daab1a676645`, both without an authenticated
host band in the original 23/14/9 production report. The historical native
two-face/equivalence conflict for the former is not overridden by this raster
pixel audit. Neither is covered by a positive pixel-run proof.

The dedicated exact-original-source job in this PR consumes the independent
producer and actual source PDF, checks all seven G17 join rows and publishes
the full read-only artifact for subsequent physical-host verification.
No original customer quantity or frozen Full Plan V2 scoring is changed.
