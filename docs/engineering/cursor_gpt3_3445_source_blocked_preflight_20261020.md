# Cursor — GPT3 #3445 original-source SHA preflight is unclassified

**2026-10-20 • Architecture-first note. Shadow/CI only. No FIRM, no PDF commit, no frozen-truth change.**

## Observed

- GPT3 integration #3445 HEAD `cd1ec93b` focused Python 3.13/3.14 and integrated activation jobs succeeded.
- Job `original-source-score` (run 39369273043 / 118453202319) and `original-source` (run 39369273052 / 118453202441) failed at `sha256sum --check` with `No such file or directory` for the Lot16 REV E and Maryborough architectural PDFs.
- Those workflows (`score-gpt3-lot16-1215-opening-local.yml`, `test-gpt3-maryborough-original-floor-score-input.yml`) named `documents/sources/...` but did not call `.github/actions/provision-original-sources`. The public checkout never contains private originals.
- Hub §5 and GPT3 lane rules require a missing original to be **SOURCE_BLOCKED**, not a production-test success and not an opaque `sha256sum` regression.

## Inference

A configured companion-source token cannot help jobs that never provision. A red X on #3445 is not proof the signed-trade + atomic-activation composition is wrong.

## Proposed

1. Insert the existing provision action (local path, fail-closed, `allow-missing` unset) into those two original-source jobs, after checkout.
2. Replace the first SHA check with `tools.gpt3_original_source_preflight`: absent file → `SOURCE_BLOCKED` exit 2; digest mismatch → fail-closed; matching digest → `SOURCE_PRESENT`.
3. Do not skip the job as success. Do not commit PDFs.

## Remaining GPT3 original-source jobs (same defect, same PR)

Observed on current `cursor/gpt3-3445-source-blocked-preflight-20261020` after the first three jobs: 11 more GPT3 workflows still named `documents/sources` without provision. Historical worktrees of older commits also cannot see the untracked provisioned PDF unless it is copied in.

`test-gpt3-four-project-evidence.yml` / `fail-closed-inventory` must not be provisioned. It requires `original_source_not_supplied_in_this_execution` and `source_sha_verified is False` on the public runner. Giving it the originals would make that absence proof fail by construction.

Do not mass-apply all ~193 workflows. Do not change `ci.yml` in this PR.

## Provision failure vs SOURCE_BLOCKED receipt (GPT3 review of #3470)

Observed: `provision-original-sources` raises `ProvisionError` and exits 1 when the token is missing, the companion file is absent, or the digest differs. That step runs first, so the job was red without emitting `tools.gpt3_original_source_preflight` JSON/exit 2.

Proposed: keep provision fail-closed (`allow-missing` unset, no success-on-missing). Immediately after it, a `Classify original source` step with `if: always()` writes the preflight receipt and exits 2 on `SOURCE_BLOCKED` or 1 on digest mismatch. Producer steps have no `always()` and do not run. Two honest semantics:

- (A) provisioning failed closed and the job is red
- (B) original-source replay emitted structured SOURCE_BLOCKED and did not run the producer

Do not set `continue-on-error` on provision. Do not treat missing originals as CI success.

## Benchmark observations that must not influence implementation

Lot16 8/27, Maryborough 0/24, Office/Food Prep m², and expected BOQ values are not inputs.
