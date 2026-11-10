# 3Laurel private-source contract audit (owner priority, #4135 comment 6759058490)

Scope: how 3Laurel tests, tools and workflows find the private original, and what they do when it is absent or wrong. Base `main` `81c12b417`. Companion to the canonical bridge owned by MAX; this change only touches 3Laurel loading and test setup.

## Findings (observed)

| Where | Behaviour before | Problem |
|---|---|---|
| `tests/test_antigravity_3laurel_host_binding.py` | `pytest.skip` when `documents/sources/...` is absent (path relative to the current directory) | silent skip in every mode, including a protected run |
| `tests/test_gpt1_original_3laurel_asw_candidates.py` | `pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE...")` | same |
| `tests/test_gptmax_native_filled_scale_shadow.py` | `pytest.skip` unless env `THREELAUREL_ARCH_ORIGINAL` is set | same, and a third path convention |
| `tests/test_elevation_door_vertical_witness_shadow_v1.py` | `pytest.skip` when absent **and `pytest.skip` when the hash differs** | a wrong or altered original became a skip, never a failure |
| four different resolvers | relative path, two environment names, one with a hash-mismatch skip | no single contract |
| `diag-claude-handoff-profile-stack.yml`, `diag-claude-lineage-attach-original-source.yml` | `pull_request` trigger with path filters, matrix on `documents/sources/3LAUREL...pdf`, no provisioning | on a public PR touching those paths the job can only fail on the missing PDF |
| `test-gptmax-source-authority-stages.yml` (`real-source-stages`), `verify-option-a-original-wall-source.yml` (`original-3laurel-customer-shadow`) | same pattern (`sha256sum --check` on a PDF public PRs do not have) | same; owned by other lanes, listed below |
| `gpt1-3laurel-original-floor-area.yml`, `gpt1-3laurel-source-positive-opening.yml`, the `original-partial-source` job of `gpt1-ceiling-canonical-source-sha-integrity.yml` | `workflow_dispatch` on `main` only, provisioned with `allow-missing: "false"` | correct: an absent original fails, never skips |
| `tools/gpt3_original_source_preflight.py` | stable-inode digest compares `lstat` with `fstat` | reports "original source changed during preflight" for a present file on Windows (seen locally), so the evidence reporter cannot run there; not changed here |
| `tests/conftest.py` public-CI skip scan | recognises only the Maryborough filename | the 3Laurel tests handle their own absence; no global NOT_RUN label for them |

## Change

- `tests/original_source_3laurel.py`: one resolver with the preflight's statuses. `SOURCE_PRESENT` runs; `SOURCE_MISMATCH` (other bytes, symlink, directory, unreadable) **always fails**; `SOURCE_BLOCKED` is an explicit `ORIGINAL_SOURCE_NOT_RUN ... not an original-source pass` skip **only** under `PLANREADER_PRIVATE_ORIGINAL_POLICY=skip_missing_in_public_ci` and fails otherwise (the protected workflows never set the policy); a named path that is missing always fails and never falls back to the default location; the default is under the repository root, not the working directory; an unknown policy value fails.
- The four tests above go through it. Checked on a real test in all three modes: no original and no policy fails with `ORIGINAL_SOURCE_UNAVAILABLE`; no original with the public policy is the explicit NOT_RUN skip; the original provisioned runs and passes.
- The two `diag-claude-*` measurement workflows lose their `pull_request` trigger and are guarded to `workflow_dispatch`.
- Tests: `tests/test_3laurel_original_source_contract_v1.py` (missing, mismatch in both policies, named path, symlink, directory, unreadable, unsafe mode, bad policy, precedence, repository root, no verification claim without a matching digest, and a static guard that no test naming the original skips for it on its own) and `tests/test_3laurel_original_workflow_contract_v1.py` (no pull-request job names the original without a `workflow_dispatch` guard or the public policy; the two remaining unmigrated jobs are listed explicitly so a new offender fails and a migrated one must be removed; the provisioned 3Laurel workflows keep `allow-missing: "false"`, run only on `main` dispatch and never set the skip policy). 15 single-line mutations of the resolver are all caught.

## Not done / for the bridge owner

- The two remaining unguarded PR jobs (`test-gptmax-source-authority-stages / real-source-stages`, `verify-option-a-original-wall-source / original-3laurel-customer-shadow`) belong to other lanes and the canonical bridge; they are recorded in `KNOWN_UNMIGRATED`.
- The resolver is a 3Laurel helper; if MAX defines the canonical resolver it should replace `tests/original_source_3laurel.py` behind the same `require_original_3laurel()` call.
- The preflight's stable-inode check needs a Windows-safe identity comparison before the evidence reporter can run locally.
- Nothing here is an original-source verification: no original was read by CI, no score, no frozen change.
