# Physical Scale Authority V1

**TEST-ONLY / EXPECTED-RED FOUNDATION / NOT FROZEN / DO NOT MERGE**

Base: `bb61a8dee24c71b12cffcbb19e8dd89965b6e4fe`.

This contract defines one proposition only:

> this exact source/page/viewport has this producer-authenticated physical unit mapping from native PDF points to millimetres.

It exists because a plain `ScaleCalibration` or `ViewportScaleBinding` is not, by itself, an authenticated source proposition. Both are ordinary constructible data objects. Physical Opening Void V2 must not accept caller-minted scale status, `px_per_m`, ratio text, fingerprints, or a prebuilt calibration as physical truth.

## Existing safe behavior

Current PlanReader already does two important things correctly:

1. `measurement_authority_for_page_scale()` keeps title-block-only scale PROVISIONAL, not FIRM.
2. `pb_viewport_scale_binding` classifies ordinary viewport scale text as TITLE_BLOCK and adds `scale_not_firm` rather than silently promoting nearby `1:100` text to FIRM.

Those rules must remain intact.

## Missing positive producer

At this base there is no producer-owned source-native graphic scale-bar authority or equivalent sealed exact-scope FIRM scale evidence producer. Therefore **no new positive PhysicalScaleAuthority should be fabricated in this workstream**.

A future positive route may be added only when an independently reviewed upstream producer can prove, for the exact document/revision/source SHA/snapshot/page/viewport:

- the scale evidence exists in authenticated source-native observations;
- the evidence semantics establish a physical scale (for example an actual graphic scale bar with authenticated labelled length and measured native span), not merely nearby ratio text;
- the resulting points-per-mm mapping is finite and strictly positive;
- competing in-scope scale evidence is completely enumerated and reconciled;
- contradictions fail closed;
- stale/wrong-page/wrong-revision evidence cannot be reused.

Audited human approval may be a separate route later, but an ordinary caller flag/string is not approval authority.

## Required public firewall

A future public `PhysicalScaleProducer.publish_scope()` must accept selectors/lineage only. It must not accept:

- `px_per_m`, `points_per_m`, `points_per_mm`, `mm_per_point`, conversion factor;
- ratio / denominator / `1:100` text;
- caller `ScaleCalibration` or `ViewportScaleBinding` objects;
- caller `is_verified`, status, FIRM flag, confidence, source type;
- caller completeness/count/hash/fingerprint;
- nearest/first/radius tie-breakers;
- caller graphic-scale-bar coordinates or labelled length.

Fingerprints may address an already authenticated record but never create authority.

## Required attacks

A future positive implementation must fail closed for:

- title-block-only scale;
- viewport text-only scale;
- caller-constructed `ScaleCalibration(is_verified=True, status='valid', ...)`;
- caller-constructed `ViewportScaleBinding(measurement_authority='firm', ...)`;
- caller ratio/denominator/conversion factor;
- inferred scale;
- missing revision/snapshot/page/viewport lineage;
- wrong page or stale revision;
- conflicting source scales;
- incomplete scale-evidence universe;
- non-finite/zero/negative mapping;
- source SHA mismatch;
- candidate fingerprint without authenticated source record.

Contradiction monotonicity applies: adding a contradictory in-scope scale observation can only preserve or weaken authority, never strengthen it.

## Freeze rule

This validator must remain NOT FROZEN until independent review confirms the contract and a real source-native positive scale producer/prerequisite exists. Do not create fake positive fixtures using caller `ScaleSourceReading`, manual flags, or synthetic FIRM dataclasses merely to make a test green.
