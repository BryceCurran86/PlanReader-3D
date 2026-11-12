# Maryborough A120 ? source dark-filled wall-bar geometry

## Why this exists

Maryborough's original reflected ceiling plan A120 (PDF page 9, index 8)
has dark PDF FILL-painted wall strips in addition to genuine stroked
lines. Cursor's initial RCP tracer found 13,939 stroked source lines
and 32 topology rings but **zero** of the 18 material+height bubbles
inside a usable ceiling zone. A stroked-lines-only trace cannot use
the independently visible dark wall strips that actually define
critical stopping boundaries.

GPT1 now provides a separate, noncommercial source-witness module:

    python -m planreader_next.rcp_dark_bar_source_faces --pdf ORIGINAL.pdf --page 8 --output NEW_PRIVATE_JSON

It reads the immutable original file and reports each dark, narrow,
source-owned FILL bar and its TWO actual painted long-edge geometries,
including its original PDF rect reference, source colour, stroke status,
bbox coordinates and exact endpoints. The strips remain CANDIDATE wall
witnesses, not reviewed inner finished wall faces.

A qualifying source bar must be:
- An actual original PDF-native filled RECT whose fill is dark
  (each normalized channel below 0.55), with known clipping.
- 2.0 to 14.0 PDF points thick, at least 20.0 points long.
- The correct native PDF path ID and actual source geometry. No
  extension or snapping to a white layout rectangle's edge.
- White background masks, unknown paint, short symbols or
  broad black furniture fields are excluded.

The code also records mask-side-to-dark-edge source correspondence
without inventing full perimeter lines. All results remain
physical_wall_identity_authenticated=false,
finished_wall_face_authenticated=false,
commercial_publishable=false and benchmark_credit=false.

### Original A120 proof

Pinned source SHA256:
b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007.

The strict dark-fill filter finds **45 original wall-bar candidates** and
**90 actual painted long-face candidate edges**. This is NOT 45
authenticated walls, nor 90 commercially measured wall faces.
Separately, A120 has 18 authentic material+height callouts and 13
white layout-mask hints, 7 of which have all four proposed mask edges
corroborated by at least one dark-wall strip within the test tolerance.
That is layout corroboration, not finished-ceiling zone geometry.

Owner-confirmed errors:
- Mask 1 (rect:p114:i0) / mask 3 (rect:p116:i0) overlap at native
  coordinates [571.2, 1556.96, 693.6, 1584.56]. A real dark wall
  rect:p73:i0 runs x558.24..702.48 at y1585.04..1590.32; the
  white mask 3 top bbox is NOT a drawn line across that wall.
  Actual source bar rect:p63:i0 continues from x702.48 to 1217.76
  at y1550.96..1556.24. This is a stepped boundary candidate.
- Broad FPB mask rect:p141:i0 has a fabricated continuation through
  Sales. The true dark wall rect:p56:i0 stops at native x694.08.
  The remainder x694.08..1217.04 has NO matching source dark wall
  and MUST NOT be extended as a structural/finish boundary.

No ceiling area or official frozen120 score is issued from this audit.
Cursor should use both source stroked lines and these dark-filled wall
bar source edges, then independently authenticate the actual geometry
and material/height relationship. Keep the original PDF out of Git.
