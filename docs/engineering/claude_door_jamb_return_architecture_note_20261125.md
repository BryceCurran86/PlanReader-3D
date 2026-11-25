# Short door-jamb returns in the dark-painted layered ring (25 November 2026)

Default off (`door_jamb_returns`). Stacked on #4683, which is held (#4135 comment 7156845089). Claim: #4135 comment 7158215641.

## 1. Observed

- The short wall between a door and the next wall is often never collected. The merged-face collector needs 40 pt. The
  stroke-pair collector needs 8 pt and exactly one partner face line, and extra lines 0.5 to 1 pt outside a wall give a face
  two partners. The doorway then has no wall gap, so nothing can close it.
- On the original that showed it (counts only): beside three doors such pieces are about 33 pt on one side and 5.5 to 5.8 pt
  on the other; two more are 5.8 and 7.4 pt; the walls are 6.5 pt thick.
- Two of those doorways closed on main only because the open leaf, drawn in line with the frame strokes, together made a
  40 pt line. #4683 hides the leaf (correctly) and the jamb goes with it.
- Each affected doorway has one segmented-swing witness, whose closed chord says where the wall starts. The jamb is drawn
  as a small frame at the chord end, cross strokes at it, and both wall faces running from it to a wall of the other direction.

## 2. Inference

The missing evidence is not a lower minimum length. It is the door's own jamb.

## 3. The rule

For each segmented-swing witness and each end of its closed chord, one strip is made only when all hold:

| | Condition | Reused limit |
|---|---|---|
| E1 | The chord is axis-aligned | the chord proposer's 0.12 pt |
| E2 | Black visible face lines start at that end and run away from the door: one on the chord line, and exactly one other 1.2 to 8 pt from it with a black cross stroke at the end between the two, on one of them | the proposer's 0.18 pt and 1.0 pt run; wall thickness 1.2 to 8 pt |
| E3 | Both faces run on without a break; the piece ends where the shorter one stops | 0.18 pt |
| E4 | A strip already collected in the other direction touches that far end | face-cluster 0.8 pt |
| E5 | The piece is shorter than the merged-face minimum | 40 pt |

The band spans the face lines actually read; the strip runs along the chord and keeps the face and cross-stroke path ids.
Zero or several candidate second faces abstain; nothing is chosen by nearness. Every witness's own arc and leaf are door
symbol ink and are never read. No new threshold, label, tag, page number or position.

**Authority.** Topology candidate ink, like the other collectors. It authenticates no wall, closes no doorway by itself and
issues no quantity. A room record still needs exactly one figured pair. Off by default; not wired into any consumer.

## 4. Expected abstentions (written before the tests)

No axis-aligned chord; no cross stroke at the end; zero or two second faces; thickness outside 1.2 to 8 pt; faces that stop
at the frame; nothing of the other direction at the far end; a piece of 40 pt or more; a chord that is not on a face line.

## 5. As built

`pb_layered_wall_doorway_room_ring_shadow.py`: `_jamb_return_extent`, `_collect_door_jamb_return_strips`, and a default-False
explicit-bool keyword `door_jamb_returns` (requires `dark_painted_wall_source`) on `build_layered_wall_doorway_room_rings`
and `build_from_pdf_bytes`. The helper runs after every other collector, so E4 sees their strips. One change from the
proposal: the band comes from the drawn faces, because a witness chord can sit up to the leaf tolerance off the face line.

Tests `tests/test_layered_door_jamb_returns_v1.py` are synthetic and follow the drafting convention above. They cover both
pieces under translation, axis swap and both mirrors; the door closing and the room behind it becoming a candidate; split
face strokes, input order, unrelated content, a repeated witness, another door's strokes; every look-alike in section 4 plus
grey, invisible and filled ink, a tick, a line into the doorway, a face off the chord, a diagonal chord; no mutation and
deterministic replay; the switch's validation and forwarding. 47 of 49 single-line mutants are killed; the two survivors are
equivalent changes (the run direction is already fixed by how near and far ends are picked; a zero length cannot occur
because both faces run more than 1 pt from the end). Scale invariance is not claimed: the reused limits are paper-space.

## 6. Measured on originals (local, counts only)

- **Keyword off:** whole-result digests identical to the base (#4683 head `2003868ca`) on 41 of 41 runs: 17 pages of 10
  documents, in the dark-painted, default, and dark-painted plus sliding-leaf and wall-end configurations.
- **Keyword on** (both dark-painted configurations): only the two pages with usable jambs change.
  - The A110 plan: 13 pieces, all real wall by eye. Closures 23 to 35 with none lost. The nine doorways looked at go from
    5 to 9 shut. Candidate rings 171 to 178: four rooms (three WC and shower rooms and the Office; PWD was already one) and
    three thin wall cavities now closed at their ends. Two rooms (M-AMB, F-AMB) stay merged. The room-face scope records
    nothing with the keyword off or on (13 figured dimensions; no candidate has exactly one matching pair).
  - One public sample page: 4 pieces (a pier between two doors and short returns, all real by eye); closures unchanged;
    candidate rings 106 to 102 (sliver rings inside those pieces) in the dark-painted configuration, unchanged with
    sliding-leaf and wall-end.
  - Four other sheets of the same set carry door witnesses but yield no piece, and every page without one: identical.
- **Regression:** the 74 test files that reference the module or one of its production importers, plus the #4683 and new
  test files, local originals provisioned: #4683 head 9 failed, 1,378 passed; this branch 9 failed, 1,449 passed. The same
  nine tests fail on both (local-original tests on Banksia, 3Laurel and the Maryborough office and PWD customer chains); the
  71 extra passes are the new tests.

## 7. Not solved

- With the keyword off this branch behaves as #4683 does, including its lost doorways. A successor that replaces #4683 has
  to decide whether the returns are on whenever the door-stroke exclusion is.
- On one enlarged sheet a doorway that #4683 loses has a wall 12.7 pt thick, above the 8 pt limit, and stays lost. A later
  option is to let a cap spanning both faces set the thickness, with a guard against furniture; it needs its own
  look-alike tests.
- Doors drawn as true curves are out of scope.
- #4683 and #4694 stay held until this is reviewed and that sheet's doorway is decided.

## 8. Observations that must not influence implementation

Door tags, room names, rooms read by eye, any sheet's counts or areas. No quantity, benchmark value or file name was used.
