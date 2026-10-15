# GPT1 Q02/Q07 — Canonical ceiling source checksum admission

## Observed source/provenance defect

`pb_live_ceiling_area_quantity_publication._publish_one` correctly requires exact
canonical room, real 2-axis figured measurement or resolved scale record,
positive finite m², upstream shadow `ceiling_lining` receipt, source revision,
viewport and source metadata equality. It previously allowed **matching copied
non-SHA strings** in `canonical_ceiling.source_sha256` and
`quantity.metadata.source_sha256` to pass the independent FIRM reissue boundary.
The equality of two imported fields is not original source authority.

## Narrow generic correction

Reject canonical source SHA unless it is a typed 64-character hexadecimal
digest. Preserve existing exact metadata comparison and all other authority
gates. This check establishes only a **well-formed source identifier**: it
does not establish that the original PDF bytes match that digest, that a
ceiling finish exists, or that room geometry is metrically authenticated.
The independent producer source SHA, physical room ownership, figured two
axes/graphic bar, material occurrence and final customer gate remain
mandatory. No project names, data-specific dimensions or default scale.

Fixture negatives include matching forged, short, long, nonhex, padded,
bool/number source SHA receipts; no live FIRM area, wall or opening quantity
may result. Existing ordinary and case-insensitive uppercase hexadecimal
source receipt positives, scaled and figured quantity families remain
unchanged when all previous source gates are genuine.

The original 3Laurel p3 partial floor/surface replay is a source-integrity
control, not a claim that all 18 source pages or building ceilings were
surveyed. A count of zero **produced source quantities** does not imply that
the building contains zero ceilings. The Maryborough source FIRM measured
Food Prep, Office, Cold Room floors and eight accepted Lot16 opening areas
are not recalculated or touched. Frozen Full Plan V2 source, scorer, truth,
manifest, denominator, 20,000 input cap, W2 snap, customer projection and
quantity schemas unchanged.

## Review and completion

This is a **fail-closed canonical→quantity boundary fix**, not commercial
authority expansion. PR stays draft pending original-SHA source replay,
targeted positive/negative tests on Python 3.13 and 3.14, full CI,
independent lineage/authority review and relevant upstream owner handoffs.
No new customer quantity, official frozen match or score claimed.
