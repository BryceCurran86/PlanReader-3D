# Separate floor-plan geometry and RCP finish sources ? GPT1

## The actual source blocker addressed

Maryborough's floor plan (original PDF p7/index6) carries room boundaries
and dimension evidence. Its reflected ceiling plan (p9/index8) carries
material and height bubble evidence (GRID, IPF1, FPB, etc.). The earlier
\`building._measure_one\` required **all** room dimensions, source geometry,
room label, material code and height text to be on the **same PDF page**.
Thus even if Cursor authenticates both sheets independently the ceiling
area issuer could not consume the two.

The new **opt-in, draft-only** ceiling row accepts \`page_index\` for the
source-authenticated plan footprint and independent \`rcp_page_index\`
for its actual material/height evidence. It requires:

- Exact original PDF SHA shared across pages; two distinct page indexes.
- A source-drawn ceiling footprint on the plan page (original native
  rectangle or physically closed source polygon), explicitly reviewed
  \`boundary_basis: source_owned_ceiling_zone\`.
- Original dimension chain words for **both plan axes**, bound to the
  actual footprint geometry; no guessed scaled dimensions or ceiling area.
- Original plan room-label word genuinely inside the source polygon.
- Original RCP material word + printed height paired in **one source text
  bubble** inside one nonambiguous source-drawn RCP rectangle.
- \`rcp_cross_sheet_correspondence_reviewed: true\` and exact RCP rectangle
  ref plus optional RCP height word ref for disambiguation. Even after
  review, the result remains \`MEASURED_DRAFT_REVIEW_REQUIRED\`,
  commercial_publishable=false and benchmark_credit=false.

A valid selection includes in the ceiling row:
\`\`\`json
{
  "ceiling_id": "office-ceiling",
  "room_id": "office",
  "page_index": 6,
  "rectangle_ref": "<floor plan original rectangle ref>",
  "boundary_basis": "source_owned_ceiling_zone",
  "width_word_ref": "<actual plan horizontal dimension word>",
  "height_word_ref": "<actual plan vertical dimension word>",
  "room_label_word_ref": "<actual plan room word>",
  "rcp_page_index": 8,
  "rcp_source_rectangle_ref": "<original RCP native rectangle ref>",
  "finish_word_ref": "<RCP source material code word ref>",
  "rcp_height_word_ref": "<RCP original printed height word ref>",
  "rcp_cross_sheet_correspondence_reviewed": true
}
\`\`\`
Actual receipt values must be derived from the source, not invented as in
the placeholder example. The same source RCP rectangle cannot be assigned
to multiple ceiling area claims. The old single-page route is unchanged,
including the original row-ID hash/lineage. Both are create-only reviews.

Synthetic original-native three-page PDF tests demonstrate a separate
floor plan, door schedule, and ceiling RCP can produce **13.270425 m2
ceiling area at 2500 mm local RCP height** in a *review-only* takeoff,
while mismatching pages, dimensions, RCP words/rectangles, unreviewed
cross-sheet identity, duplicate ceiling zones and overwriting outputs
fail closed.

## Still not solved by this issuer change

Maryborough source-native floor plan currently has **zero physically
enclosed room regions**. This patch does **not** fabricate those polygons
or promote the 18 genuine RCP height/material receipts into 18 measured
ceiling zones. Cursor must source-close the physical rooms and bind the
corresponding real RCP material/height geometry before a Maryborough
production takeoff can use the review-only cross-sheet issuer.

The original PlanReader production pipeline, frozen 120 denominator and
signed quantities are not changed. No private original PDFs are committed.


## Source paint correction (12 November)

A closed native PDF rectangle operation is NOT always a visible outline.
Maryborough A120 path 141 is white fill-only masking/background paint;
its bbox is not a wall, ceiling border or measured ceiling zone. The
cross-sheet RCP rectangle witness now requires original source paint
to show a visible stroked outline. A reviewer cannot promote a white
fill to a ceiling-zone witness. Real ceiling-zone perimeters can instead
follow several original visible wall/transition line segments.
No ceiling quantities are issued from WHITE mask rectangles alone:
they remain source layout hints until separately corroborated by
visible dark wall/floor/ceiling transition ink and exact dimensions.


### Owner correction: A120 layout-mask rectangles remain useful as SEEDS

The owner reviewed the 13 outlined layout-mask bounding boxes on the
actual A120 original. The principal mistakes were rectangle 1's
bottom-left junction where rectangle 3's line crosses the real wall
and a falsely extended line through Sales. We should not discard
the remaining mask layout hints just because native PDF paint type is
white fill-only. However a fill-only bbox does NOT have a drawn
outline and cannot by itself authenticate a measured ceiling boundary.

rcp_mask_wall_witnesses preserves the 13 original white fill-mask
layout seeds in an opt-in separate review packet, checks each side
against independently painted dark original wall strips and reports
unsupported spans and source wall IDs. In the original A120 native
coordinates the rectangle-1/3 mask overlap is
[571.2, 1556.96, 693.6, 1584.56]; original real dark wall rect:p73:i0
runs around source y1585..1590, supporting the stepped junction
instead of the straight white bbox edge. Rectangle-3 top-left bbox
edge lacks wall support over native x571.2..702.48; its real dark
wall step is about 28.08 PDF points away. The large FPB mask
rect:p141:i0 contains the fake line into Sales: its y_max=1376.72
edge has wall ink over only source x279.84..694.08, while
x694.08..1217.04 is UNSUPPORTED. Do NOT create a wall through Sales.

Thus propose_rcp_source_zone_rectangles in strict-stroked mode still
returns 0 confirmed visibly stroked rectangle outlines; the opt-in
mask layout witness mode returns 13 helpful ceiling layout hints
with independent wall evidence and unresolved edges. Neither counts
as measured ceiling area or frozen120 customer output. Floor-plan room
ring closure is not a prerequisite for tracing source A120 ceiling zones.
