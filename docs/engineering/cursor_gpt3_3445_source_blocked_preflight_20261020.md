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

## Benchmark observations that must not influence implementation

Lot16 8/27, Maryborough 0/24, Office/Food Prep m², and expected BOQ values are not inputs.
