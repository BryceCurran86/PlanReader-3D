# 3Laurel floor outline vs. physical wall source correspondence — 16 Nov 2026

**Status: shadow diagnostic only. Not a commercial source issuer.**

The existing shared enclosure boolean in PR #4360 was accepting source
`Finish_Floor` polygon outlines (Media, Bed 2, Bed 3, Living) and a
`Annotation_General` box (Garage) as if those shapes proved four physical wall
faces. MAX must not use that boolean to authorise finished-floor, ceiling,
skirting or tiled-wall customer rows.

`pb_three_laurel_floor_wall_face_correspondence_shadow.py` makes that
misclassification inspectable without claiming to repair it:

- Read a *closed, filled, native* `Finish_Floor` polygon only as a candidate
  coordinate reference around a printed room label.
- On every candidate boundary edge, find native dark-painted
  `Enclosure_WallInternal` / `Enclosure_WallExternal` rectangle paths whose
  long-axis orientation and face position genuinely agree with that edge.
- Report the original path IDs, side directions, exact uncovered intervals,
  owner counts and the length supported by those original source wall fills.
- If the floor candidate is not closed or is missing, ABSTAIN. Ignore
  annotations, unknown layers, white floor fills and mismatched explicit
  viewports as physical wall owner receipts.
- **Always emit `physical_wall_authenticated=False`,
  `measurement_authorized=False`**. Geometry contact does not prove wall
  material or doorway closure. No new customer rows, no frozen120 score credit.

## Original 3Laurel source diagnostics (p3, source SHA validated locally)

| Room | Floor candidate path | Native wall fill support | Boundary with no direct physical fill support |
| --- | --- | --- | --- |
| Media | 97 | 308.1 / 412.7 PDF pt | 104.6 PDF pt |
| Bed 2 | 304 | 269.6 / 405.9 PDF pt | 136.3 PDF pt |
| Bed 3 | 269 | 270.7 / 405.9 PDF pt | 135.2 PDF pt |
| Living | 123 | 554.9 / 772.2 PDF pt | 217.3 PDF pt |
| Garage | no closed floor candidate | unknown | unknown |

These percentages are **NOT measurement accuracy or final enclosure proof**.
Unmatched portions can be real openings, segmented wall faces, concave floor
boundaries, structural returns or incomplete source evidence; they are not
permission to paint solid walls across a gap or bill floor finish outdoors.
The original private receipt JSON is stored ONLY on Bryce's PC:
`C:\Users\bryce\private_packets\gpt6_max_3laurel_floor_wall_receipts_20261116.json`.

## MAX handoff

1. For each unmatched span, require *the original page and viewport's*
   native hosted-opening or physically joined wall-face witness; report path
   IDs and evidence kind. Do not infer a doorway from a convenient gap.
2. Connect original source-filled physical face families to the typed wall
   graph and spatial-room ownership; use `Finish_Floor` strictly as finish
   intent / candidate location, not as structure.
3. Keep outdoor alfresco and porch outside the enclosed building footprint.
   Do not classify the isolated timber post as a wall or internal path 1030
   as a missing outer wall.
4. Only after authentic wall, threshold, schedule, scale and finish evidence
   is complete should the real customer issuer be re-enabled and its **full
   sealed customer-body parity** tested against independently verified
   originals. Never fix the 26 failing issuer tests by downgrading source
   checks or changing expected values to match unsupported quantities.

The code is deliberately generic and has no original PDF embedded in public
files or any per-room benchmark truth determining a commercial result.
