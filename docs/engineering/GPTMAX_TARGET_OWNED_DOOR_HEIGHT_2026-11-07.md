# Target-owned door height at the source-to-customer boundary

Owner: GPT MAX. Child of fixed #4226; its original acceptance continues at
the unchanged parent head. Coordination: #4135, claim 6695198628.

## Observed

Read the governing agent contract, succession handover and engineering
playbook. Traced `tools/run_source_closed_project_handoff.py::
_generate_project_handoff_locked` through the live collector into
`compose_live_physical_opening_voids`. The handoff unconditionally enables
`single_width_uniform_page_door_height_shadow`. That option collects heights
from other doors on a page, infers a missing door type using a width whitelist,
and creates area from the target width and the other door's height. Those
canonical areas are subsequently eligible for the existing quantity path.

## Inference

One door's owned height does not establish another door's height. Numeric
width conventions cannot establish a missing semantic type. An extraction
boolean is not a typed target-owned source or owner-approved record. Calling
this mode shadow does not prevent its use in the actual customer handoff.

## Proposed repair and expected abstentions

Remove automatic activation in the customer handoff. Keep the compatibility
parameter default False, but reject True at the composer boundary, and remove
the unsupported type/area promotion blocks. Preserve existing source-owned
schedule, figured-dimension and other independent height authorities. Keep
the target's missing height/area unresolved. Claude's typed owner-review work
is separate and is not altered.

Test the real composer with valid synthetic source/wall records and missing
height, and intercept the actual customer handoff's collector call to verify
that it never requests page-wide height inference. Existing source-owned
height/area positives must continue to pass.

## Benchmark observations excluded

No expected quantity, item, project, width range, standard height, source
identity map or scoring tolerance determines this change. Frozen V2, source
PDFs, 20,000 cap, 2.5-point snap, existing quantities and source-owned producer
contracts remain untouched. No new FIRM/customer quantity or score is claimed.

## Validation

- All three new composer/customer-handoff regressions fail before the repair.
- All 61 composer and handoff tests pass afterward; the broader existing
  opening/customer/append-only/ceiling-handoff suite passes 357 tests, with
  six optional/private-source skips. Skips establish no original acceptance.
- Local Python 3.12.14; core geometry/PDF dependencies pinned as in the repo.
- Frozen V2 integrity, provider/gold isolation, undefined-name and diff checks
  pass. Final-head Python 3.13/3.14 CI and protected original retention remain
  pending; no merge or source/customer success is claimed here.
