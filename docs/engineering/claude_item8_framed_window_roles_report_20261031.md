# Item 8: authenticating the roles of lines on a wall face (framed windows, stepped returns). ARCHITECTURE REPORT, NO CODE

Status: report only, written under `AGENTS.md` ("first deliverable on a new change"). It answers the exit GPT MAX set on
#4147 (review 5722472635): "authenticate the framed-window/stepped-return roles and competing physical identities".
It stops for review. Nothing here changes code, a quantity, a threshold or a benchmark file.

## 0. Compliance (what was actually read and traced)

- Read: `AGENTS.md`; `docs/AI_ENGINEERING_PLAYBOOK.md` sections 1, 4 to 8, 11 to 13; the opening levers in
  `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`; GPT MAX's two reviews and the owner decision on
  #4147.
- Functions traced (file, name): `pb_physical_opening_authority.py`: `_visible_structural_candidates` (native six-line
  rule, including the interior-stub test and the "boundary-anchored cap" comment), `_raster_frame_line_groups`,
  `_raster_wall_face_continues`, `_raster_double_continuous_face_gap`, the raster framed discovery loop
  (`RASTER_FRAMED_WALL_BAND_INTERRUPTION`), and my own `_merge_layered_structures`, `_shared_host_face`,
  `_seeded_ink_checks`, `prove_seeded_existence`. `pb_source_visibility_authority.py`: `native_unstroked_fill_evidence`,
  `native_dimension_cap_evidence`, `_native_dimension_source_proof_batch`.
- Authority boundaries crossed (playbook section 6): 1 primitive capture, 3 candidate geometry. Nothing reaches 4
  entity evidence, 5 measurement input, 6 QuantityEvidence or later.
- Files that stay untouched: `pb_planreader_pdf_extractor.py`, every `pb_*quantity*` and issuer module, W10,
  `benchmarks/frozen_holdout/**`, `documents/sources/*.pdf`, the 20,000 primitive cap, the 2.5 pt snap, every threshold.
- Expected abstentions (before any test): both Maryborough strips keep ABSTAINING until a role rule is approved; a drawing
  whose window symbol shares its paint block with the wall abstains; a candidate with a rival host layer abstains.

## 1. Observed repository behavior

1. **Native rule.** `_visible_structural_candidates` finds two faces interrupted at the same gap with a jamb at each end
   (six lines). A non-member line collinear with a face and strictly inside the gap is an "interior stub" and removes the
   candidate; a line anchored at a gap end is kept as a possible cap "for the producer-owned annotation opposition
   checks". There is no native pattern that expects frame lines inside the gap.
2. **Raster rule already has a framed pattern.** `RASTER_FRAMED_WALL_BAND_INTERRUPTION` needs at least two frame-line
   groups between the faces (`_RASTER_MIN_FRAME_LINES = 2`) and at least eight supporting observations, and it is vetoed
   when wall-face ink covers at least 0.8 of the gap on the endpoint rows (`_raster_wall_face_continues`,
   `raster_wall_face_ink_continues`). `_raster_double_continuous_face_gap` records that two painted tracks across a gap can
   be glazing/frame lines or a lintel, and that this negative "MUST NOT veto independently source-supported framed
   candidates".
3. **Producer roles are opposing candidate atoms.** `native_unstroked_fill_evidence` and `native_dimension_cap_evidence`
   re-authenticate the source bytes and receipts, read paint facts (path index, seqno, stroke, fill, opacity) and return
   `EvidenceAtom`s with status CANDIDATE and opposing polarity. No producer method supports existence.
4. **Playbook section 13.** Priority 1 is lossless vector provenance (path index, stroke, dash, layer, clip); priority 3 is
   typed negative evidence as opposing atoms on retained candidates; the joint hosted-opening graph is priority 4.
5. **My own #4147 code (a gap, found while tracing).** `prove_seeded_existence` drops a layer pair with an interior stub
   before merging and does not report it; only survivors reach `candidate`. That removes a plausible competing identity
   silently, which "retain all plausible candidates" forbids.
6. **Maryborough first strip, measured read-only on the SHA-verified original** (paint facts from the native page):
   - the nominated glazing strip is 38 single-line paths, painted as ONE contiguous block (38 distinct paint-order
     numbers inside a span of 40); the second strip is the same shape (38 lines, span 40) at another place in the order;
   - the strip's lines are 0.48 pt black, the same width and colour as the wall's own face pieces (the page has 6,832
     such lines); the wall face pieces and the stroked line that closes the outer layer's gap are in a different, earlier
     contiguous block;
   - the 482 thin 0.24 pt red lines on the page, including the ones that make the glazing layer pair fail the stub rule,
     are painted late (90% of them after paint-order 107,137, against a page maximum of about 109,700);
   - the lines across the outer face (one exactly the gap's extent, one running through) and the wall-weight returns
     anchored at the inner face's jambs are not covered by any later opaque fill (checked against every filled drawing on the
     page), so they are visible in the final render;
   - unstroked filled-rectangle edges at the gap's extent exist at very early paint order (underneath everything).

## 2. Inference (labelled, not proof)

- I1. The outer layer pair stays refused under the repository's own raster policy too: a stroked line covers the whole gap
  on the outer face, far above the 0.8 coverage that policy vetoes. Replacing my any-overlap rule with the raster
  coverage rule would not change the first strip's outcome on the outer pair.
- I2. **Paint style cannot authenticate the glazing role on this drawing**: strip ink and wall faces share one style. A
  rule such as "glazing is the thin red class" is contradicted by the measured strips (n = 2, weak but a counterexample).
- I3. **Paint order may.** A window symbol exported as one contiguous block that is not part of the wall's block is a
  provenance fact the producer can authenticate (seqno and path index are already read by the sibling methods). It is a
  hypothesis from two strips of one document, not a rule.
- I4. The outer-skin pair and the glazing pair are two competing readings of the host of the same window. The plan alone
  does not say which one the window belongs to, so both must be retained as rivals.

## 3. Proposed change (shadow only; each step stops for review)

- **S1. Provenance accessor (playbook priority 1).** A producer method that returns authenticated paint facts for named
  native observations (path index, seqno, kind, width, stroke, dashes, layer, fill, opacity), re-proved against the
  source bytes and receipts exactly as `native_unstroked_fill_evidence` does, reusing its page paint cache, raising on any
  integrity failure. It asserts no role.
- **S2. Shadow role comparator.** A shadow-only module that, for a seeded candidate, relates each face-collinear non-member
  line to (a) the candidate's own face pieces (same style, adjacent order, same drawing block), (b) the nominated strip ink
  (its block), (c) fill masks, and reports the relation as CANDIDATE `EvidenceAtom`s with explicit polarity. It also
  returns every stub-dropped and every closed layer pair as a rival host layer (this fixes observation 5). It never
  releases a veto and nothing consumes it.
- **S3. Population measurement before any rule.** Over every nominated strip that reaches a whole-aperture CANDIDATE, on
  both private originals, record how often face-collinear ink exists and its relation in S2. Success is decided in advance
  and without any expected quantity: a relation that holds in both documents, survives translation, rotation and scale,
  and separates window-block ink from wall-block ink. If none holds, the question stays ABSTAIN for good.
- **S4. Decision gate (MAX).** Only if S3 shows such a relation, MAX may define a release rule. It must keep the vetoed
  reading as a rival, require independent corroboration of the same physical opening (callout identity, elevation frame,
  whole-aperture reading), stay default-off and be replayed on a second source before any promotion review.
- **Stepped returns** (second strip) follow the same order: first a typed description of the stepped terminals (shadow),
  then a count of how many tagged strips have them, and only then a pattern proposal.

## 4. Benchmark observations that must not influence implementation

None were used. The two strips are development observations of a failure mode. No expected quantity, tolerance or score
was consulted, and the paint values above are descriptive: no threshold (including 0.8) is to be tuned to them.

## 5. Questions for the authority owner

1. May S1 and S2 proceed as shadow-only work?
2. Keep my stricter any-overlap face rule, or align it to the raster policy's 0.8 coverage rule? (I1 says the first strip
   does not change either way.)
3. Retain stub-dropped layer pairs as rivals in the seeded result (my recommendation)?
4. Which second source should S3 use besides Maryborough?
