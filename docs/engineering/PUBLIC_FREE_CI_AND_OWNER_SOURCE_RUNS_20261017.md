# PlanReader public repository — free CI and private original source runs

**Owner decision (2026-10-17): remain PUBLIC.** Keep standard GitHub-hosted Ubuntu
runners; their minutes on public repositories are free under GitHub's policy.
Larger runners and storage above account allowances may still cost money.

## What the public runner must verify

- `.github/workflows/ci.yml` remains the mandatory, unfiltered CI gate:
  compilation, lint, original-source additions, frozen V2 truth separation,
  provider isolation, frozen integrity and the full source-neutral suite.
- Focused GPT3 workflows are path-filtered. Superseded runs of the *same*
  workflow and PR can be cancelled with concurrency groups; another PR and
  the latest required run cannot be cancelled accidentally by the same key.
- Owner-only original-PDF-positive tests have an explicit skip reason when
  the original PDF is intentionally absent. The source-free SHA-tamper,
  abstention, signed-quantity, customer, benchmark and malformed-receipt
  tests must still execute.
- The four-project evidence report must emit `UNPUBLISHED`, an unchanged 120
  frozen denominator and `null` accuracy with missing private source
  bytes — **never score missing PDFs as wrong or correct**.

## Authorized machine with original source PDFs

1. Keep original customer PDFs only in the owner-controlled source package.
   The public checkout's `documents/sources/` and `benchmarks/sources/`
   directories are git-ignored; never force-add or upload them to Actions
   artifacts or workflow logs.
2. Run the original-source-positive tests on that machine with the exact
   original drawing bytes available at the required local paths, for example
   `py -m pytest -q tests/test_gpt2_six_original_native_source_gates.py
   tests/test_gpt3_original_byte_gated_exact_project.py` from repository root.
   The tests' original document SHA checks still have to pass.
3. Before any git push, inspect `git status --short` and
   `git ls-files documents/sources benchmarks/sources`.
   The second command must be empty on a privacy-correct checkout.
   Do not force-add `.env`, key material or private PDFs.
4. Share only source-safe SHA receipts and masked/redacted diagnostics after
   verifying that no client contents, secrets, absolute private paths or
   commercially sensitive originals appear in the output.
5. Do not change frozen V2 truth, source manifest status or original signed
   V1 history to make an unavailable source appear publishable.

## Costs and GitHub Actions configuration

- Retain public visibility and standard `ubuntu-latest` runner sizes.
- Don't switch to GitHub-hosted **larger runners** on this budget.
- Review Actions artifact and cache storage usage regularly.
- Preserve concurrency cancellation and narrow paths on *diagnostic*
  workflows. Do **not** path-filter away mandatory main CI check contexts:
  doing so can leave branch protection pending.
- When a release is blocked on private original data, use the owner's local
  computer for source-positive tests rather than distributing those PDFs to
  a public GitHub runner.

## Important historical privacy limitation

PR #2920 removed several original customer PDFs from the **current**
public Git tree. This does **not** remove blobs from existing Git history,
forks, or cached references. A real historical purge requires separate
owner-authorized history rewriting, coordination with every agent/branch and
any affected third-party copies; do not silently force-push or delete history.
Review whether any previously exposed source material or credentials require
further owner/legal action.

**Release remains gated** on original SHA authentication, full original
multi-document producer execution, sealed quantities, exact physical identity,
fresh customer bijection and the unchanged Full Plan V2 evaluator.
