# Item 35 native graphic-state join — v1 (Phase 2, shadow)

Shadow / diagnostic only. Stacked on the ref-only census (#1066). It changes no
authority, candidate construction, `classify_disposition`, `prove_existence`,
closure, wall authority, count, extractor prediction or commercial output, and
touches no benchmark-defining file.

- Module: `pb_native_graphic_state_join.py`
- Script: `scripts/native_graphic_state_join_report.py`
- Tests: `tests/test_native_graphic_state_join_v1.py`
- Approved architecture: `provenance-join/architecture_delta_native_graphic_state_join.md` (project files)

## Question

Do member incidences of ambiguous physical-opening candidates have source-owned
graphic-state characteristics that differ from the complete visible native
primitive universe of the same source scope? The answer is a distribution. No
value is a rule: a rect edge, a short segment, a fill, a stroke width, a layer
name or a dash pattern is never treated as noise or as an opening.

## Observed

- `extract_native_page` is the only producer of stroke, fill, width, layer and
  dash, together with `path_index`, `item_index` and (rect edges) `edge_index`,
  each with a producer presence flag.
- `SourceObservationRecord` keeps only `source_primitive_ref` and geometry, so the
  metadata must be replayed from the exact source bytes.
- A solid stroke is reported by PyMuPDF as `"[] 0"` with `dashes_present=True`;
  the report calls that `array_empty` and never "solid".

## Join

1. The caller supplies the exact bytes. SHA-256 is recomputed and must equal the
   source hash bound to the semantic scope; a mismatch is `no_join_sha_mismatch`
   (nothing extracted). No download, discovery, filename, URL or project name.
2. `extract_native_page` is replayed on those bytes (same function the producer
   used).
3. Key: `(page_id, path_index, item_index, edge_index | None)` parsed from the
   verified `visible:segment:d<N>i<M>[e<K>]` ref. Geometry is only an exact
   equality assertion on that identity. No bbox, nearest, tolerance or
   equivalent-path matching.

| Condition | Status |
|---|---|
| identity + exact geometry + consistent id fields | `joined` |
| unparseable ref, non-native kind | `unknown_identity` |
| no replayed segment for the key | `unknown_missing_in_replay` |
| page cannot be replayed | `unknown_replay_unavailable` |
| unresolved / not corroborated | `unknown_not_corroborated` |
| lineage differs / viewport scoped | `unknown_lineage_mismatch` / `unknown_viewport_scoped` |
| raster record | `not_native_no_pdf_path` |
| duplicate identity in replay | `conflict_duplicate_identity` |
| geometry differs on the same identity | `conflict_geometry` |
| producer id string disagrees with its index fields | `conflict_identity_fields` |
| two joined rows of one path disagree | `conflict_path_metadata` |

Absent stroke / fill / width / layer / dashes stay `absent` (producer flags) and
are never turned into a colour, a no-fill class, a named layer, a line class or 0.

## Populations (never pooled; line and rect edge always separate)

1. `participating_member_incidences`: members of candidates that hold an
   ambiguous member (a primitive in two or more candidates); both distinct
   primitives and incidences (candidate, member pairs) are reported.
2. `ambiguous_observations`: primitives in two or more candidates.
3. `visible_universe_candidate_pages` (primary baseline): every visible native
   primitive on the pages that hold candidates.
4. `visible_universe_all_scope_pages`, and
   `visible_universe_candidate_pages_minus_participating` (no overlap with 1).
5. `non_participating_candidate_members`: secondary, descriptive only.

Strata: document, then primitive class, then page. `view_id` is null and
`view_scope_status` is `unavailable` (source records own no viewport).

## Reporting guard

Graphic state is a property of the drawing path, so independent observations are
unique `(page_id, path_index)` paths. A ratio needs at least 30 of them in its
stratum and group, otherwise `ratio_suppressed_low_n`. Raw counts and the
denominators are always shown. 30 is a display guard, not a production
threshold and not evidence of significance or of any filter.

## Emitted

Per group and class (and per page with participating members): primitives,
incidences, unique paths, join-status counts, histograms of stroke, fill, paint
presence, width, dash and layer (raw values, top 25 plus `other`), visible
segments per path (page-wide) and replay-derived items per path. Comparisons of
participating against each baseline as path/primitive shares with denominators
and share differences (suppressed under the floor). A rows digest, deterministic
examples, and consistency checks. `commercial_authority_granted` is a constant
`False`.

Run (bytes are read once and are the bytes that are hashed, published and
replayed):

```
PYTHONPATH=. python scripts/native_graphic_state_join_report.py PDF_OR_DIR [...] \
    [--pages 0,1] [--output report.json] [--no-reference]
```
