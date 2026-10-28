# GPT3 owner-only original-eight/default and original-nine/explicit replay pin — 2026-10-29

## Observed repository behavior

- The production original Lot16 source-positive path is `tools/run_gpt3_lot16_original_sealed_score_input.py` -> source/append-only seal -> `pb_live_opening_customer_projection.py` -> `pb_customer_output_verification.py`. The exact original retention assertion is `tests/test_gpt3_lot16_original_nine_whole_retention.py`; the workflow executes this test, not a synthetic substitute.
- The trusted manual entrypoint `.github/workflows/gpt3-trusted-original-nine-replay-manual.yml` is restricted to owner `workflow_dispatch` from `main` with the same original and rerun actor. It authenticates an immutable approved base/head and the complete file allowlist *before* resolving the trusted-main source provisioner. The original is mounted read-only into an offline, read-only candidate-code container. The result log is withheld and cleaned; original PDFs and secrets are not uploaded.
- Before this change, main still pinned old base `cb6936403142ca6d14e85b029907b75aa19dbf79` and old candidate `2ef34d242c73dc3b70d3cad2ac6afe4707d2c9fa`.
- The current corrected draft #3796 candidate is `296f48e8d89496afd96b4eda5a2e65f18285227b`, integrated on reviewed base `a8d0fa5ef2dc0db3e1171ab8e8558bf9448f1e94`. The exact base-to-candidate diff has 52 paths: the previously approved 51 plus `docs/engineering/gptmax_append_only_diagnostic_scope_replay_20261029.md`. Compared with this same base, main `bde568bc4bcece94c7928021346de6b82b081796` changed 25 paths and the candidate/main intersection is empty.
- GPT MAX reported the unchanged original89 test passing on the corrected candidate in a source-bearing isolated review environment, but this does not constitute the trusted owner/main manual workflow passing at the new pin. A separate private GitHub Actions harness corrected its nested mount destination, yet run 40757964941 failed *before job steps* on both Python 3.13 and 3.14. No original-positive or official frozen score is inferred from that failure.

## Inference and first failing release gate

The stale immutable base/head pair and 51-path allowlist on trusted main cannot authenticate the corrected 52-path candidate. The first workflow trust gate must be updated before any owner-only manual replay can validate this exact candidate. After the pin is merged, a **new actual source-positive** 8/default and 9/explicit replay must still pass on both Python versions. The private Actions pre-start failure requires owner/admin runner/billing/usage investigation; it is not a source assertion result.

## Narrow change

Update only the two approved SHA values in the owner-only manual workflow and its static security contract, and add the single independently reviewed documentation path to the exact allowlist. Do **not** modify the owner-only actor/repository/ref checks, secret provisioner, network isolation, Docker mounts, original test command, source SHA checks, signed/customer eight-body retention, cleanup, or any original/frozen input. The original test directly checks source SHA, eight-body signed/customer retention, physical identity and distinct source snapshots. Page/viewport and decision-scope authority remain subject to their separate upstream production gates; this pin does not independently verify or promote those receipts.

## Required verification and abstentions

- Confirm exact branch diff, reviewed 52-path candidate allowlist, zero main overlap and both immutable SHA constants.
- Run exact-head Python 3.13 and 3.14 CI plus security/privacy/signed/customer/raster/performance checks applicable to this workflow.
- A green static or source-neutral CI result alone is **not** the trusted original8/9 positive replay.
- Do not merge #3796 or grant ninth FIRM/customer/score authority until the owner/main workflow actually passes both source-positive original paths, the #3758 mixed-snapshot integration conflict is resolved without weakening guards, and the unchanged frozen120 evaluator executes all four authenticated projects.
- Security/workflow pin merge is tracked separately from the 40 substantive GPT3 production engineering implementations.

## Untouched boundaries

No source PDF bytes, original credentials, customer signed archives, production geometry/quantities, frozen120 benchmark or denominators, 20,000 primitive cap, 2.5-point snap, or any other agent's branch is changed. Benchmark observations are not implementation inputs.
