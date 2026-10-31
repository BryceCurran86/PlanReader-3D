# Item 8: opening-occupancy separation witness for callout claimants (shadow, opt-in)

Status: implemented as a default-off shadow input; nothing here grants a physical opening, host, kind, frame,
scale, metric, count, quantity or customer output. Written under `AGENTS.md` and the 2026-10-24 owner policy
(independent review optional; checks, original-source evidence and retention mandatory). It builds on the merged
#3869 callout shadow (MAX's exclusion model) and #3912 structural assessment, and preserves MAX's finding that
neither distance, a lettered tag, an intervening line, nearest-object choice nor expected identity separates a rival.

## 1. Observed repository behavior

- `audit_plan_callout_to_glazing_strip_from_source` -> `_ring_for_word` / `_native_curve_exclusions` ->
  claimants found by LOCATION ONLY (`_position`, `_box_can_oppose_strip`: a ring or envelope that fits the strip's
  along-extent and lies on one side) -> `_decide` step 8: any trusted rival is CONFLICT, any uncertain one ABSTAINED.
  A door bubble hundreds of points from a window strip is therefore a rival whenever its box projects into the
  strip's extent.
- The repository already has an authenticated tag-to-opening relation:
  `pb_schedule_opening_instance_binding_authority._opening_aperture` builds the jamb-bounded aperture from an
  opening's own source observations and `_aperture_contains_bbox` ("plan tags must be inside the actual
  jamb-bounded opening aperture") tests a tag box centre against both the along range and the face-band normal range.
  The callout shadow never consults it.
- `PhysicalOpeningAuthority.prove_existence` is per observation. A member shared with a rival candidate is
  `ambiguous_physical_opening_candidates` while an unshared member of the same candidate can be CORROBORATED, so one
  member's corroboration is not the candidate's.
- Original SHA `b1be5353...e007`, p7 (read-only): W02 and W05 are CONFLICT; every trusted rival is a door bubble;
  the six window hexagons lie in no candidate aperture.

## 2. Inference (labelled)

A callout symbol anchored inside the jamb-bounded aperture of exactly one corroborated opening, and inside no other
candidate's aperture, is positively accounted for by that opening, so its location fit to a strip elsewhere is not a
competing claim. This is a drafting-convention inference, not proof: a type mark may in principle label several
instances (standing limit `tag_type_vs_instance_unproved`) and the occupancy is a location fact, not kind, host or
identity (`occupancy_is_location_not_kind_host_or_identity`). It can only move a claimant from "rival" to "separated,
retained with its witness", so it is the non-conservative direction and is kept opt-in and shadow-only.
An occupancy also inherits every error of the producer's existence proof (standing limit
`occupancy_inherits_physical_opening_existence_authority_errors`): a corroborated aperture that is not a real opening,
for example an internal glazing subdivision gap, would be a false witness until that authority vetoes it, at which
point the witness disappears with it because it is re-derived from the producer's own proofs on every run.

## 3. Proposed change (as built)

1. `pb_plan_tag_opening_occupancy_shadow.py` (default-off, strict-bool enabled): on the producer's own independent
   replay (`fork_native_source_shadow`) it enumerates the page candidates through the existing read-only accessor,
   builds each aperture with the binder's helper, and for every named anchor tests EVERY candidate (no ranking,
   no distance, no letter test). An anchor is occupied only when exactly one candidate contains it and every member of
   that candidate is CORROBORATED with one identical record whose observation set equals the candidate's and whose own
   aperture still contains the anchor. Contested, uncorroborated, mismatched or uncontained anchors stay rivals with a
   typed diagnostic. A candidate whose aperture cannot be built, or a published observation that fails
   authentication, abstains the whole inventory.
2. The callout shadow takes `ClaimantOccupancy` records as an optional scope input (ownership checked, empty means "not
   evaluated"). A claimant entry (six-edge ring, envelope exclusion, unresolved word) is separated only when its own
   box centre lies in the occupied aperture, the occupied opening shares no ink with the strip and its aperture does
   not touch the strip's box. Separated claimants stay on the record (`separated_claimants`, count in `numbers`) and a
   CANDIDATE that relied on a separation carries `callout_rivals_separated_by_opening_occupancy`. A callout whose own
   tag occupies a different opening abstains (`callout_tag_occupies_other_opening`). An untrusted word is never separated.
3. `audit_plan_callout_to_glazing_strip_from_source(..., claimant_occupancy=False)` (explicit bool): the default is
   byte-identical; True runs a second pass with the census. The local census tool gains `--claimant-occupancy`.

## 4. Expected abstentions

An anchor in no aperture, in several, in one that is not fully corroborated, or whose record differs from its
candidate stays a rival. Exclusion-only claimants with untrusted labels, undecidable rings and any claimant whose
aperture touches the strip stay uncertain. If the census cannot be produced the result carries
`claimant_occupancy_unavailable` and separates nothing.

## 5. Benchmark observations that must not influence implementation

Maryborough matched items remain 0/24. No expected quantity, count, tolerance, object mapping or tag list enters
selection, thresholds or tests; the only tolerance is the binder's own containment tolerance, mirrored and pinned by a
parity test. Which original claimants end up separated is an observation, not a target.
