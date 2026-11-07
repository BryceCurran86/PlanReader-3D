# Source-only ceiling origin survives copied record IDs

## Observed behavior and real quantity trace

Reviewed AGENTS.md, the engineering playbook, adopted W1-W10 topology and
measurement/firewall rules, CI, the three-agent handover, and the inherited
`publish_original_rcp_source_closed` -> `CrossViewCeilingFinishRecord` ->
`publish_cross_view_ceiling_quantities` path in #4222 at 72b970ce.

The original RCP route issues material evidence with a source-zone record ID
and `commercial_projection_allowed=False`. It has no independently measured
ceiling area. The constructor and quantity consumer veto promotion by the
record ID prefix and permission flag. A source-neutral reproduction through
the real quantity function shows that ordinary `dataclasses.replace` changing
both fields creates one FIRM ceiling from the existing room-area fixture.
This is a confirmed authority-transfer defect, not an original ceiling result.

## Inference

The producer's generic private record seal does not distinguish the legacy
material route from the original source-only route. A copied public ID must
not erase the latter's categorical material-only origin. A caller-side flag
also cannot provide the missing independent RCP metric ownership.

## Bounded repair

Retain the existing record type. Give source-zone records a distinct private
producer capability, retained by ordinary dataclass copies, and expose its
material-only meaning as a read-only computed property. The constructor
normalizes source-zone IDs to that capability and rejects permission changes
regardless of the copied ID. The quantity consumer checks the origin property
again, including after forced mutation of both public fields. Existing source
IDs, source geometry, values, signer/customer bodies and the legacy ceiling
route remain identical. This is an in-process authority contract, not a
security boundary against equal-privilege code stealing private capabilities.

## Required proof and expected abstentions

First demonstrate the copied-ID/flag negative failing at the real quantity
consumer. Check actual source-route record construction, benign ID copies,
forced public-field mutation, absent/source-only ceiling area, and the existing
legacy positive and source/customer suites. The source-only route must issue
no quantity. Preserve final fixed-head Python3.13/3.14 CI and original signed
retention gates before release; this MAX child must not overwrite Claude's
live fixed branch. No private PDF or original coordinates are committed.

## Benchmark separation

The frozen 120 items, all source hashes, tolerance/cap/snap, expected areas,
and project-specific prediction inputs are untouched. No score or quantity
gain is claimed by this rejection fix.

## Integration and local verification

The failing quantity-consumer regression returned one FIRM ceiling before the
fix. After it, 140 focused finish/quantity/source-closed/customer tests pass,
including the original producer method, benign copies, rekey-plus-flag attacks,
forced public-field mutation, and existing legacy positives. The original PDF
F07 consumer suites also pass (63 tests). The capability/property is not a new
source schema and does not alter emitted legacy record IDs or quantities.

MAX's combined candidate starts from Claude's 72b970ce source result and this
fix, incorporates current main 0cc74650 (including corrected #4218), and retains
the reviewed #4220 native tuple allocation and #4221 worker lifecycle patches.
These last two affect source ingestion/runtime, not material or measurement
authority. The original source-only comparison at #4220 retained all 427,242
native observation IDs over all 31 Maryborough pages; one local process peak
was 95MiB lower than main. The next complete visibility ingestion also passed
below 1.5GiB. Neither result proves the whole role's previous 6GiB failure fixed.

The combined tree needs a single pinned source-private role attempt under the
existing budget, protected original F07 and historical sealed/customer replay,
and final Python3.13/3.14 CI. No incomplete parent test, historical source-only
positive or synthetic area is a release grant. Keep the candidate draft until
the actual gates complete; preserve the upstream branches and their history.
