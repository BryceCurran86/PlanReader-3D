# Next engine ? dimension inventory to native face association (GPT1, 2026-11-12)

This is a **shadow-only** adapter for the existing PlanReader Next engine. It
does not edit the original PlanReader production app, replace the native PDF
parser, promote commercial quantities, or change the frozen 120-item benchmark.

## Contract

1. load_native_page(original_pdf, page_index) authenticates source bytes.
2. inventory_page_dimensions(page) registers figured millimetre words and
   uniquely source-owned dimension lines, hash stations and connector refs.
3. associate_dimension_inventory_to_native_faces(page, index, candidates)
   accepts only source-native face-segment references with an explicit
   claimed item kind (room_finished_face, wall_face, opening_frame, ceiling_edge).
4. An association requires ALL: same source SHA/page; exact source words;
   one unique source dimension line; unique endpoint hash stations; exact
   equality between dimension stations and the proposed native face's endpoints
   within existing source representation tolerance; 0.35?36 point separation
   between the dimension and source face; and distinct native connector ink
   bridging both dimension endpoints ALL THE WAY to that face.
5. If zero physical candidate faces match, or more than one item claims a
   dimension, or multiple figures claim one face, the association ABSTAINS.
   The result carries the original word/line/tick/connector/face refs.
6. Every association is SOURCE_GEOMETRY_MATCH_REVIEW_REQUIRED; physical
   item authority and finished lining face remain false, even if a candidate
   was labelled room_finished_face. No area, FIRM result, customer output or
   benchmark credit is issued.

Synthetic regression: one native rectangle with 3600 and 2400 mm lines
generates two source-connected shadow face associations. A nearby but
unconnected parallel face and a distant same-station face both abstain.
Two different item IDs claiming one face cause ambiguity.

Real original 3Laurel page 3, at the 2026-11-12 source revision: 230 inventoried
figures, five unique dimension-line geometries, ZERO matched native face
candidates under the exact source-connection gate. This is expected and does
not imply that the printed figures are wrong or that rooms lack dimensions.

## Next stage (Cursor / GPT1)

Cursor: recover exact source-native physical wall/finished-face paths and
their drawn dimension extension-line associations without guessing by
proximity; handle page rotation and non-exact CAD representation separately.
GPT1: consume verified face/host/schedule bindings in the existing quantity
issuer pipeline after independent source ownership and full reviewed dimensions.

The 870 cavity slider figure is NOT room height, schedules remain the
authority for doors, and open Kitchen/Living/Dining labels do not create walls.
The 20,000 source primitive safety cap is unchanged. Private original PDFs and
source-dependent diagnostic geometry must remain outside the public repo.

## Default-off CLI

Given an authenticated original PDF and a reviewed source-face selection JSON
(which must contain the same source SHA, page index and item_faces with
item_id/item_kind/face_segment_ref keys), run:

    python -m planreader_next match-dimensions --pdf source.pdf --page 0 --faces candidate-faces.json --output shadow-associations.json

Output is create-only, contains just source-geometry candidate bindings and
abstentions, and cannot authorize quantities or commercial publication.
