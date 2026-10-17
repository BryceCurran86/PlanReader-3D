# Original source provisioning for CI

Status: built, **not applied**. No existing workflow has been edited. The step that edits them
(`scripts/apply_provision_original_sources.py`) runs only after the owner has created the companion repository and the
secret below.

## Why

The ten original owner/client PDFs are no longer in this repository (`docs/PRIVATE_ORIGINAL_SOURCES.md`, #2920).
186 workflows (201 jobs, including `ci.yml`) and 23 test files read `documents/sources/<name>.pdf`, so on any tree that
includes `main` those jobs fail at `sha256sum --check` or `FileNotFoundError`. This provisions the files onto the runner,
verified, and nowhere else.

## Design

* **Authority is the frozen manifest.** `benchmarks/frozen_holdout/full_plan_v2/projects/*/source_manifest.json` pins every
  file's name, `size_bytes` and `sha256`. Nothing is hard-coded in the action. A name that is not in a manifest cannot be
  requested; two manifests that disagree about one name are an error.
* **Fail closed.** No token, no companion repository, a 401/403/404, a size above or below the pin, or a digest mismatch
  each fail the step. A file is written to a temporary name next to its destination, verified, and only then renamed, so a
  bad download never leaves a file that looks valid. A final independent check re-hashes every selected file.
  A file that is already present with the right size and digest needs no token and no network, so a branch cut before
  the originals were removed keeps working.
* **No silent skip.** `allow-missing` defaults to `false`. Setting it to `true` only turns the failure into a warning and
  `outputs.provisioned=false`; use it only for a job that genuinely runs without the originals.
* **Token handling.** The token is read from the environment (never argv), masked with `::add-mask::`, sent only to
  `api.github.com`, and removed from the request before any redirect to another host (GitHub answers raw contents requests
  with a redirect to its object store). Tests cover each of these against local servers.
* **Nothing is published.** Files land in `documents/sources/`, which is git-ignored, and `scripts/check_private_original_source_additions.py`
  refuses a commit that adds anything there. The transform refuses to touch a job that uploads an artifact whose path could
  include the originals (`.`, `**`, `documents/...`, the workspace), because artifacts of a public repository are downloadable
  by anyone; today no workflow does, and a test pins that.
* **Excluded on purpose:** `package-full-plan-v2-verified-checkout.yml` (job `snapshot-public-repository-only`) is obsolete.
  It archives the tracked checkout and asserts a PDF is inside it, which the originals-out-of-git policy forbids. It will fail
  until someone deletes or rewrites it; provisioning cannot help because `git archive` skips untracked files.
* **Fork pull requests** receive no secrets, so original-source jobs fail closed on them. That is intended.

## Owner setup (one time)

1. **Create a private repository** for the originals, for example `BryceCurran86/PlanReader-3D-sources`. Keep it private,
   turn forking off, and do not add collaborators or apps you do not need.
2. **Upload the ten PDFs** to `documents/sources/<exact file name>` in that repository (names, sizes and digests are in the
   manifests; the preflight `tools/diag_gpt1_source_pdf_package_preflight` checks them). Optionally tag the commit
   (`sources-v1`) so CI can pin it.
3. **Create a fine-grained personal access token**: GitHub, Settings, Developer settings, Personal access tokens,
   Fine-grained tokens. Resource owner: your account. Repository access: *Only select repositories*, only the companion
   repository. Permissions: Repository, **Contents: Read-only** (nothing else). Set an expiry (90 days) and put the renewal
   date in your calendar.
4. **In PlanReader-3D**, Settings, Secrets and variables, Actions:
   * Secret `ORIGINAL_SOURCES_TOKEN` = the token.
   * Variable `ORIGINAL_SOURCES_REPOSITORY` = `BryceCurran86/PlanReader-3D-sources` (your name).
   * Variable `ORIGINAL_SOURCES_REF` = `sources-v1` (optional; empty means the default branch).
5. **Run the smoke test**: Actions, *Provision original sources (smoke test)*, Run workflow. Green means ten files
   downloaded and verified, the checkout stayed clean, and the no-token path failed closed.

## Rolling it out to the workflows

After the smoke test is green and this change is on `main`:

```bash
# 1. the gates that matter most first: ci.yml and the GPT3 signed-output replays
python scripts/apply_provision_original_sources.py --action-ref <merge-commit-sha> \
    --only ci.yml --only 'score-gpt3-*' --only 'test-gpt3-*' --apply
# 2. then the rest, in one or two batches
python scripts/apply_provision_original_sources.py --action-ref <merge-commit-sha> --apply
```

The script inserts one step after the job's first `actions/checkout`, naming exactly the manifest files the job mentions
(jobs that run the whole `tests/` tree, and jobs that only mention the directory, get all ten). It re-parses every file and
refuses to write if anything other than that one step would change; a second run changes nothing. Pin `--action-ref` to a
commit SHA so the code that sees the token cannot change under you. Each edited workflow lists itself in its own
`pull_request` paths, so each runs once on the rollout PR; do it in batches to keep the queue short.

## Operations

* **Rotate the token** before it expires: create a new fine-grained token, replace the secret, delete the old token.
* **Add or replace a source**: update the manifest (a separate benchmark-defining PR), upload the file to the companion
  repository, move the tag.
* **If a job reports "original sources NOT provisioned"**: the message names the files; check the secret and variables exist,
  the token has not expired, and the file is at `documents/sources/<name>` in the companion repository at `ORIGINAL_SOURCES_REF`.
* **Residual exposure**: the PDFs remain in this repository's git history, earlier PR refs and any forks or caches until the
  history is purged under owner control. Provisioning does not change that.
