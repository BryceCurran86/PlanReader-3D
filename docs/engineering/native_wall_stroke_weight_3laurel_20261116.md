# 3Laurel original source ink: dark/thick wall evidence

The original 3Laurel ground-floor source PDF (page index 2) has strongly
distinguishable native CAD ink families:

- `Enclosure_WallExternal` and `Enclosure_WallInternal` contain original
  dark **0.71 PDF-point single-line strokes**. The former contains genuine
  external wall face runs, the latter internal partition face runs.
- Many genuine physical walls are also black-filled geometric strips; a
  filled PDF path often has `width=0`, which is **not** absence of wall
  thickness. The occupied rectangle/polyline geometry carries thickness.
- Floor finish/annotation strokes typically have different **0.37-0.43pt**
  source widths and **must not** become physical walls. Some annotation
  strokes may be .75pt, so raw darkness/width without original source
  wall-family ownership is never sufficient.

The existing heavy-stroke collector used one universal >=1.2 PDFpt
cutoff. That supported other vector plan sources such as Q5446, but
excluded every original 3Laurel single .71pt heavy wall stroke from
that collector. The new source-role-specific gate accepts >=.65 PDFpt
**only** for named native wall layer rows, while leaving the existing
>=1.2 PDFpt rule for other drawing families unchanged. It retains
dark-neutral color, opacity, long axis alignment, original path IDs,
no inferred joins and no material/area/customer quantity authority.

## Original page diagnostic / regression proof

On the untouched original 3Laurel p3 native PDF:
- Previously: **0** single-heavy wall strokes accepted by this collector.
- Updated: **200** original dark source wall-face stroke candidates,
  retained with their native PDF path IDs.
- The original exterior opening detectors still find **16 windows,
  3 exterior hinged doors, 2 ASD sliders, 1 garage panel-lift = 6 doors**,
  and 2 neutral-grey source wall seams.
- The whole-building initial trace **still ABSTAINS** with
  `source_exterior_other_wall_ink_outside_candidate`; it does not
  invent a complete house polygon or approved customer measurement.
- Direct original page preflight timing in the same test environment:
  prior source heavy-width gate ~22.85 sec; updated ~20.25 sec.
  This is not an official performance benchmark or a guarantee of faster
  full 31-page Maryborough extraction.
- 108 focused Python3.13 tests passed covering wall graph/exterior
  endpoint/source preview and wall-source negatives. Public CI still
  needs an exact-head full run before merge.

## Correct next traversal

The already shipped `extract_planar_faces` generic algorithm uses
oriented half-edges and the clockwise predecessor at each junction.
The exterior source preflight, however, currently selects a closed
polygon from unioned wall bands. That can close the wrong left/alfresco
or porch component while genuine Bed5/Living/right-house and garage
wall ink lies outside it. Wall-stroke recovery alone will not fix the
wrong-loop selection.

The correct source-owned **inside-face** first pass must start on an
exterior wall whose room-facing side is proved, follow connected
native physical wall face segments with the consistently leftward
half-edge turn, use only already authenticated window/door threshold
bridges and real wall junctions, and accept closure **only when the
same directed starting edge is encountered again**. Reject dead ends,
unhosted gaps, premature smaller room cycles, right-house/garage
exclusion, outdoor ALFRESCO/PORCH, and isolated timber POST. It must
not turn an apparent .71pt annotation into structure, count painted
wall above a frame without source height, or publish quantities merely
because a topological loop closed.

This change contributes only wall-source candidates. It does not
claim that the original 3Laurel complete inside-facing exterior
footprint is yet source-authenticated.
