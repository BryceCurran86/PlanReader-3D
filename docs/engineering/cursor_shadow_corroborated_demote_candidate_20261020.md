# Cursor — shadow receipts must not mint CORROBORATED from caller counts

**2026-10-20 • Architecture-first. Shadow only. No FIRM.**

## Observed

Several just-landed shadow compilers set `EvidenceResolutionStatus.CORROBORATED` when a caller-supplied collection is non-empty (`total > 0` or `healthy > 0`), or when caller geometry passes a local numeric bound (cavity slider, freezer D17/EPX takeoff, glazing thermal match). Empty collections already ABSTAIN. Commercial flags stay False.

## Inference

A non-empty caller list is detection, not independently re-resolved source ownership. `CORROBORATED` is the vocabulary later seams may treat as measurement-ready. Shadow workstreams on main must remain `CANDIDATE` until a typed document/revision/SHA/snapshot/page owner is actually resolved.

## Proposed

Demote those success statuses from `CORROBORATED` to `CANDIDATE`. Keep `ABSTAINED` when there is nothing to evaluate. Do not change geometry algorithms, do not sign FIRM, do not use expected BOQ values.

## Benchmark observations that must not influence implementation

FREEZER / EPX / FT2 / FT3 expected areas and door counts are not inputs to this demotion.
