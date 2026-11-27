# Finish-bearing room faces need wall evidence on their edges (tasks C06/C08, 2026-11-28)

Architecture note before the change (AGENTS). Approved as a generic shadow by MAX 7225222738. Report only.

## Observed
- Wall candidates are made from any visible linework; their paint is not checked before a room face is formed from them.
- The layered ring builder already defines wall bands: paired strokes (1.2 to 8 pt apart, at least 8 pt long, 70% overlap,
  exactly one partner face, so three-line hatch is not a pair) and filled bars (1.2 to 14 pt thick, at least 8 pt long,
  aspect 4 or more). It applies them to black or dark paint only.
- A finish-bearing room face can therefore be outlined by thin drafting lines, white masks or equipment, none of which the
  builder treats as wall, and nothing says so.

## Inference
A face used to measure finishes needs, along every edge, either a wall band on the OUTER side of that edge or an
authenticated doorway closure. Colour must not decide (authentic grey walls exist). Paper-white paint draws nothing
visible. The owner's existing green-ink exclusion for wall geometry stays; no other colour rule is added.

## Built (shadow)
`pb_finish_face_wall_support_shadow.face_wall_support(polygon, drawings, closures=())`:
- ink near the face only, paper white and owner-excluded green ignored, one group per stroke colour; lines on the room side
  are ignored;
- lines closer together than the builder's 1.2 pt thinnest wall are one face drawn more than once; collinear pieces are
  joined and runs under the builder's 8 pt minimum dropped;
- along each horizontal or vertical edge, a stretch is supported when a face of one ink lies on the edge (within the
  builder's 0.8 pt face tolerance) with exactly one same-ink face 1.2 to 8 pt behind it (two or more is hatch), or a
  builder filled bar lies behind it, or a doorway closure given by the caller covers it;
- the first version reused the builder's whole-line pairing: it refused a whole long wall for one short line or equipment
  line nearby, so no stretch of the Freezer was supported;
- wall ends (MAX 7226267598): a stretch at a corner of the outline, still unsupported, counts only when a line of the
  same ink is drawn along ALL of it, it touches a supported wall or doorway closure, and it is no longer than that wall is
  thick there. A break in the middle of an edge, a dashed or half-drawn end, or an end in other ink does not count;
- the 8 pt pair limit stays. `wide_candidate` (MAX 7226267598) is a SEPARATE field that never counts as support: a bare
  stretch whose only same-ink partner is 8 to 14 pt behind, running with it along at least 70% of the edge, no further face
  one thickness on (hatch), and a drawn same-ink line across the whole band near an end (cap or corner return). Same-ink
  equipment drawn as a capped double outline would look the same, which is why it is only a candidate;
- CANDIDATE only when no edge has an unsupported stretch longer than 0.8 pt, else ABSTAINED. Never CORROBORATED.

It promotes, closes, removes and publishes nothing, and no live path imports it.

## Measured (originals, local, counts only)
- Maryborough sheet 7, the two floor-finish faces (Food Prep, Office): every edge unsupported, ABSTAINED.
- Same sheet, the builder's 171 candidate rings: 8 fully supported, 3 under 10% unsupported, 5 from 10 to 50%, 155 over
  (many are rows of identical fixture-sized outlines bounded by single lines).
- Real Office: the builder's existing default-off `door_jamb_returns` gives it its own ring (source-stroke doorway closure);
  every long edge is supported, the 5.2 pt jamb stub counts as a wall end, and a 2.2 pt step with no drawn geometry does not
  (0.6 pt is within tolerance), so it still abstains. WSH/DRY (without the option): 1% unsupported.
- Cross-sheet, `door_jamb_returns` off vs on (builder only): only two sheets change. It gains the Office (Maryborough
  171 to 178 candidate rings) but LOSES the WSH/DRY room, which merges into an open region; another set loses 4 rings that
  were over 50% unsupported. Not a safe global switch.
- Known misses on real rooms: Cold Room passes three sides, its fourth is a panel wall about 8.6 pt thick, above the
  builder's 8 pt pair limit; the Freezer has 8.4 to 8.6 pt sides (73% unsupported). Raising the limit to the builder's
  14 pt filled-wall limit, and counting jogs no longer than a wall as part of it, are separate decisions, not made.

## Required checks before any use
Synthetic: black and grey double-line rooms and filled-wall rooms supported; single crossing lines, white masks, green
double lines, three-line hatch, a mixed-ink pair, short ticks, a band on the room side, a single open side and undrawn, over-long, mid-wall or partly drawn ends are not; doorway closure; translation,
quarter turn, drawing order and segment splitting; determinism and no mutation. Originals: counts only, before any wiring.

## Must not influence
Any expected area, room list or quantity; no sheet-, project- or room-specific value. All thresholds are the builder's.
