# Accuracy Handoff Checkpoint: Murera Findings & Next Target

CURRENT BENCHMARK:
30/60 = 50.0%
0 hallucinations

MURERA WINDOWS:

* automated OCR is incomplete
* manual/source inspection currently supports approximately 10 legitimate window instances
* benchmark expects 12
* do NOT force 12
* genuine W-6 exists visually but currently has no valid defined commercial window type
* BOQ quantities must NOT establish physical-instance completeness

MURERA DOORS:
current forensic source ledger appears to be:

* 2 × D-1
* 3 × D-2

total = 5 physical doors

Source type evidence appears consistent with:

* D-1 = single flush door
* D-2 = steel casement door

THIS IS NOT YET A PUBLISHED PRODUCTION COUNT.

The next accuracy task is to make production independently derive the same physical door universe.

NEXT ACTIVE TARGET

When work resumes, Antigravity owns the accuracy lane.

PRIMARY TARGET:

Murera doors_complete

Required source chain:

raster source
→ physical door geometry
→ OCR/tag observation
→ authenticated D-1/D-2 type binding
→ physical-instance dedup
→ opening-universe completeness
→ commercial count

Do NOT count text labels alone.

Do NOT use BOQ quantities as physical counts.

Do NOT tune toward expected 5.

Freeze the source-derived count before benchmark comparison.

If production independently derives 5 with a complete evidence chain:

run the five-project canonical benchmark.

Target:

31/60 = 51.67% or better
0 regressions
0 hallucinations
