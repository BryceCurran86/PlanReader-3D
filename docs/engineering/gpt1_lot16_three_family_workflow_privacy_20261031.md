# GPT1 — original three-family Lot16 workflow privacy repair (2026-10-31)

## Observed repository behavior

- Public PR job `GPT1 Original Lot16 Three-Family Quantity First Failures` checks out a possibly untrusted PR head and executes an original-source diagnostic requiring a private Lot16 PDF that PR checkouts must not contain. Immutable head `98fd56be212d48509c34663de400c1ddf4461df1` of GPT1 #4134 failed its original-source job at precisely this gate (workflow run 41150959030).
- The same workflow currently uploads `artifacts/gpt1-original-lot16-first-failure/` under `if: always()`. The diagnostics can include original-owned source text, geometry, physical records, measurement first-failure ledgers, page/viewport and ownership identity. A public artifact is therefore not an acceptable destination, even if it is produced only by an owner-run.
- Live diagnostic `tools/diag_lot16_room_face_scope.py` runs `source_figured_scale_shadow`, `original_figured_plan_plane_shadow`, source owned plan view, production floor/opening first-failure diagnostics and the existing source-owned stage predicates. They are diagnostic, not independently FIRM. The W1–W10 geometry/canonical adapter is also shadow-tier; it does not grant measurement, opening host, commercial or benchmark authority.

## Inference and first failing gate

The public PR event has no original PDF and must not obtain its credentials. The unconditional source diagnostic is an event-gating and source-private output defect, **not evidence of a missing original PDF or a construction measurement failure**. Retrying PR CI with private source credentials would cross an unauthorized trust boundary.

## Proposed change

1. Retain existing source-free scale, source-plane, owned figured bridge and frozen-truth firewall tests in a credential-free PR job; add workflow privacy regressions.
2. Only on exact repository `BryceCurran86/PlanReader-3D`, trusted `workflow_dispatch` on `refs/heads/main`, with both actor and triggering_actor being the owner, check out immutable `github.sha` without credentials and verify the SHA. Use the existing pinned private-source provision action with `allow-missing: false` to obtain the exact Lot16 filename; run the unchanged SHA-256 check and original source diagnostic.
3. Retain all existing stage assertion predicates for first-failure family completeness, figured-scale nonauthority, and source-owned original plan-view nonpromotion. Move source output only to ephemeral `RUNNER_TEMP`, capture diagnostic stdout/stderr privately, do not print source-derived summaries, never upload an artifact, and always remove private original/report bytes.

## Validation and abstention

- Adversarial workflow tests verify owner/repository/ref/event/rerun guards, immutable pinned checkout, exact-name SHA source provisioning, source-free PR job, original assertion presence, no PR private source access, no diagnostic log/JSON/artifact upload and unconditional cleanup.
- The source-free tests must pass before merge; full exact-head Python 3.13/3.14 CI and relevant companions must pass. An original trusted run may be performed separately, but a public PR run is explicitly not source-positive proof.
- Missing original, missing secrets, mismatched SHA, malformed report, unproven plan-view/figured-axis authority or missing first-failure family must fail closed, never mint FIRM quantities or a frozen score.

## Untouched ownership / benchmark firewall

No changes to any production source module, original PDF, source hash, source credential, signed Lot16 or Maryborough customer rows, V2 frozen gold or evaluator, 20,000 primitive cap, 2.5pt snap, or GPT2/GPT3/GPT MAX branches. This fixes a CI evidence/security boundary; it is not an accuracy milestone and must not be advertised as score improvement.
