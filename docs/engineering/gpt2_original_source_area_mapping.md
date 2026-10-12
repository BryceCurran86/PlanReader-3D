# SourceRoomArea producer-local result ownership protection

GPT2 issue [#2009](https://github.com/BryceCurran86/PlanReader-3D/issues/2009), source-backed property correctness for [GPT1 #2017](https://github.com/BryceCurran86/PlanReader-3D/issues/2017) and [GPT3 #2014](https://github.com/BryceCurran86/PlanReader-3D/issues/2014).

Both `CrossViewRoomAreaResult.evidence_by_source_room_face_record_id` and
`SameViewRoomAreaResult.evidence_by_source_room_face_record_id` previously
constructed a plain `{source_face_receipt: original_area_evidence}`
comprehension. The cross-view `evidence_by_physical_room_id` property had
the same last-write-wins problem. When original source records contain two
competing source-room-face receipts, two different faces claiming one
`physical_room_id`, or one reused original figured area
`EvidenceAtom.evidence_id`, a dictionary comprehension can silently turn
ambiguity into a FIRM metric area. The source-area collector consumes these
properties before its area bridge; later output guards cannot revive
source certainty if an early helper already overwrote a competitor.

The new `unique_source_room_area_evidence_by` indexes only exact
`CrossViewRoomAreaRecord` or `SameViewRoomAreaRecord` producer-sealed
records from the correct result type; an invalid record type fails closed.
It validates original typed/trimmed IDs and refuses every competing
source-face, physical-room and figured-area evidence receipt, preserving
valid independent rooms regardless of iteration order. Incomplete
competing records with a valid original source face/physical ID still poison
that identity; an entirely unrelated malformed address cannot suppress a
different authentic room. It preserves separate same-view/cross-view
producer scope and downstream cross-view priority rather than combining
conflicting views here.

This is **production source-authority protection**, not area recovery.
No label, polygon, viewport, scale, quantity, commercial finish or ceiling
is inferred. The original Maryborough 31-page PDF SHA is
`b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`.
Original source PDF CI requires the independent previously established
Food Prep **13.270425 m²** (`qty_be2a3b3108220d48f6f5`),
Cold Room **25.37875 m²** (`qty_9795d69439e85c35b01c`),
Office **9.05352 m²** (`qty_29e71bd466a9e5fa1783`) to remain FIRM
documented **room areas** under production page 7 geometry and page 11
source support, after this defensive change. Those test controls are
not injected into a producer, not floor material mappings, and not frozen
scoring truth.

DRY STORE remains ABSTAIN. Missing authenticated split-faced rooms
and unscaled surfaces remain unavailable. Frozen Full Plan V2 truth,
evaluator, object universe, 24+27 denominators, tolerances and the
20,000 original source-primitive safety cap are untouched.
