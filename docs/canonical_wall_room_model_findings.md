# Canonical physical wall + room evidence model — findings (research, shadow-only)

Status: shadow research only. Nothing here is imported by
`assemble_wall_candidates`, `reconstruct_room_candidates`,
`collect_topology_from_segments`, or any authority/publication path. No
quantity is published. No commercial output changed.

## Architecture

```
native PDF primitives -> U1 lineage -> W2/W3 topology -> U2 supporting/
opposing evidence (canonical, PR #283) -> pb_canonical_wall_room_evidence_
model.resolve_wall_physical_evidence -> WallCandidate (existing W1 contract,
reused, NOT replaced) -> pb_canonical_wall_room_evidence_model.
reconstruct_room_candidates_from_credible_walls -> RoomCandidate (existing
W1 contract, reused, NOT replaced)
```

`WallCandidate`/`RoomCandidate` (`pb_wall_room_topology_contracts.py`)
already carry every field this phase needed — no parallel wall/room object
was created. `EvidenceAtom`/`EvidenceResolutionStatus`/`stable_contract_id`
(`pb_migration_contracts.py`) are U2's own canonical evidence language,
reused unchanged. No `SemanticClass`, no `EvidenceStrength`, no single-label
classifier, no Otsu wall classification.

## Independent evidence families (see module docstring for full detail)

1. `u2_physical_wall_linework` — U2's own solid-stroke atom.
2. `paired_wall_faces` — `pb_vector_geometry_v130.detect_wall_pairs`, reused
   unmodified (bug found and fixed during this phase: `detect_wall_pairs`
   returns NATIVE segment ids, not post-split Stage-A edge ids — matching
   had to go through U1 lineage, not `face_a_segment_ids` directly).
3. `valid_junction_behavior` — at least one end is a real junction (not a
   fully isolated, both-ends-dangling segment — see False-Strong Case below).
4. `native_layer_wall_support` — a U1 lineage source record's native layer
   name contains "wall".

Two families are explicitly deferred, not faked: `explicit_figured_dimension`
and `opening_interruption_continuity` (need `pb_figured_dimension_evidence`/
`pb_viewport_dimension_binding` and `pb_wall_room_topology_opening_host_
binding` wiring respectively — out of scope for this pass).

**Explicitly excluded from being a family, to avoid repeating #273's
circularity**: room participation (rooms consume resolved wall evidence
one-directionally; nothing feeds back), bare one-hop connectivity (already
required just to have a junction at all), length alone (never promotes by
itself, only gates which edges are eligible for other checks).

## A real design constraint found: CORROBORATED is coupled to thickness

`WallCandidate.__post_init__` already enforces "a PROVISIONAL measurement
authority can never back a CORROBORATED entity" — a pre-existing, correct
guard. Every wall this phase produces has `thickness_m=None`/
`thickness_authority=PROVISIONAL` (no stage before this one resolves real
thickness), so **no wall can legitimately reach the top-level `CORROBORATED`
status in this phase, even with maximal independent existence evidence** —
confirmed empirically: 0 walls reached top-level `CORROBORATED` across all
four real drawings tested. The true finding (existence is independently
corroborated) is preserved losslessly in `metadata["physical_evidence_
status"]` instead of being discarded or (wrongly) forcing the top-level
status past what the schema's own invariant allows.

## FALSE-STRONG CASE — confirmed via real-drawing census, not hidden

Initial census (Lamu, KSTVET) showed many identical-length, repeated
"existence-corroborated" walls at hatch-tick scale (Lamu: 3.6pt x8+
samples; KSTVET: 8.02pt x4+ samples). Root cause: `valid_junction_behavior`
originally required only "neither end is AMBIGUOUS/UNRESOLVED/etc.", which
a fully isolated segment (bare `ENDPOINT` at both ends, touching nothing
else in the drawing) trivially satisfied — combined with U2's own
near-universal solid-stroke support, two nearly-non-discriminating signals
were being counted as two independent confirmations.

**Fix applied** (first-principles, not fitted to these drawings' specific
measurements): `valid_junction_behavior` now requires at least one end to be
a REAL connection to something else; a segment with `ENDPOINT` at both ends
no longer qualifies (there is no junction there to validate, only its
absence). Locked in by `test_31_isolated_dangling_segment_does_not_get_
junction_family`.

**Measured real-world effect**: Lamu's existence-corroborated count dropped
77 → 39 (nearly half); Baghau (170), Dungicha (695), and KSTVET (58) were
unchanged (their corroborated walls were not driven by isolated dangling
segments in the first place — the fix did not blanket-suppress evidence).

**Honesty note — NOT fully resolved**: the fix only removes the
fully-isolated (both-ends-dangling) sub-case. Lamu's remaining
existence-corroborated samples still include repeated 3.6pt segments that
connect to something at exactly one end — plausibly still hatch-tick marks
touching a baseline stroke, not real walls. A length-based or
repetition-based signal would likely close this further; deliberately not
added in this pass to avoid layering a second ad-hoc threshold onto real
drawings without dedicated adversarial testing of ITS own failure modes,
matching this whole project's standing "no rushed patch" discipline. This
remains an open, documented limitation, not a claimed fix.

## Real-drawing census summary (region-scoped, matching prior sessions' established regions; full data in scripts/canonical_wall_room_census_output.json)

| Drawing | Stage-A edges | Wall hypotheses | Conflict | Candidate | Existence-corroborated (capped) | Rooms (conservative / firm / permissive) |
|---|---|---|---|---|---|---|
| Baghau | 1,922 | 670 | 300 | 370 | 170 | 12 / 3 / 160 |
| Lamu | 1,009 | 605 | 416 | 189 | 39 | 0 / 0 / 96 |
| Dungicha | 5,514 | 1,973 | 915 | 1,058 | 695 | 238 / 236 / 308 |
| KSTVET | 2,313 | 781 | 652 | 129 | 58 | 0 / 0 / 83 |

**Baghau mullions/hatch**: the hatch-tick field (documented solid, untagged
convention) largely lands in `conflict` or plain `candidate`, not
existence-corroborated — U2's own array-based opposing nominations (hatch/
grid) correctly engage on this population.

**KSTVET thin repeated geometry**: highest conflict fraction of the four
(652/781, 83%) — consistent with the documented "thin repeated geometry"
concern; conservative room reconstruction found zero rooms here (the
credible-only edge population was too fragmented to close any loop), while
permissive mode found 83 — a real, visible cost of the conservative default
worth keeping explicit rather than silently accepting the permissive count.

**Lamu known masonry runs**: after the junction-behavior fix, corroborated
count nearly halved; remaining cases are documented above as a genuine,
unresolved limitation, not claimed as fixed.

**Dungicha dense classroom partitions**: highest room count (238
conservative, 236 "firm") — plausible for a genuinely partition-dense
classroom block, but not independently verified polygon-by-polygon in this
pass; flagged for future stratified visual inspection rather than accepted
uncritically (per "never hide suspicious corroborated cases," a large,
unverified room count is itself worth naming, not just the individual
false-strong wall samples).

Two very long (~1,620-1,630pt) Dungicha chains landed in `conflict` despite
substantial supporting evidence — plausible explanation: a long external
wall run passing near Dungicha's own documented repeated-window-tick
convention, correctly triggering U2's regular-tick-array opposing
nomination somewhere along its span. Not deeply verified visually in this
pass; named as a stratified example for future review, not silently
resolved either way.

## Quantity-impact diagnostic (shadow only — no BOQ values used or compared)

| Quantity family | Status | Why |
|---|---|---|
| Wall length | PARTIAL | Centerline geometry exists per WallCandidate; no scale authority wired in this pass (`length_m` stays `None` throughout, by design — see module scope) |
| External/internal classification | BLOCKED | `interior_exterior` stays `"unresolved"` — no room-side/exterior-boundary reconciliation wired to wall existence evidence yet (RoomCandidate's own `exterior_boundary` flag exists but is not cross-fed back to `WallCandidate` in this pass) |
| DPC baseline eligibility | BLOCKED | Needs wall length + exterior classification, both PARTIAL/BLOCKED above |
| Gross wall-area eligibility | BLOCKED | Needs resolved thickness (PROVISIONAL throughout, by design) and wall length |
| Opening-host eligibility | PARTIAL | `pb_wall_room_topology_opening_host_binding` exists and is untouched/reusable; `opening_interruption_continuity` family explicitly deferred in this pass, not wired |
| Plaster/paint face eligibility | BLOCKED | Depends on gross wall-area (BLOCKED) |
| Room/slab boundary eligibility | PARTIAL | `RoomCandidate` polygons exist with wall provenance; conservative/permissive room sets both available, but not cross-validated against any independent boundary signal yet |

No BOQ expected value was used as an algorithm input anywhere in this pass.
No quantity was compared against gold to tune a threshold.

## Real-drawing performance note

Dungicha's region (5,133 raw / 5,514 Stage-A edges) took ~106-111s for the
full pipeline (splitter + junctions + wall assembly + evidence resolution +
room reconstruction) on the EXISTING O(n^2) splitter — #281's spatial-index
work was deliberately NOT depended on here per the standing instruction
("Do NOT depend on #281 unless purely optional performance support is
needed"). This is a real, measured cost of that choice, not hidden: a
future integration combining this module with #281 (once #281's own
padded-AABB correctness fix lands and is verified) would be expected to cut
this substantially, matching the speedups already measured there on the
same class of real drawings.
