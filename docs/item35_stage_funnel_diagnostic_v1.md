# Item 35 stage funnel — diagnostic v1

Shadow / diagnostic only. This changes no production authority, no extractor
prediction, no commercial output and no benchmark-defining file.

- Module: `pb_item35_stage_funnel.py`
- Script: `scripts/item35_stage_funnel_report.py`
- Tests: `tests/test_item35_stage_funnel_v1.py`

## OBSERVED

- `collect_item35_authority_shadow` (`pb_item35_production_authority_shadow.py`)
  runs `SourceVisibilityProducer` → `SemanticOpeningEnumerationProducer` →
  `build_semantic_opening_inventory_completeness` →
  `GenericOpeningCountProducer.publish` once and returns one flat dict. The live
  extractor stores it as `item35_authority_shadow` and nothing else reads it.
- The dict exposes scope ids, four counts, the two semantic completeness flags,
  the semantic reason codes and record id, and the generic count status, reason
  codes and count. It does **not** expose per-opening `prove_existence()`
  results, `compare_identity()` results or host-binding decisions.
- Several fields are **shell defaults, not observations**: an empty shell
  (`source_unavailable`, `document_id_unavailable`, `page_scope_unavailable`,
  `shadow_exception:*`) has `False` flags, `0` counts and
  `generic_count_status="abstained"`. When the semantic authority publishes no
  record, the same defaults remain alongside real scope ids.
- The shadow collapses every non-conflict semantic record status into
  `"evidence_present"`. The semantic authority itself can return `CORROBORATED`
  or `ABSTAINED` with a record.
- The shadow's `commercial_count_unlocked` only means "the generic count
  authority returned a record". Its module docstring ("intentionally unsealed …
  commercial count publication remains blocked") is stale: the completeness
  adapter attaches the source-authentication seal when the semantic record
  reports `physical_opening_universe_complete`, and a minimal synthetic drawing
  with a floor-plan title yields `generic_count == 1`
  (`tests/test_item35_production_authority_shadow_v1.py` asserts this). No
  production code consumes that flag; the extractor only stores it.
- Out-of-range page scopes make the shadow raise (`ValueError:
  observation_unavailable`); the extractor turns that into a
  `shadow_exception:<Type>` shell.

## INFERENCE

- Because the shadow returns scope ids only from its non-shell path, and that
  path always continues through count publication, "scope ids present" means
  all five observable stages ran. `test_real_shadow_*` in the test file pins
  this against the real producer, so a control-flow change fails a test.
- A semantic record is present exactly when `semantic_record_id` is not
  `None`; only then are the flags and counts observations.

## PROPOSED (implemented here)

The funnel is a pure reader of that dict. It never runs an authority and never
re-derives a value; there is one diagnostic execution path.

| Stage | Observed when | Reported |
|---|---|---|
| `source_visibility` | scope ids present | output = visible observations (only if a semantic record exists) |
| `semantic_opening_enumeration` | scope ids present | status `CONFLICT` / `ABSTAINED` where the shadow says so, none for `evidence_present`; input = visible, output = enumerated openings, support count; all semantic reason codes |
| `structural_enumeration_completeness` | semantic record present | `complete`; `ABSTAINED` when incomplete; residual count; gating semantic codes |
| `physical_opening_universe_completeness` | semantic record present | `complete`; `ABSTAINED` when incomplete; enumerated openings only when complete; gating semantic codes |
| `generic_count_publication` | scope ids present | the count authority's own status, reason codes and count |
| `physical_opening_existence_per_opening`, `physical_opening_identity_comparison`, `opening_host_binding` | never | `observed=false` — the shadow does not expose them |

Rules:

- Authority can only be preserved or lowered. A status is asserted only where
  the shadow exposes one, or where "incomplete universes abstain" applies.
  Nothing is raised to `CORROBORATED`; the only `CORROBORATED` a funnel can
  show is the generic count authority's own.
- Unknown is not zero. Placeholder defaults become `observed=false` / `None`.
- `blocking` is `True` for an observed stage that abstained, conflicted, is
  incomplete, or did not publish a count. `first_blocker_stage` is the earliest
  blocking observed stage. `first_unobserved_stage` says where the shadow never
  reached; `first_blocker_stage=None` with a non-`None` `first_unobserved_stage`
  is *undetermined*, and `None` with `None` means only that no observable stage
  blocks. Neither is a pass: the identity stages are always unobserved.
- Reason codes are passed through, de-duplicated and sorted. The two
  completeness rows carry the subset of the semantic record's codes that the
  semantic authority uses to derive each flag (constants imported from
  `pb_semantic_opening_enumeration_authority`); the semantic row keeps the full
  list, including codes this module does not recognise.
- `commercial_authority_granted` is a constant `False` that cannot be
  constructed as `True`. `shadow_reported_commercial_count_unlocked` is the
  shadow's flag copied for inspection.
- The record id is `stable_contract_id("item35_stage_funnel", …)` over the full
  content, verified again on construction. The aggregate reports ties for the
  dominant blocker instead of choosing one.
- The shadow schema is pinned: an unsupported `schema_version`, a missing or
  incoherent field, or a new key raises rather than being guessed or ignored.
- Gold-free: inputs are PDF bytes and optional 0-based page indexes. The script
  derives `document_id` from the content hash so ids do not depend on file
  names or paths.

Run:

```
PYTHONPATH=. python scripts/item35_stage_funnel_report.py PDF_OR_DIR [...] \
    [--pages 0,1] [--output report.json]
```

## Not done, deliberately

- **Per-opening identity metrics.** Reporting corroborated / abstained /
  conflict counts for `prove_existence()`, `compare_identity()` or host binding
  needs a producer-owned diagnostic seam and its own architecture review. The
  generic count reason codes may mention pairwise identity outcomes; they are
  passed through on the count row and are not re-attributed to an identity stage.
- **Cross-scope opening identity (Option 1).** Not implemented. There is no
  approved producer-owned cross-view ownership or correspondence link, so
  cross-scope identity must keep abstaining (`compare_identity` already returns
  `physical_opening_identity_scope_mismatch`). None of these prove that two
  openings on different pages, viewports or revisions are the same physical
  opening: equal dimensions, equal schedule mark, equal or similar geometry,
  proximity, nearest/first matching. A design needs a positive
  ownership/correspondence authority first.
- Wiring into `extract_from_pdf`, JobHub, W10 or any commercial path. Production
  modules must not import the funnel; a test scans the repository for that.
