**Suggested patch for #2812 - GPT3 owns that PR and decides. Merge into `gpt3/verified-eight-match-development-checkpoint-20261016` if you agree; I will not touch #2812's branch myself.**

## Why
GitHub deletes artifact `11929406140` (ZIP SHA `950e1074...`, run 38636511093) on **2026-11-13T21:06:46Z**. After that the checkpoint workflow fails on every PR that triggers it. The five files it needs are small (186 KB, the same size class as the committed seven-row package), so they are committed instead.

## What changes (on top of #2812 `6e13e02f`)
- `docs/engineering/lot16_original_signed_eight_row_20261015/`: `production/source_sealed_run.json`, `production/verified_customer_rows.json`, `identity_map_with_1215.json`, `exact_project_report.json`, `producer_head_sha.txt`, `SHA256SUMS`, `.gitattributes` (`* -text`, so no checkout rewrites line endings and the pins hold on Windows), `README.md`. The committed blobs hash to the pins; the two production files are byte-identical to the archived signed originals that are compared after every owner merge (and to the artifact).
- The workflow reads the fixture: `sha256sum --check SHA256SUMS` and the producer-head check replace the API download, the ZIP hash and the unzip; the `GH_TOKEN` env and the `actions: read` permission are dropped; the fixture directory and the new test are added to `paths`. Everything after that (cryptographic verification, bijection, identity bindings, the scoreboard CLI expecting exit 2, the 8/27 assertions) is unchanged.
- `tests/test_lot16_signed_eight_row_fixture.py` (7 tests, run in the ordinary CI): SHA pins, producer head, fingerprint and the eight signed areas, customer rows verify one-to-one, an edited number and a missing row are rejected by the verifier, identity map and report bind the same eight. Mutation: flipping one byte of the sealed run fails six of seven.
- The checkpoint doc describes the fixture instead of the artifact lifecycle.

## Evidence
I executed the modified workflow step locally against the fixture: SHA check OK, "EIGHT ORIGINAL SIGNED SOURCE QUANTITIES AND CUSTOMER ROWS VERIFIED", scoreboard exit 2 with `matched_within_tolerance` 8, `observed_accuracy` 0.2963 (8/27), `development_accuracy` null, three projects missing. No benchmark truth, scorer, tolerance, denominator or production module is touched. Base is a branch, so no repository workflow runs on this PR; the evidence above is local.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
