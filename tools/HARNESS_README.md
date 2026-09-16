# Validator Replay Harness

**Version:** 0.2.0  
**Scope:** tooling only; no PlanReader production-authority changes.

The harness replays frozen expected-RED validator contracts against an exact production SHA without mutating the caller's active worktree.

## What it does

1. Resolves the exact production, base and validator commits.
2. Creates a detached temporary worktree at the production SHA.
3. Overlays every validator-branch change relative to the frozen validator base.
4. Verifies the validator test file by real Git blob SHA (`git rev-parse <validator>:<path>` and `git hash-object`).
5. Runs a fast preflight over all changed validator Python files:
   - Ruff `F821,F823,E9`
   - Python compilation
   - pytest collection
   - invalid `EvidenceResolutionStatus` references
   - direct placeholder `raise AssertionError(...)` checks
   - frozen blob identity
   - validator production-file / benchmark / gold / holdout guards
6. Runs ordinary pytest.
7. Runs `pytest --runxfail --maxfail=1`.
8. Emits JSON and Markdown reports.
9. Removes the temporary worktree deterministically, including exception paths.

## Important terminology

The harness verifies Git/content identity and executable test behavior. It does **not** prove semantic completeness and is not a cryptographic semantic-authority system.

`production_file_count` means Python production files changed by the **validator overlay**, not files changed by the production implementation under test.

## Current lanes

### Identity

- Validator: `gpt2/opening-instance-identity-redteam-v1`
- File: `tests/test_opening_instance_identity_redteam_v1.py`
- Frozen Git blob: `b66fbc0701d498357642076688add4287f5e8a24`
- Known exact replay: `24 passed`
- PR #333 remains draft/test-only/unmerged and is used read-only as the calibration target.

### Dimensions

- Validator: `cursor/opening-dimensions-redteam-v1`
- File: `tests/test_opening_dimension_authority_redteam_v1.py`
- Frozen blob: pending validator normalization.

### Completeness

- Validator: `cursor/opening-universe-completeness-redteam-v1`
- File: `tests/test_opening_universe_completeness_authority_redteam_v1.py`
- Frozen blob: pending validator normalization.

### Host binding

- Validator: `cursor/opening-host-binding-redteam-v1`
- File: `tests/test_opening_host_binding_authority_redteam_v1.py`
- Frozen blob: pending validator normalization.

## CLI

```bash
python -m tools.validator_replay_harness_cli \
  --lane identity \
  --production-sha 507c57db16be515e2432c695341bdea1e71b3fd7 \
  --base-sha 62a161519e617cdf9ce23069820dbf7c68aaf521 \
  --json-report /tmp/identity-replay.json \
  --markdown-report /tmp/identity-replay.md
```

For frozen validators, a blob mismatch is `contract_drift` and fails the replay.

## Verdicts

- `validator_green` — baseline and `--runxfail` both pass.
- `expected_behavioral_red` — preflight/baseline are healthy and `--runxfail` reaches a genuine missing behavior.
- `contract_drift` — frozen validator blob mismatch.
- `preflight_failure` — static/collection/guard failure.
- `import_failure` — replay reached an import failure.
- `fixture_failure` — replay reached broken fixture wiring.
- `behavioral_regression` — ordinary baseline pytest failed.
- `preflight_only` — requested preflight completed successfully.

The CLI exits non-zero if preflight failed, including `--preflight-only` runs.

## Harness tests

`tests/test_validator_replay_harness.py` includes executable coverage for:

- canonical/invalid evidence statuses;
- direct placeholder detection;
- real Git blob SHA identity;
- overlaying a validator branch onto a different production SHA;
- exact overlay blob preservation;
- deterministic worktree cleanup;
- cleanup after exceptions;
- real #333 exact-head identity replay (24/24 expected).

Run:

```bash
python -m pytest -q tests/test_validator_replay_harness.py
```

## Guardrails

The harness must not be used to modify benchmark gold, expected answers, scorer logic, tolerances or holdout material. A validator branch touching benchmark/gold/holdout paths fails preflight.
