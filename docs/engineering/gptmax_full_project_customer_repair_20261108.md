# Full-project customer handoff repair

## Observed

On main `3f9bcb98`, `tools.run_source_closed_project_handoff` combines genuine
floor, finish, opening and ceiling family seals, but exports floor/opening
customer rows only in `floor_area` or bounded `core` mode. An `all` run therefore
cannot supply its exact mixed-family customer artifact. The owner role runner
also never verifies or combines actual customer artifacts. The private staging
wrapper globs family-only customer files, which would duplicate rows once a
whole-project file exists. Original run 42402258575 completed all ten processes;
Maryborough and 3Laurel sealed but failed customer staging. Lot16's second role
and all Q5446 roles returned no sealable result; those are separate source gates.

An additional observed inventory defect: the producer appends
`opening_metric_axes` but omits that key from `expected_by_family`. These axes
explicitly deny commercial projection and remain engineering-only.

## Change

Consume the existing floor/opening projectors and already verified finish and
ceiling family rows in `all` mode. Require the real combined seal/customer
verifier and exact IDs/counts before exporting a whole-project artifact. Preserve
source seals when an optional customer projection fails; report the exact stage
without changing original claim reason codes. Never turn engineering-only axes
into customer quantities or remove their explicit veto.

In the existing all-source-role runner, authenticate each role's canonical
customer artifact against its actual seal, then verify the combined union and
write one canonical aggregate customer file. Family-only files must not enter
that union. Missing roles, wrong sources, missing/duplicate/foreign rows and
unsupported commercial scope remain unverified. Record safe source failure
details so genuinely empty/unavailable production can be distinguished from
missing customer export; do not manufacture negative quantities or empty seals.

Trace: source bytes -> existing live physical claim -> existing family issuer
and source traces -> family seals -> existing customer projectors -> exact
combined seal/customer verifier -> canonical role aggregate. Physical, scale,
material, geometry and commercial authority are unchanged. Frozen truth,
evaluator, maps, tolerances and source PDFs are untouched. Source-positive
original replay, historical signed/customer retention and fixed-head Python
3.13/3.14 CI are required before release. No accuracy gain is inferred here.
