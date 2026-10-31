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

- `_structure_frame`, `_merge_layered_structures` (layered faces of one gap merge into ONE candidate carrying
  `layered_faces_of_one_gap`; structures that share nothing stay apart) and `_seeded_ink_checks`.
- `seeded_candidate_structures` (from #4140) now returns layered structures merged; still CANDIDATE or ABSTAINED
  only, no record, no memo.
- `prove_seeded_existence(selector, member_observation_ids, accounted_observation_ids=())`: the six-line predicates on
  the named members; each structure is first judged against the stubs the restricted universe left out, using the
  enumerator's own definition (a line collinear with one of its faces that lies strictly inside the gap; a line
  anchored at a jamb or running through the gap is not one) and is dropped if it has one; the survivors' layers are
  merged; more than one distinct opening is CONFLICT; any other visible line inside the gap and between the outermost
  faces must be named by the caller or the proof abstains; then the viewport-scope gate, the annotation and unstroked-fill
  opposition and the geometry identity that `prove_existence` applies, and the same record. For a plain opening it
  issues the identical record `prove_existence` issues (tested, plain and producer-owned authority, rotated and
  scaled).

## 4. Expected abstentions

No structure among the members; a member that is not a visible observation of the selector's page; a selector outside
the structure; two distinct openings; a stub inside the gap on every layer; unnamed ink inside the gap; a viewport scope
that is not promotable; annotation or fill opposition; an unresolvable geometry identity.

## 5. Result on the SHA-verified Maryborough original (private, read-only)

- First strip: `prove_seeded_existence` returns ONE `CORROBORATED` existence record whose structure is the plain
  six-line pair of faces at y 1946.48 and 1951.52 with its two jambs exactly at the reading's ends (843.6 and 1047.6).
  The layered rule did not apply: the second layer pair (faces at y 1951.52 and 1959.92) is dropped because six lines
  collinear with the 1959.92 face lie strictly inside its gap (post and mullion outlines), which is the enumerator's own
  reason to refuse it. Nothing is left unaccounted inside the gap of the surviving structure. Caveat: the glazing strip
  lies in the neighbouring layer (y 1952.96 to 1958.48), adjacent to this structure's faces and not inside them, so how
  a strip attaches to this record is a host-binding question, not answered here.
- Second strip: no structure, so ABSTAINED (`visible_wall_continuation_required`).

## 6. Not proven / decisions for the owner of the authority

1. Whether a caller may name members at all. This patch is the minimum evidence for that decision; it is not wired.
2. The layered-gap rule is exercised on synthetic layered walls only; on the original it merges two structures in the
   accessor but the proof drops one of them.
3. The second strip's stepped-return terminals have no pattern.
4. Python 3.14 locally, the private signed-replay workflows, and any consumer.

## 7. Benchmark observations that must not influence implementation

None were used.
