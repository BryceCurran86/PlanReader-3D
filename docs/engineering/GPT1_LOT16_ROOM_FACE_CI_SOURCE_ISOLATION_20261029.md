# Lot16 room-face diagnostic CI source isolation

Base: `a8d0fa5e`. Coordination #3462 claim 6478243901.

## Observed behavior

Read current AGENTS.md, engineering playbook and its required references,
shared accuracy-lever guidance and CI. Existing #3758 companion run
40748128932/job123027253791 fails with
`Lot16 SHA-verified architecture PDF unavailable: matches=0` before executing
the diagnostic. `.github/workflows/diag-lot16-room-face-scope.yml` runs
`source-room-face` on public PRs without provisioning an original PDF.
`tools/diag_lot16_room_face_scope.py` is the unchanged original diagnostic;
the workflow verifies the exact original SHA before calling it on page index 2.
Its detailed room/geometry output is already suppressed and temporary.

The existing privacy test enforces one four-step job and forbids source
credentials globally. It tests disclosure prevention, but does not distinguish
a source-free PR job from a trusted original-source job.

## Inference and proposal

A missing private original is not a producer regression or source-positive
success. Public PRs must run only source-free checks. Retain the exact
original SHA, page, diagnostic arguments, nonzero-exit rejection, private
stdout/stderr and temporary report behavior inside an explicit owner/manual/
main/repository job, including the owner who initiates reruns. Pin checkout
to the triggering SHA, verify it before provisioning the exact original
filename through the existing action, and always remove originals.

Add a public job with source-label and privacy regressions; no private source
or credential is accessible there. Extend the existing parsed-YAML contract
with adversarial guard, checkout, public-step and cleanup mutations while
retaining its original diagnostic/SHA/log-disclosure negatives. Default PR
execution skips the original-source job and does not claim original authority.

## Authority boundaries and benchmark firewall

Only workflow execution and its existing privacy test change; no diagnostic,
source producer, metric, quantity issuer, signer, customer contract, original
PDF, credential, frozen truth/evaluator, 20k primitive cap or 2.5pt snap changes.
Expected abstention remains unchanged for absent or conflicting source
evidence. No benchmark observation is used as an implementation input, and
no source measurement, customer publication or score increase is claimed.

Executed validation: 225 workflow/privacy/security/room-label/path-coverage
tests and 221 additional immutable signed-fixture/source-boundary/source-file
addition tests pass on each of Python 3.13.16 and 3.14.8 (446 per runtime).
Provider/gold isolation, frozen V2 integrity, production/truth separation,
F821/F823 lint and diff-whitespace checks pass. Inspected the complete final
diff; the original diagnostic Python block is unchanged.

Required full exact-head remote checks remain distinct from these source-free
targeted tests and trusted original execution. No new original run was
performed or implied by this workflow repair.
