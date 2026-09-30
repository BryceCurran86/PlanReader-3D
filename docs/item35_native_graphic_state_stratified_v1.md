# Item 35 structure-adjusted graphic-state check — v1 (Phase 2b, shadow)

Shadow / diagnostic only. Stacked on the Phase-2 native graphic-state join (#1079).
It changes no authority, candidate construction, `classify_disposition`,
`prove_existence`, closure, wall authority, count, extractor prediction or
commercial output, proposes no filter, and touches no benchmark-defining file.

- Module: `pb_native_graphic_state_stratified.py`
- Script: `scripts/native_graphic_state_stratified_report.py`
- Tests: `tests/test_native_graphic_state_stratified_v1.py`
- Byte-identity fixtures: `tests/fixtures/native_graphic_state_join/`
- Approved design: `provenance-join/design_stratified_graphic_state_check.md` (project files)

## Question

The six-source Phase-2 run found graphic-state differences between participating
member primitives and the rest of the visible native primitives, and warned that
they overlap with path size and edge visibility. This check asks whether any
difference is left **after holding path structure fixed**. Nothing else.

The only claim it can support is *residual association between graphic state and
candidate participation after conditioning on path structure*. It cannot say a
candidate is false or real (participation is a property of how candidates are
built, not a truth label), and no rect edge, short path, filled path, colour,
width, layer name or dash pattern is ever a rule.

## Refactor of the join (the only change to #1079's module)

`build_native_graphic_state_join` used to compute the per-primitive rows and the
group memberships and aggregate them in one function. The first half is now the
public `build_native_graphic_state_join_rows(...)`, which returns an immutable
`NativeJoinRows` (mapping proxies, frozensets, tuples). The aggregator consumes
that bundle unchanged. `digest_of_rows` was extracted the same way.

Proof that nothing changed: synthetic PDFs (three page scopes, with and without the
structure reference, SHA mismatch, an absent semantic record, unavailable candidate
pages, and replay mutations that force every non-joined status) were run against the
#1079 head (`8a3bb657`) and the refactored module: every `record_id` and every
`payload_json` is identical: 160 cases over two independently rendered sets of the 12
synthetic PDFs (PDF bytes are not deterministic), 4,264,234 payload bytes compared. 40 of
those cases are pinned in the repository
(`golden_1079_output.json`, recorded from the #1079 head under PyMuPDF 1.28.0) and
covered by a regression test, one per case. The case test skips if the installed
PyMuPDF differs from the pin, so a second test fails if the pin in
`requirements.txt` moves without the golden being re-recorded.

## Unit and groups (per primitive class; never pooled)

The unit is the unique page-qualified native path: graphic state is constant per
drawing path, so a path is one independent observation however many primitives it
holds. A path holding lines and rect edges is two class-specific records.

- **participating**: a path holding at least one participating member primitive
  (the same primitive set as the Phase-2 join).
- **baseline (primary)**: every other visible native path of that class on the
  candidate pages, i.e. `visible_universe_candidate_pages_minus_participating` at
  path level. A path with any participating primitive is participating, so no path
  is on both sides; `mixed_paths` counts participating paths that also hold
  non-participating primitives. (Phase 2's primitive-level baseline kept those
  non-participating siblings, so its baseline path counts can be larger.)
- **control (secondary, descriptive only)**: baseline paths holding a
  non-participating candidate member. Only counts are reported; never standardised
  against.

A path with any primitive that did not join by exact identity is excluded (never
guessed) and counted in `integrity`; `analysis_complete` says whether any were.

## Strata

| Plan | Class | Strata | Outcomes |
|---|---|---|---|
| `lines_fill_presence` | line | page x visible-segments band (1, 2, 3-5, 6-10, 11+) | fill present |
| `lines_conditioned_on_fill` | line | page x visible-segments band x fill presence | stroke, width, layer, dash; fill colour (filled paths only) |
| `rect_edges_by_visible_edge_band` | rect edge | page x visible-edges band (1-2, 3-5, 6+) | fill colour, paint presence |
| `rect_edges_by_visible_edge_count_fine` (sensitivity) | rect edge | page x visible-edges band (1, 2, 3, 4, 5-8, 9+) | same |
| `lines_fill_presence_fine_bands`, `lines_conditioned_on_fill_fine_bands` (sensitivity) | line | as the line plans, bands 1, 2, 3, 4, 5, 6-10, 11-20, 21-50, 51+ | same |
| `lines_fill_presence_page_pooled`, `lines_conditioned_on_fill_page_pooled`, `rect_edges_page_pooled` (sensitivity) | line / rect edge | as the approved plans but **without page** | same |

Fill presence is not a stratifier when it is the outcome. The sensitivity plans are
additions to the approved design, each labelled `sensitivity_only`, none replacing
an approved plan:

- *Fine rect bands.* One rect has at most four edges, so the approved 3-5 band
  pools a clipped rect (3) with a full one (4), which could leave residual
  confounding by edge count that would read as a graphic-state effect.
- *Fine line bands.* Participation is path-level and grows with path size, and the
  approved top band (11+) is open-ended, so giant CAD paths sit beside small ones in
  one stratum. The finer bands close that band.
- *Page-pooled.* Page x band strata can be so thin on a many-page source that none
  reaches 30 paths in both groups, leaving no adjusted estimate at all. Pooling
  pages keeps an estimate, at the price of leaving any page-to-page difference in
  graphic state uncontrolled: an effect that shows only here may just be a page.

Fill colour is descriptive only.

Outcome values: `absent` is always shown when present, then the most common
values by path count (ties by value), at most 12 values, the remainder folded into
`other_values`. Values are chosen from all candidate-page paths of the class, so
they never depend on the participating/baseline split. The folded values are
themselves listed per field (`folded_values`, participating-heavy first, at most 50,
with `folded_values_omitted` for the rest) so a rare value that only participating
paths use is visible although it has no outcome of its own.

## Per outcome

- **crude**: participating vs baseline over all paths, with raw counts.
- **eligible_strata_only**: the same, restricted to eligible strata.
- **standardised**: direct standardisation to the participating stratum mix over
  eligible strata (the standardised participating share equals its eligible-only
  share; only the baseline is reweighted).
- **coverage**: participating (and baseline) paths that sit in eligible strata.
- **sign_concordance**: eligible strata that go positive, negative or zero, with the
  participating paths in each, and the dominant-sign share with its denominator.
- **retained_fraction_vs_eligible_only** / **sign_relation_vs_eligible_only**: the
  standardised difference over the eligible-strata-only difference (isolates what
  standardising did).
- **retained_fraction_vs_crude** / **sign_relation_vs_crude**: the standardised
  difference over the crude difference (adds what dropping the ineligible strata
  did; a crude effect carried entirely by ineligible strata shows up here, not in
  the eligible-only pair). Both are unbounded ratios, null when the reference is
  zero; the relation is `same_sign`, `opposite_sign`, `reference_zero`,
  `adjusted_zero`, `both_zero` or `not_estimable`.
- **strata_rows**: every stratum `[index, k_participating, k_baseline, difference]`,
  ineligible ones with a null difference. Nothing is hidden where a direction
  reverses. Indexes refer to `strata.table`.
- **null_control**: see below.

Difference is always participating minus baseline. Eligible means at least 30
unique paths in **each** compared group (`ratio_suppressed_low_n` below that, raw
counts still shown; the floor also applies to coverage). The floor is a reporting
guard, never a production threshold and never evidence of significance. Arithmetic
is exact (rationals), rounded once on output, so results are independent of input
order.

## Null control

The baseline paths are split into two halves by a hash of (source SHA-256, page,
path index, primitive class, fixed salt); three fixed salts are reported. The split
ignores participation, reads no gold, mutates no row and replays identically. It is
a calibration reference for the size of a difference with no participation effect,
**not** a significance test. The halves are usually larger than the participating
group and have their own eligible strata, so it understates the sampling noise of
the observed comparison. The split is keyed by the source hash, so it follows the
file's bytes (it differs between two files with different bytes even if their
content is geometrically identical).

## Emitted

Per entry: binding (source SHA-256 = supplied bytes SHA-256 = replayed bytes,
semantic record id, PyMuPDF version), `integrity`, `definitions`, and per class the
population block and the plans above. `commercial_authority_granted` is a constant
`False`; `view_id` is null and `view_scope_status` is `unavailable`.

`integrity` holds the rows digest (identical to the Phase-2 `rows_digest` for the
same source), join status counts, candidate and participating counts,
participating incidences and primitives per class for cross-checking the Phase-2
report, the Phase-2 replay summary (`replay`), unavailable candidate pages,
`participating_members_accounting` (where every distinct participating primitive
went: analysed, in an excluded path, outside the candidate pages, non-native such as
raster, or without a join row; the check fails if any is unaccounted for), excluded
paths, the optional #1059 structure cross-check, and `analysis_state`:
`complete`, `no_candidate_pages`, or `incomplete_unavailable_candidate_pages`,
`incomplete_candidate_members_without_row`, `incomplete_paths_excluded`. A page that
fails to replay makes every native path on it excluded, so an incomplete state means
the numbers describe a subset.

Run (bytes are read once and are the bytes that are hashed, published and
replayed; the document id derivation is the join report's, so the semantic scope is
the one that report was built on):

```
PYTHONPATH=. python scripts/native_graphic_state_stratified_report.py PDF [...] \
    [--pages 0,1] [--no-reference] --output report.json
```

Each entry carries `analysis_state`, and the run-level `coverage` counts
`entries_analysis_incomplete` (labels in `analysis_incomplete_labels`) and prints a
warning on stderr. The exit code is 1 when an entry errored or could not be read and
0 otherwise: an incomplete analysis is data to read, not a crash. `--no-reference`
skips the independent #1059 candidate-structure cross-check.

## Reading the report

- Start from `integrity.analysis_state` and `integrity.checks`; then `coverage` of each
  outcome: an adjusted number that covers little of the participating population says
  little about it.
- A crude difference that shrinks or flips after standardising is path structure; a
  difference that survives inside strata is the only thing this check can call a
  residual association.
- Sign concordance with a denominator of one or two strata is not concordance.
- `ratio_suppressed_low_n` is the floor, not a zero; raw counts are always printed.
- A field with one value in both groups prints a difference of 0.0 that carries no
  information (check `values_analysed`). A difference that prints 0.0 can still count
  as positive in the sign tallies: differences are rounded to six places, the signs
  are exact.
- `control_paths` is a count only.

## What it does not do

No candidate is rejected, filtered, ranked, merged, thresholded or scored; no
opening identity, closure, count, wall or commercial quantity changes; no benchmark
row, gold value, mapping or tolerance is read; no source is downloaded or
discovered. Lamu rows are not inspected. A residual association, if one appears,
would need its own architecture review and an independent truth source before it
could inform anything.
