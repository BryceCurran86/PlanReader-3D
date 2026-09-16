# Validator Replay Harness

**Version:** 0.1.0  
**Status:** Tooling-only. Production authority files changed = 0.

Validator replay harness for frozen expected-RED test contracts. This tool verifies git/content identity and test execution isolation. It does NOT prove semantic completeness itself.

## Design Principles

- **Never silently mutate** the caller's working tree
- **Use isolated temporary git worktrees** for replay at exact production SHA
- **Fail fast on preflight**; collect on production run
- **Separate expected-RED** from behavioral regression
- **Report in machine-readable JSON** + human-readable Markdown
- **Refuse to run** if validator blob SHA mismatches expected (hard fail)

## Files

- `tools/validator_replay_harness.py` — Core harness library
- `tools/validator_replay_harness_cli.py` — CLI entry point
- `tools/validator_replay_lanes.json` — Lane configuration
- `tests/test_validator_replay_harness.py` — Comprehensive test suite (Level 1/2/3)

## Quick Start

### Preflight Only

```bash
python -m tools.validator_replay_harness_cli \
  --lane identity \
  --production-sha 507c57db16be515e2432c695341bdea1e71b3fd7 \
  --base-sha 62a161519e617cdf9ce23069820dbf7c68aaf521 \
  --preflight-only \
  --verbose
```

### Full Replay with Reports

```bash
python -m tools.validator_replay_harness_cli \
  --lane identity \
  --production-sha 507c57db16be515e2432c695341bdea1e71b3fd7 \
  --base-sha 62a161519e617cdf9ce23069820dbf7c68aaf521 \
  --json-report /tmp/identity_replay.json \
  --markdown-report /tmp/identity_replay.md \
  --verbose
```

## Lanes

### identity (frozen)
- **Status:** FROZEN ✓
- **Validator Ref:** `gpt2/opening-instance-identity-redteam-v1`
- **Validator File:** `tests/test_opening_instance_identity_redteam_v1.py`
- **Blob SHA:** `b66fbc0701d498357642076688add4287f5e8a24`
- **Known Result:** 24 passed
- **Note:** Read-only reference validator. Existing PR #333 (merged).

### dimensions (normalizing)
- **Status:** NORMALIZING
- **Validator Ref:** `cursor/opening-dimensions-redteam-v1`
- **Validator File:** `tests/test_opening_dimensions_redteam_v1.py`
- **Blob SHA:** (pending freeze)
- **Note:** Do not merge. Tests being normalized by another agent.

### completeness (normalizing)
- **Status:** NORMALIZING
- **Validator Ref:** `cursor/opening-universe-completeness-redteam-v1`
- **Validator File:** `tests/test_opening_universe_completeness_redteam_v1.py`
- **Blob SHA:** (pending freeze)
- **Note:** Do not merge. Tests being normalized by another agent.

### host (normalizing)
- **Status:** NORMALIZING
- **Validator Ref:** `cursor/opening-host-binding-redteam-v1`
- **Validator File:** `tests/test_opening_host_binding_redteam_v1.py`
- **Blob SHA:** (pending freeze)
- **Note:** Do not merge. Tests being normalized by another agent. Depends on completeness.

## Preflight Checks

Run automatically unless `--preflight-only` is omitted. Fail fast on any issue.

1. **Ruff (F821, F823, E9)** — Undefined names, redefined variables, syntax errors
2. **Compileall** — Python bytecode compilation
3. **Pytest Collection** — Test discovery and metadata extraction
4. **Enum Validation (AST)** — Check for invalid `EvidenceResolutionStatus` members
5. **Unconditional Placeholders (AST)** — Detect `raise AssertionError("not implemented")`
6. **Import Validation (AST)** — Track static vs dynamic imports
7. **Blob SHA Verification** — Hard-fail if validator file SHA mismatches expected

## Test Execution

### Normal Run (GREEN tests only)
```
pytest -v --tb=short <validator_file>
```
Records: passed, failed, skipped, xfailed, xpassed

### Expected-RED Run (runs xfail cases)
```
pytest --runxfail --maxfail=1 -v --tb=short <validator_file>
```
Records: same metrics; halts on first failure for diagnosis

## Result Classification

- `VALIDATOR_GREEN` — Both normal and --runxfail pass
- `PREFLIGHT_FAILURE` — Preflight checks failed
- `COLLECTION_FAILURE` — Pytest collection error
- `IMPORT_FAILURE` — Import error (likely missing fixture or module)
- `FIXTURE_FAILURE` — Fixture breakage
- `EXPECTED_BEHAVIORAL_RED` — Expected-RED tests fail as designed
- `BEHAVIORAL_REGRESSION` — Unexpected failure
- `CONTRACT_DRIFT` — Validator blob SHA mismatch

## JSON Report

Example structure:

```json
{
  "lane": "identity",
  "base_sha": "62a161519e617cdf9ce23069820dbf7c68aaf521",
  "production_sha": "507c57db16be515e2432c695341bdea1e71b3fd7",
  "validator_ref": "gpt2/opening-instance-identity-redteam-v1",
  "validator_path": "tests/test_opening_instance_identity_redteam_v1.py",
  "expected_validator_blob_sha": "b66fbc0701d498357642076688add4287f5e8a24",
  "actual_validator_blob_sha": "b66fbc0701d498357642076688add4287f5e8a24",
  "sha_match": true,
  "timestamp": "2026-09-16T07:30:00Z",
  "changed_files": ["tests/test_opening_instance_identity_redteam_v1.py"],
  "production_file_count": 0,
  "preflight": {
    "passed": true,
    "ruff_check": {"passed": true},
    "compileall_check": {"passed": true},
    "pytest_collection": {"passed": true, "count": 24},
    "enum_validation": {"passed": true},
    "unconditional_assertions": {"found": []},
    "blob_sha_check": {"passed": true, "expected": "...", "actual": "..."},
    "errors": []
  },
  "pytest_normal": {
    "passed": 24,
    "failed": 0,
    "skipped": 0,
    "xfailed": 0,
    "xpassed": 0,
    "returncode": 0
  },
  "pytest_runxfail": {
    "passed": 24,
    "failed": 0,
    "skipped": 0,
    "xfailed": 0,
    "xpassed": 0,
    "returncode": 0
  },
  "benchmark_touched": false,
  "gold_touched": false,
  "holdout_touched": false,
  "verdict": "VALIDATOR_GREEN",
  "version": "0.1.0"
}
```

## Test Suite

### LEVEL 1: Pure Unit Tests
Fast, no external repos. Test scanners, parsers, hashing, serialization.

**Run:**
```bash
pytest tests/test_validator_replay_harness.py::Test* -v
```

**Covered:**
- Enum member validation (canonical vs invalid)
- Unconditional assertion detection (false positive avoidance)
- SHA256 hashing determinism
- Blob SHA mismatch detection
- Python file scanning (enums, placeholders, imports)
- JSON serialization determinism

### LEVEL 2: Local Integration Tests
Temp git repos inside pytest temp directories. Test worktree creation/cleanup.

**Run:**
```bash
pytest tests/test_validator_replay_harness.py::TestIsolated* -v
```

**Covered:**
- Isolated worktree creation at exact SHA
- Worktree cleanup on context exit
- Preflight stage accumulation

### LEVEL 3: Real PlanReader #333 Smoke Replay
Read-only smoke test against frozen identity validator (existing PR #333).

**Run:**
```bash
pytest tests/test_validator_replay_harness.py::TestIdentityValidatorReplay -v -s -m slow
```

**Expected:**
- Blob SHA matches
- Preflight passes
- Pytest collection works
- 24+ tests passed
- 0 production files changed
- benchmark/gold/holdout untouched
- JSON + Markdown reports generated

## Worktree Isolation

The harness creates isolated temporary git worktrees using:

```bash
git worktree add <temp_path> <target_sha>
```

This ensures:
- No mutation of caller's checkout
- Exact replay at frozen validator SHA
- Deterministic cleanup via `git worktree remove`
- Parallel-safe (multiple harnesses can run simultaneously)

## Authority Constraints

Before execution, harness verifies:

- **Production files changed = 0** (tooling-only mandate)
- **Benchmark untouched** (no test data changes)
- **Gold untouched** (no expected-value changes)
- **Holdout untouched** (no regression test exclusions)

Any violation is flagged in verdict.

## Extending the Harness

### Add New Lane

1. Update `tools/validator_replay_lanes.json`:
   ```json
   "new_lane": {
     "validator_ref": "...",
     "validator_path": "tests/test_....py",
     "expected_validator_blob_sha": null,
     "base_sha": "...",
     "status": "normalizing"
   }
   ```

2. Run:
   ```bash
   python -m tools.validator_replay_harness_cli --lane new_lane --production-sha <sha> --base-sha <sha>
   ```

### Customize Preflight

Edit `run_replay()` in `tools/validator_replay_harness.py`:

```python
# Add custom check
custom_check = run_my_validator(worktree_path, config.validator_path)
preflight.custom_field = custom_check
```

## Security Notes

This tool verifies **git/content identity and test execution**. It does NOT:

- Prove semantic completeness
- Replace manual code review
- Cryptographically verify validator correctness

It IS:

- Deterministic
- Reproducible
- Tamper-detectable (blob SHA mismatch hard-fails)

## CLI Exit Codes

- `0` — Success (VALIDATOR_GREEN or PREFLIGHT_ONLY)
- `1` — Failure (any other verdict)

## Logs and Verbosity

Default: INFO level  
With `--verbose`: DEBUG level

Logs go to `stderr`; reports to specified output paths.

## Known Limitations

1. **Pytest timeout:** 120s per run (can be increased in code)
2. **Worktree cleanup:** Slow on large repos; runs in background
3. **Ruff/compileall:** Requires these tools installed
4. **Git requirement:** Must be in a git repository

---

**Harness Status:** ✓ Ready for lane validation  
**Production Authority:** 0 files changed  
**Next Step:** Wait for #332 / #334 / #335 validators to freeze; run harness immediately
