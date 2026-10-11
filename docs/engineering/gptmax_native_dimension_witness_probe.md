# GPT MAX: source-owned native dimension witness probe (read-only)

## Why

The byte-verified original Lot16 page 3 currently contains a G17 physical
opening record `physical_opening_existence_415d34ddc0c7591b181ddadc11aefe1d`
with **six native support observations** and an unresolved two-face wall-host
conflict. Visual proximity to the printed 90/450 dimension annotations cannot
prove it is not a real opening. The G17 source truth must be preserved until
all supporting line and printed dimension-cap provenance is authenticated.

The existing `pb_source_visibility_authority.native_dimension_cap_evidence`
returns **opposing CANDIDATE atoms only** when an entire original source-owned
dimension line, both endpoint cap/tick systems, and trusted native text bind.
The new diagnostic tests this exact existing authority against the original
opening's complete source support; it never treats a nearby word or pixel as
a physical source owner.

## Exact-source command

```sh
PYTHONPATH=. python tools/diag_gptmax_native_dimension_witness.py \
  --pdf "documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf" \
  --page-id 3 \
  --representative-observation-id source_observation_50346acbb28e7a0a9e7311b4b6965f8a \
  --expected-opening-record-id physical_opening_existence_415d34ddc0c7591b181ddadc11aefe1d \
  --expected-source-sha 10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844 \
  --output original-native-dimension-source-probe.json
```

The opening and representative observation IDs come from original-source
[run 38132210312](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38132210312),
not from a frozen V2 expected quantity. IDs are CLI diagnostic selection,
**not runtime opening rejection predicates**. The generic tool requires
real original bytes and an exact source SHA; it independently re-ingests the
PDF, authenticates the native support IDs, re-proves the opening identity,
and asks the existing producer to validate exact complete dimension opposition.

## Interpreting the report

- `native_dimension_cap_opposition_proven=true` only means complete authenticated
  **opposing candidate evidence** was found for the specified support IDs
  *within one original-source candidate atom*. A union of disconnected partial
  dimension-cap candidates is never treated as complete evidence.
  It never proves physical nonexistence or automatically removes a G17 claim.
- `false` means this particular strict producer could not authenticate
  complete dimension caps; it does not prove that the native record is a wall
  opening, either. Review missing/ambiguous source paths, not nearest labels.
- Every result explicitly says no physical host, count, quantity, or benchmark
  publication is allowed. Existing 14 Lot16 authentic hosts and nine frames
  must survive any later production change.
- This tool does not touch source documents, W2/W3/W4 lineage, frozen V2
  manifests/truth/tolerances/denominators/evaluator, or the 20,000 input cap.

The generic synthetic G17 regression covers deterministic read-only
provenance and foreign/stale source rejection; exact original Lot16 verification
remains mandatory before any production change.
