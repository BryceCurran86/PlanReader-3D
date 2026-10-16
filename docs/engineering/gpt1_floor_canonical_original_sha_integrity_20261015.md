# GPT1 Q01/Q07 — Require a real source SHA address on FIRM room and floor reissues

## Observed first failing admission

In `pb_live_floor_area_quantity_publication`, both
`publish_live_floor_area_quantities` and
`publish_live_canonical_room_area_quantities` compare canonical source
SHA fields to source quantity metadata by lowercased string equality. Before
this change the former could publish a pair with the same copied invalid
string; the latter could throw `AttributeError` if a replayed canonical
room SHA was not a string.

## Smallest fail-closed correction

A shared pure, typed predicate requires exactly 64 hexadecimal characters
from each canonical floor/room SHA before an upstream documented/scale-room
area may be reissued FIRM. It does NOT trust mere matching source metadata,
does NOT calculate the source SHA from original bytes (the producer must do
that independently), and does NOT add a competing room-area resolver.

A malformed SHA in a canonical room cannot take down valid independent
floor areas: the invalid room alone ABSTAINS. A malformed SHA in a floor
with matching copied metadata cannot create a new FIRM floor quantity.
Existing exact source-area numbers, valid 64-hex SHA case folding,
documented figured area without scaled polygons, source-face/canonical
ownership, duplicated physical-room quarantine and customer row parity are
unchanged.

## Authentic original source and regression checks

The existing GitHub `test-gpt2-source-room-handoff-integrity.yml` already
has both modified GPT1 files as pull request paths. On this PR it repeats
the exact original Maryborough 31-page source, source SHA
`b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`,
topology page index 6 and independent area-support page index 10,
then requires exact three original measured Food Prep/Office/Cold Room
areas, original source receipt IDs, three FIRM floor reissues, three
canonical-room reissues, three seals and three verified customer rows,
with all other rooms and finish/ceiling output still ABSTAIN. Python 3.13,
3.14 full CI and frozen Full Plan V2 integrity must also pass.

The original eight Lot16 opening-area quantities and no new ceilings or
wall-finish objects are unaffected (this module does not own them).
No original PDFs, benchmark gold/denominator/tolerances/evaluator,
global W2 snap, 20,000 input primitive cap, customer projection or
quantity family schema have been changed.

## Authority review

This is a **restrictive** canonical source→QuantityEvidence integrity
gate. A syntactically valid source digest cannot itself prove physical
construction identity, area scale, or exact PDF source; all existing
producer and original SHA contracts remain mandatory. No new score claim.
