# Cursor — missing finish codes and empty native census must not authenticate

**2026-10-20 • Architecture-first. Shadow / existing authority only. No FIRM.**

## Observed

- `evaluate_source_open_passage_connection_shadow` treats both finish codes missing as `contiguous_finish_flow` and publishes CANDIDATE. Differing codes without a stroke already conflict. Absence of finish evidence is not shared-finish proof.
- `ScheduleOpeningInstanceBindingAuthority` sets `native_census_authenticated = True` before iterating `published.text_observation_ids`. An empty census stays True, so an OCR-only contained tag can still request a schedule description as if native words were authenticated.

## Inference

Empty evidence is not corroboration. Geometry of caller wall edges is already required for a passage candidate; finish continuity still needs stated codes or a physical stroke.

## Proposed

1. Passage: both finish codes missing and no aligned transition stroke → ABSTAIN (`finish_evidence_unavailable`). Do not invent contiguous flow.
2. Schedule binding: `native_census_authenticated` is True only when `text_observation_ids` is non-empty and every resolved word is corroborated. Empty stays False.

## Benchmark observations that must not influence implementation

Office/Food Prep/Wash Up m² and expected opening descriptions are not inputs.
