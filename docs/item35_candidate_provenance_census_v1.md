# Item 35 candidate drawing-path provenance census — v1

Shadow / diagnostic only. It changes no authority behaviour, no extractor
prediction, no commercial output and no benchmark-defining file. It rejects,
filters, ranks, merges and thresholds nothing, and it starts no cross-scope
identity work.

- Module: `pb_candidate_provenance_census.py`
- Script: `scripts/candidate_provenance_census_report.py`
- Tests: `tests/test_candidate_provenance_census_v1.py`

## Question

The candidate-structure run (#1059 / #1060) showed that ~91% of the ambiguous
observations in KSTVET, Lamu and Mbagha sit in candidates spanning three or more
structurally different families, and that the highly ambiguous observations are
mostly very short segments. This census asks, descriptively: **where do the
members of those candidates come from in the PDF — the same native drawing path,
or several?** It does not say what that means.

## Ref grammar (observed on `main`)

`SourceObservationRecord.source_primitive_ref` of a visible segment is minted by
`pb_vector_geometry_v130.extract_native_page` (`segment.id`) and prefixed by
`SourceVisibilityProducer`. `resolve_visible` already fails closed unless the
visible ref equals `"visible:" + parent.source_primitive_ref` with a native parent
on the same page and geometry.

| Ref | Meaning | `observation_kind` |
|---|---|---|
| `visible:segment:d<N>i<M>` | native line item | `native_pdf_visible_segment` |
| `visible:segment:d<N>i<M>e<K>` (K = 0..3) | one of the 4 edges of an `re` item | `native_pdf_visible_segment` |
| `visible:raster_segment:<sha256>:<detector>:<i>` | detected from pixels; no PDF path | `raster_pdf_visible_segment` |

- Both native forms carry the same `observation_kind`; the **rect-edge subclass
  is derived from the verified `e<K>` ref syntax only**, not from the kind.
- `N` is `enumerate(page.get_drawings())`, so it is per page. Native path identity
  is **always `(page_id, N)`**, never the bare index. An item is `(page_id, N, M)`.
- Only `l` and `re` items become segments; curves and quads never do, so a
  "path" here means *visible line / rect-edge segments observed on it*, not the
  PDF path's full content.
- The visibility authority rejects native geometry shorter than 0.5
  (`VISIBILITY_GEOMETRY_INVALID`), for line items and rect edges alike. A native
  visible record shorter than 0.5 therefore contradicts the producer and is
  reported as an anomaly (never filtered). Raster evidence is not assumed to obey
  the floor.

## What is measured

Scope: the pages that hold a diagnosed observation (same rule as the #1049
diagnostic), through the read-only `visible_candidate_structures` accessor
(#1059). Candidates are split into two groups by structure alone:

- **participating**: at least one member observation belongs to two or more
  candidates on its page;
- **control**: the rest. This is the source-owned baseline needed before any
  enrichment is interpreted; same-path or sequential-path construction may be
  common among non-ambiguous candidates too.

Per group: distinct drawing paths per candidate (exact 1..6) and the classes
`single_path` / `two_paths` / `three_plus_paths` / `raster_involved`; members per
path; distinct items per candidate; native line vs rect-edge members;
`path_index_span` and draw-order contiguity (`single_path`, `contiguous_run`,
`non_contiguous`); member length by fixed reporting band, by a finer tiny-length
grid, and quantiles; path class by shortest / longest member band; member band by
path multiplicity; and the visible-segment count of the involved paths versus all
paths on the enumerated pages.

For the ambiguous conflicting observations (disposition-based, as in #1059): the
size of the observation's own path, the number of distinct paths in the union of
its candidates, and whether its candidates are all / some / none single-path,
cross-tabulated with its own length band.

Also reported: per-page blocks, the full grammar/inventory of visible segments on
the enumerated pages, anomalies, representative examples with **raw refs
preserved**, and the consistency checks below.

### Fixed reporting bands (PDF units)

`<0.5`, `[0.5,1)`, `[1,2)`, `[2,5)`, `[5,10)`, `[10,25)`, `[25,100)`, `[100,∞)`,
`unknown`. They are bins, not thresholds; nothing is filtered by them.

### Consistency checks (all reported; `null` = not checked)

candidate total, ambiguous-observation total, observations-in-multiple-candidates
and observations-in-candidates equal the #1059 structure summary of the same
scope; participating + control = total; complete + `provenance_incomplete` = each
group total; path-class bins sum to the complete candidates; length-band sums equal
member totals; candidate/member ids agree with the accessor (mismatch count 0);
native path identity is page-qualified; no unavailable pages; no failed provenance
resolutions; no members outside the page inventory.

## Rules

- Read-only: public seams only (`resolve_visible`, `visible_candidate_structures`,
  `classify_disposition`); a test forbids private accessors, and no authority module
  is edited. Production code must not import this module (tested).
- **Fail closed:** a member that is unresolved, not corroborated, on another
  page/lineage/viewport, or whose ref is unparseable or contradicts its kind makes
  its candidate `provenance_incomplete` with reason codes; nothing is guessed.
  Complete raster members are `raster_involved`, not unknown.
- **Descriptive only.** Path order and proximity prove neither authorship, physical
  identity nor independence. A candidate whose members share a path is not called
  contaminated, and one spanning many paths is not called independent (a hatch or
  dimension tick is often a path of its own).
- Deterministic (sorted keys, stable ids over the content, examples by smallest
  stable id, ties kept) and bound to source SHA, revision, snapshot and semantic
  record. `commercial_authority_granted` is a constant `False`.
- No benchmark gold, expected value, scorer or tolerance is read.

## Parked

Joining stroke / fill / width / layer (available only from `extract_native_page`,
not on the observation record) is **not** part of this phase. If it is added
later it must use the exact SHA-verified source bytes and producer-derived
page/path/item keys, never approximate geometry matching.

## Run

```
PYTHONPATH=. python scripts/candidate_provenance_census_report.py PDF_OR_DIR [...] \
    [--pages 0,1] [--output report.json] [--no-reference]
```
