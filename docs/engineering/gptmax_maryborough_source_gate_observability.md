# Maryborough source-gate failure observability

Observed: `.github/workflows/test_gpt2_maryborough_grid_component_completion.yml`
calls `collect_live_physical_net_wall_claim`, builds labelled room rows and
quantity receipts, then asserts the existing original-source controls before
printing its result. Failed run 38164782173 (job 114544963674) exits at the
control receipt assertion. Its preserved artifact 11712911064 contains only a
traceback in result.json; the input source SHA is retained, but the original
observed rooms, quantities and reasons are unavailable. The artifact's checkout
SHA is 8e8c5937491b5bc0f5d81a71b95084a10f79fa72 (GitHub's tested merge), not
PR #2420's recorded head 9f94b76684cd4adde9cb0e7eab8441bdb1b1cac4.

Inference: keeping observations before validation would distinguish an upstream
absence, conflicting receipts and an actual producer regression without
weakening the assertion or assuming failure means a quantity of zero.

Proposed change: save `observed_claim.json` immediately after the existing
production call and labelled-room construction, before any quantity/control
assertion. Include the tested git SHA, original source SHA, canonical room/floor
counts, exact source-owned labels/IDs, all room-area receipt IDs/values/statuses,
evidence and reasons, and the claim's status/reasons. Also record the event's
actual PR head/base SHA so a merge checkout cannot be mistaken for exact-head
evidence. Do not change checkout selection or any production/source control.

This is CI observability only. The producer, expected controls, assertions,
source PDFs, frozen V2 and publication gates remain unchanged. Validate YAML
and embedded Python syntax, and prove the quantity/source assertions are
identical before/after. No additional project replay or broad tests are needed
for this output-only change; the existing source job will exercise it after
authorized publication.
