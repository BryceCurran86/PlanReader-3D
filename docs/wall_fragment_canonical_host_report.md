# Wall fragments -> canonical host (Defect 3): diagnosis and the one change made

Status: **Draft, shadow-neutral, needs an authority-promotion review before merge.** Official
scores are unchanged; this document makes no accuracy claim.

Scope: why legitimate fragments of one physical wall do not yield a usable canonical host, and
the smallest generic change that is defensible. Reproduce every number below with
`scripts/wall_host_canonical_census.py --pdf PLAN.pdf --page N` (public APIs only, read-only).

## 1. Observed repository behaviour

- W2 snaps endpoints (2.5 pt) and merges collinear runs (3 deg). W3 classifies junctions
  (L/T/X/ENDPOINT/AMBIGUOUS/NEAR_JUNCTION_REVIEW/UNRESOLVED). W4 emits wall candidates that
  carry `junction_types` per end and the producer-owned `PhysicalWallIdentity`.
- `resolve_physical_wall_equivalence` runs a candidacy gate first. A pair the gate excludes
  (orientation incompatible, no longitudinal overlap, scale-implausible) is *not an identity
  competitor* and carries **no relation**. Only gate-admitted pairs get SAME / DISTINCT /
  AMBIGUOUS. A pure-SAME component yields one representative; any AMBIGUOUS edge makes every
  member abstain.
- `OpeningHostFrameProducer._shared_host_frame` seals a whole-wall frame only when the wall's
  extent is proven. Every aligned candidate outside the component had to carry a positive
  DISTINCT relation; "no relation" returned `None` (`opening_host_frame_whole_wall_unproven`).
- Four unmodified development pages (census, 2026-10-04):

  | page | wall candidates | ambiguous | representatives | pairs considered / total |
  |---|---|---|---|---|
  | Lamu p41 | 661 | 502 (76%) | 159 | 5,747 / 218,130 |
  | Lamu p42 | 438 | 310 (71%) | 128 | 3,285 / 95,703 |
  | KSTVET p54 | 955 | 919 (96%) | 33 | 24,941 / 455,535 |
  | 3-Laurel p3 | 1,560 | 1,353 (87%) | 206 | 37,114 / 1,216,020 |

  Every one stops at `physical_wall_candidate_scope_bounds_unresolved` (viewport bounds), so
  no opening is host-bound and no frame is built (`opening_host_frame_host_unavailable`).
- Diagnostic only, not committed: with the viewport bound bypassed, bindings stay 1/5
  (Lamu p41), 1/21 (Lamu p42), 0/9 (KSTVET p54); every frame still abstains.

## 2. Inference

Three separable blockers, only one of which belongs to this lane's host/frame code:

1. **Viewport bounds** (upstream, GPT / #989 lane) - nothing downstream runs on real pages.
2. **Equivalence ambiguity** - dominated by far-parallel pairs the gate admits only because no
   verified scale is available, and by unpaired double-line faces. A verified scale would
   exclude 85-95% of the admitted pairs but would not pair the faces. Angle tolerance changes
   (Copilot's proposal) do not move these counts.
3. **Frame strictness** - an aligned remote fragment with no relation vetoed the whole-wall
   frame even when a wall corner proves it cannot be part of that wall. This is the one defect
   with a local, defensible fix.

## 3. Change made

`pb_opening_host_frame_authority.py` only. An aligned candidate with *no* relation to a
component member may now be excluded when **all** hold:

1. the pair is positively non-competing - the equivalence candidacy gate
   (`physical_wall_pair_identity_candidacy`, same producer-owned `verified_points_per_mm`) is
   replayed and explicitly excludes it, and both identities are usable;
2. the candidate lies entirely beyond a face end that is **closed** - every component member
   reaching that extreme ends there in a W3 `L_CORNER`, so the run turns and cannot continue
   along the line;
3. the candidate is on a selected wall face (existing aligned test, unchanged).

Everything else is unchanged and stays fail-closed: open ends, T/X/ENDPOINT/AMBIGUOUS/UNRESOLVED
ends, a fragment inside the extent, a gate-admitted pair, a recorded SAME or AMBIGUOUS relation,
an unusable identity. No new scale, angle, gap or distance threshold was introduced; the proof
reuses the gate and `_COORD_TOL`. Fragment provenance is untouched: the frame still lists every
member wall candidate id.

## 4. Deliberately not changed

- Snap 2.5 pt / collinear 3 deg / near-miss band: measured no effect on real pages.
- The shared-source-face layer gate and the overlap rule in the trusted-relation overrides:
  they are what keeps unrelated parallel walls apart; relaxing them is a merge-risk change.
- Equivalence itself, `compose_live_canonical_walls`, gross-wall geometry composition, quantity
  authorities: untouched. `takeoff_eligible`, `deduction_authority` and W10 are untouched.
- No second resolver, vocabulary or schema was added.

## 5. Authority and customer-output effect

- Raises authority? **Possibly, at the frame seam.** It can turn
  `opening_host_frame_whole_wall_unproven` (ABSTAIN) into a sealed whole-wall frame. A sealed
  frame feeds canonical-wall composition, so this needs an authority-promotion review by GPT Max;
  CI alone does not count.
- Measured footprint today: **none**. Frames on the four development pages are unchanged
  before/after (census above); they fail on blockers 1 and 2, not on this one.
- Shadow proof: the new tests assert that no authority input is mutated and that replay is
  deterministic with stable ids; existing authority suites for frame, binding, equivalence,
  composition and gross geometry pass unchanged.

## 6. Tests

`tests/test_opening_host_frame_closed_wall_remote_fragments.py` (20): synthetic positive
(closed building, remote aligned fragments both as faces and as a single line); look-alike
negatives (open both ends, open at one end with the fragment beyond it, no remote fragment,
recorded AMBIGUOUS relation); metamorphic (translation, 90/180/270 rotation, uniform scale,
input order and primitive direction, unrelated-content / larger page); deterministic replay;
unit tests for corner closure, per-face closure, gate-exclusion and "no new threshold".
Against the original code 15 of the 20 fail (the 5 that pass both ways are the fail-closed and
invariance checks that must not regress).

## 7. Benchmark observations that must not influence implementation

The census pages are development drawings used to find failure modes. No expected quantity,
gold, mapping, tolerance, file name, page number or project name is an input to the code, the
tests or the census script.

## 8. What would unlock real-page footprint (not done here)

1. Resolve the viewport bound upstream (open PRs; not this lane).
2. A verified page scale feeding the candidacy gate (existing scale authority, not a new one).
3. Double-line face pairing for the equivalence resolver (separate shadow workstream).
