# Item 8: seeded existence proof for a proposed whole opening (PROPOSAL, UNWIRED)

Status: a draft patch against `pb_physical_opening_authority.py`, stacked on the aperture correspondence (#4140).
Nothing calls it; it changes no existing result, status, record or quantity. It exists so that the authority's
owner can decide, on evidence, whether a caller may name the members of an opening at all. Written under
`AGENTS.md`; the authority-promotion review it needs is a separate decision.

## 1. Observed repository behavior

- `prove_existence(selector)` derives its candidates from its own memoised page universe. There is no point at
  which a structure proposed by another authority can be presented to it, and the producer-owned authority is
  designed so that callers cannot inject candidate sets.
- On the Maryborough original the unrestricted page universe gives the two window strips only fragments
  (`strip_fragments_only_no_whole_extent_candidate`): the existing enumerator reads the glazing frame lines and posts
  as faces and interruptions.
- Restricted to the members of a whole-extent reading from the aperture authority (terminal jambs and host faces), the
  same enumerator finds, for the first strip, two six-line structures with exactly the reading's two jamb stations
  that share a face line (two layers of one wall); for the second strip none (its terminals are stepped returns).
- A wall drawn in layers also double-counts today: each pair of layers is its own existence identity, and an
  observation shared by both layers is `ambiguous_physical_opening_candidates`.

## 2. Inference (labelled)

- Structures that have the same face direction, the same two jamb stations and a shared member line cannot be two
  openings side by side; they are layers of one.
- Restricting the universe hides evidence. The only sound way to restrict it is to apply the enumerator's own negative
  evidence to what was left out, and to make the caller name everything else inside the opening.

## 3. Proposed change (as built; pure additions, no existing line of logic touched)

- `_structure_frame`, `_merge_layered_structures` (layers of one gap merge into ONE candidate carrying
  `layered_faces_of_one_gap` only on a verified SHARED HOST FACE, see section 8; structures that share a jamb, a cap or
  nothing stay apart as rivals) and `_seeded_ink_checks`.
- `seeded_candidate_structures` (from #4140) now returns layered structures merged; still CANDIDATE or ABSTAINED
  only, no record, no memo.
- `prove_seeded_existence(selector, member_observation_ids, accounted_observation_ids=())`: the six-line predicates on
  the named members; each structure is first judged against the stubs the restricted universe left out, using the
  enumerator's own definition (a line collinear with one of its faces that lies strictly inside the gap; a line
  anchored at a jamb or running through the gap is not one) and is dropped if it has one; the survivors' layers are
  merged; more than one distinct opening is CONFLICT; wall-face ink that continues into the gap on any face is refused
  whatever the caller names (section 8); any other visible line inside the gap and between the outermost
  faces makes the proof abstain (unnamed it is unaccounted; named it is only the caller's assertion of a role, which
  cannot grant it, section 9); a structure set aside for a stub stays a typed rival (section 9); then the viewport-scope gate, the annotation and unstroked-fill
  opposition and the geometry identity that `prove_existence` applies, and the same record. For a plain opening it
  issues the identical record `prove_existence` issues (tested, plain and producer-owned authority, rotated and
  scaled).

## 4. Expected abstentions

No structure among the members; a member that is not a visible observation of the selector's page; a selector outside
the structure; two distinct openings; a stub inside the gap on every layer; wall-face ink continuing into the gap on any face (never excused by naming it); ink inside the gap, unnamed or named
only by the caller; a competing layer set aside for a stub; a viewport scope
that is not promotable; annotation or fill opposition; an unresolvable geometry identity.

## 5. Result on the SHA-verified Maryborough original (private, read-only)

**The result first posted for ab8087d4c (one CORROBORATED record for the first strip) is WITHDRAWN.** It came from the
defect the review of that head found: wall-face ink running from jamb to jamb was not counted against the opening.
With the corrected rules (section 8), on the same SHA-verified source and the same named members:

- First strip: `prove_seeded_existence` ABSTAINS (`wall_face_continues_inside_seeded_opening_gap`), with the caller
  naming nothing and with the caller naming the strip's ink, its discriminated posts and every unstroked admitted
  observation. The only structure that survives the enumerator's own stub rule is the outer layer pair, and it has four
  non-member lines on its faces across its gap: two STROKED wall-weight lines on the outer face (the same width and
  colour as the wall's own face pieces; one exactly the gap's extent, one running through it) and two UNSTROKED
  filled-rectangle edges at the gap's extent (one on each face; fill boundaries, painted early). The unstroked edges
  are not what blocks it: the two stroked lines alone are enough. The neighbouring layer pair, which holds the
  glazing, is dropped by the enumerator's own interior-stub rule (six lines on its inner face lie strictly inside its
  gap: five thin red frame lines and one fill edge), and black wall-weight lines anchored at its jambs continue its
  inner face into the gap.
- The two structures still merge in the accessor on real data: they share the same two face lines on one offset, lie on
  opposite sides of it and have the same gap, so the layered rule fires on the original for the right reason (and the
  seeded proof then drops the stub layer before merging, as before).
- Second strip: no structure (stepped-return terminals), ABSTAINED (`visible_wall_continuation_required`), unchanged.

Inference, not proof: on this source the outer skin is drawn closed across the window and the opening is in the
neighbouring layer, whose face carries window-frame linework. The existing six-line rule has no pattern for a framed
window, so an existence record does not follow from it for either strip. Fail-closed is the correct outcome under the
rule; nothing here is an accuracy gain.

## 6. Not proven / decisions for the owner of the authority

1. Whether a caller may name members at all: answered for development by the owner's conditional decision (members only
   when the producer resolves every one from the same authenticated snapshot and page, and the full visible inventory is
   checked for omitted opposition); promotion remains a separate review. Not wired.
2. A pattern for a FRAMED window (face lines interrupted, frame lines on one face) and for stepped-return terminals does
   not exist. Without producer-authenticated roles, jamb-to-jamb ink on a face cannot be told from window-frame linework,
   so the proof abstains on both original strips.
3. The layered rule is exercised on synthetic layered walls and fires on the original's two structures; no original
   opening has been proven through it.
4. Python 3.14 locally, the private signed-replay workflows, and any consumer.

## 7. Benchmark observations that must not influence implementation

None were used.

## 8. Response to the review of ab8087d4c and the owner's decision (2026-10-31)

Defects found by GPT MAX and reproduced as failing tests before any change (44 failures at ab8087d4c, all passing now):

1. **Layer equivalence.** `_merge_layered_structures` merged on any shared observation id, so a common jamb or cap
   collapsed two depth readings into one identity and the union-find chained the error. Now two structures merge only
   when (a) every identity field agrees (document, revision, source hash, snapshot, page, viewport, pattern), (b) the gap
   (both jamb stations) is the same, (c) exactly one face offset is common, the face lines on it are the very same lines
   in both, and (d) the two structures lie on opposite sides of it (`_shared_host_face`). The connected set must also be a
   clean stack across the wall, each layer starting where the previous one ends (`_is_stack_of_layers`); a connected set
   that is not one (for example two depth readings on the same side of a shared face, bridged by a third) is not merged
   at all and its structures stay as rivals, which the proof reports as CONFLICT.
2. **Solid face across the gap.** `_seeded_ink_checks` treated jamb-anchored and jamb-to-jamb ink on a face as
   not-a-stub, did not count it on the outer faces, and let the caller excuse a shared-face line by naming it, so a
   continuous three-face wall was CORROBORATED. Face ink that overlaps the gap and is not an interior stub (anchored,
   jamb to jamb, or several segments that together span it) is now its own negative on every face, outer or shared,
   and no naming excuses it. Only ink that is not on a wall face can be accounted for, and only by an observation the
   producer authenticated on this snapshot and page (an unknown id abstains).

Owner's acceptance criteria, where they stand: members are resolved by the producer from the authenticated snapshot and
page (unchanged, tested with foreign members); the full visible inventory is checked for omitted ink and the
annotation / unstroked-fill opposition is applied as `prove_existence` applies it (tested, white unstroked boundary
opposes, the same boundary drawn as stroked linework does not); a viewport scope that is not promotable stops the proof
(tested through the scope authority's contract); default off, nothing calls the proof, no quantity, issuer or count is
touched.

Standing limits: (i) the proof is deliberately STRICTER than `prove_existence` on face ink (the page proof keeps a
jamb-anchored line as a possible cap for the annotation checks); a plain opening with such ink is refused here and
issued there. (ii) Roles are not authenticated: the proof cannot tell window-frame linework on a face from wall, so it
abstains, which is why both original strips abstain. (iii) Layer stacks are exercised with up to three layers.

## 9. Response to the review of b76f92325 and the owner handoff 6543203174 (2026-10-31)

1. **Candidate retention (review 5722756785).** `prove_seeded_existence` used to drop a same-gap layer that carries an
   interior stub before the identity census. Every set-aside structure now stays in the answer as a typed opposing
   `EvidenceAtom` (existing vocabulary: kind `unknown`, status CANDIDATE, polarity opposing) naming the structure's lines,
   the stub lines and `role_status = unresolved_no_producer_authenticated_role`, in `opposing_evidence_atoms`. The reason
   `seeded_competing_layer_with_wall_face_stub_unresolved` is added to every refusal beside it, and the proof cannot
   return CORROBORATED while one exists. A set-aside layer is a competing reading, not a disproved one: nothing
   authenticates whether the stub is wall or frame linework.
2. **Caller naming cannot grant a role (owner handoff 6543203174).** Interior ink the caller names in
   `accounted_observation_ids` ends in `seeded_opening_ink_role_asserted_only_by_caller`, not in a record. The names must
   still be observations the producer authenticated on this snapshot and page (an unknown id abstains), but they are an
   assertion of what the caller knows about, not of what the lines are. Consequence, stated plainly: until a producer
   authenticates ink roles, the proof can issue a record only for an opening with NO interior ink, so it is inert for any
   real window. That is the fail-closed reading of the owner's rule, not a defect to route around.
3. **Source-neutral controls added:** poses (identity, scaled, rotated 90 and 180 degrees, mirrored), member order and
   repetition, replay, a face line beyond the gap (not a rival), foreign-snapshot members, a plain opening with glazing.
4. **Original (SHA-verified, private, read-only):** the first strip still ABSTAINS, now with both reasons
   (`wall_face_continues_inside_seeded_opening_gap`, `seeded_competing_layer_with_wall_face_stub_unresolved`) and one
   rival atom for the glazing layer pair; the second strip is unchanged (no structure).
5. **`compare_identity` (owner handoff 6543274611):** not touched here. Note for the narrow source-partition veto: a
   seeded record for merged layers and a page-level record for one of its layer pairs have overlapping
   `source_observation_ids` and different `record_id`s, so they would compare as DISTINCT today. Left to the authority
   owner to avoid overlapping edits.

## 10. `compare_identity`: shared source members are not distinctness (owner handoffs 6543274611, 6543894483, 6544665680)

**This is the one behaviour-changing patch in the PR** (every other change here is an addition; the sections above
describe an unwired method). It tightens an existing live method in the fail-closed direction only and therefore needs the
authority-promotion review before any merge.

- **Observed.** `compare_identity` returned CORROBORATED DISTINCT for any two same-scope existence records with unequal
  `record_id`, without reading their `source_observation_ids`. Layer records of one gap (and a seeded record versus a page
  record for one of its layers) share a face and an extent, so they were counted as two openings. MAX's #4148 separately
  vetoes only EQUAL rosters, so a proper partial overlap passed both.
- **Rule (`_source_member_partition`).** Records that share no observation stay DISTINCT. Records that share wall support
  but whose gaps do not overlap along the shared face axis (adjacent windows in one wall; every shared line is a face
  piece outside both gaps) stay DISTINCT. Records that share lines and overlap in extent are a CONFLICT
  (`physical_opening_identity_shared_members_overlapping_extent`). A shared jamb or cap, a shared line that enters a gap,
  a structure with no readable frame or a different face direction is ABSTAINED
  (`physical_opening_identity_shared_members_partition_unproven`). Raster records are partitioned by their own
  source-measured `aperture_bbox_pt`: boxes that overlap in area are a CONFLICT, boxes that do not are DISTINCT, a box on
  one side only is ABSTAINED. A record compared with itself is still SAME.
- **Tests, failing first** (`tests/test_physical_opening_identity_partition_v1.py`, 5 failing then passing; 20 tests):
  adjacent windows sharing support stay DISTINCT in five poses, in both authority modes and both argument orders; layer
  records of one gap are CONFLICT in five poses and both orders; a seeded record for merged layers overlaps the page record
  for one layer; disjoint and same-identity are unchanged; shared jamb, unreadable structure, fewer than six lines and the
  raster box rule at the unit level. The existing raster aperture identity test (separated apertures stay DISTINCT) caught
  a first version of the rule that ignored the raster box, which is why the box rule exists.
- **Not proven:** that no live consumer relies on DISTINCT for records that share lines in a way this rule now refuses
  (the consumer suites listed in the PR pass; no private source run exercises a shared-member pair), and the downstream
  #4148 behaviour, which is MAX-owned.

## 11. Producer-owned pairwise partition receipt for the composer (owner decision 6549912542, review 5725190625)

**Question from the composer's owner:** which producer output fields and record ownership are needed so that adjacent
openings that legitimately share wall-face support can be recovered, without silently discarding the overlap, turning
differing ids into DISTINCT, or passing a caller allowlist.

**Answer, as built (additive; unwired; `compare_identity` is now derived from the same derivation).**

- **Ownership.** `PhysicalOpeningAuthority.partition_receipt(left_selector, right_selector)` re-proves both existence
  records through the authority's own `prove_existence` and returns a `PhysicalOpeningPartitionReceipt`. The type is
  sealed: a caller cannot construct one (the seal is checked with `is`; a missing or wrong seal raises `TypeError`).
  `verify_partition_receipt(receipt, left, right)` is true only if the authority, re-proving the pair now, issues exactly
  that receipt, so a forged, stale, tampered or foreign-snapshot receipt does not verify. The composer should hold the
  two selectors it already has for the historical and the new opening and ask the authority; it should never accept a
  receipt, an id list or an allowlist from a caller.
- **Fields.** `receipt_id` (stable id of every other field); `status`; `partition` (`disjoint`, `partitioned`,
  `same_record`, `overlapping_extent`, `unproven`, `not_applicable`); `basis` (`no_shared_source_members`,
  `native_gap_intervals`, `raster_aperture_box`, `same_existence_record`); `reason_codes`; the two existence record ids;
  document, revision, source hash, snapshot and page; each side's viewport; each side's source observation ids and the
  shared ones; the compared extents (gap intervals along the shared face axis, or aperture boxes); and the producer
  method, version and generation of the left record. `grants_quantity` and `grants_firm_authority` are always False.
  `is_physically_distinct` is true only for CORROBORATED `disjoint` or `partitioned`.
- **Determinism.** The two sides are ordered by existence record id, so the receipt and its id are identical for either
  selector order and on replay. Where existence or scope is not proven the receipt is `not_applicable` and carries no ids.
- **What the composer may do with it (MAX-owned, not done here).** For a pair of siblings whose source members
  intersect, accept the pair as distinct only when `verify_partition_receipt` holds and `is_physically_distinct`; any
  other `partition` keeps the existing abstention. Shared members are never discarded: the receipt names them.
- **Tests, failing first** (`tests/test_physical_opening_partition_receipt_v1.py`, 20 tests; the first run failed at
  collection because the type did not exist): partitioned receipt for adjacent windows in five poses and both authority
  modes; order independence and replay; layers of one gap CONFLICT; disjoint and same-record cases; no partition for a
  pair without proven existence or in another snapshot; construction without the seal and with a wrong seal refused,
  forged and foreign receipts do not verify; no other result changes; the detail behind the verdict (basis and extents,
  raster box, shared jamb unproven).
- **Not proven.** No private source run exercises a shared-member pair, so the actual Lot16 a68/993 partition is not
  established; the composer integration and the downstream equal-roster veto are MAX-owned; the receipt covers pairs, not
  a roster-wide census.
