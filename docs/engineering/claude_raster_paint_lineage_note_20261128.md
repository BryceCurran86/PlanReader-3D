# Which paint made each raster segment (Lot16 raster walls, 2026-11-28)

Architecture note before the change (AGENTS); ordered by MAX 7227402524 / 7228307037. Report only.

## Observed
- On a page with no native visible vector observations, raster segments come from the full page render.
- On a page with both, they come from the same full render, kept only inside embedded image regions. Native line work drawn
  over an image is inside those regions, so it is found again as raster segments with their own raster identities.
- The producer already renders an images-only page (embedded images, no line art or text) for other raster evidence.
- Wall candidates built from raster segments carry no native identity, so they cannot be matched to room edges by source.

## Inference
Authentic lineage for a raster segment is the paint that made its pixels: if they are in the images-only render it is image
ink; if they are not, and native line segments cover it within the render's pixel size, it is those lines' ink.

## Built (shadow)
`pb_raster_segment_paint_lineage_shadow.classify_raster_segment_paint(segments, images_only_png, native_lines, dpi)`:
- image share: the part of the segment's pixels that are foreground in the images-only render (within one pixel);
- native cover: the part of its length covered by native lines of the same direction within half their width plus one pixel,
  all such lines listed, none chosen;
- `image_ink` (image share at least 90%, native cover under 90%), `vector_ink` (image share at most 10%, native cover at least
  90%), `image_and_vector` (both at least 90%), else `unattributed`.
It names no new identities and changes nothing. Segments and lines must be in the same page frame.

## Opt-in producer filter (shadow, 2026-11-28)
Measured on Lot16 sheet 3: 1,890 of 1,997 unattributed segments lie inside native word boxes (glyph strokes), and 1,542 of
2,094 wall candidates are made only of such strokes. `SourceVisibilityProducer(raster_image_paint_only_shadow=True)`: on a
page with native visible vectors and images, an image-region raster segment is kept only when its ink is in the images-only
render. Default off: segments, identities and receipts unchanged. Pages without vectors (scans) or without images are not
affected. Segment indices (so raster ids) differ when on.

Measured (one plan sheet per original, off to on): Lot16 candidates 2,094 to 320, published 59 to 24 (33 of today's 59 are
letter strokes; no published native wall lost, 3 more publish), ambiguous 2,035 to 296; Maryborough candidates 3,737 to
3,598, published 442 to 439 (its one picture covers 0.5% of the page); 3Laurel and Q5446 identical. Openings, rooms,
quantities, other sheets and a signed-row replay are not checked.

## Must not influence
Any wall count or quantity expectation. Originals: counts only, before any use.
