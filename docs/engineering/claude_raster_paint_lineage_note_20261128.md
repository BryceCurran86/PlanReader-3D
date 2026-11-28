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

## Signed-row replay result (2026-11-28): NOT SAFE TO PROMOTE
All 65 signed rows kept the same values and Maryborough's three floor rooms were identical, but Lot16 sheet 3 lost 10 rooms
including a WC and a LINEN cupboard whose walls exist only in the page's picture: where line work drawn over the picture
extends a picture line, the full-render segment is partly outside the picture and the filter drops it whole. Next design:
detect the primary raster family on the images-only render (picture ink stays whole, overlaid text and lines are never
seen), check receipt binding, and repeat the replay.

## Opt-in picture-only detection (shadow, 2026-11-28, replaces the filter; MAX 7230726656)
`SourceVisibilityProducer(raster_picture_detection_shadow=True)`: on a page with native visible vectors AND embedded
pictures, the primary raster family is detected on the producer's images-only render (kept inside picture regions as
before). Each segment's ref carries that render's SHA-256 and the identity version `picture-1.0.0`, so receipts bind to
the render that produced them and cannot be confused with full-render segments. A picture line continued by a drawn line
stays whole; drawn lines and text are never seen. Default off: segments, identities and receipts unchanged; pages without
vectors (scans) or without pictures are unaffected; the opening-local supplemental families are unchanged. Replay on the
originals required before any promotion.

## Gate result (2026-11-28): fails, replay not run
The detector's Otsu threshold depends on the whole image, so picture detection now classifies with the full render's
threshold; near the failing rooms its segments are then identical to today's apart from two letter pieces. Lot16 sheet 3
still goes 61 to 53 rooms (WC and LINEN lost): a 78.5 pt picture segment present identically with the option does not
become a wall, so wall building depends on unrelated segments elsewhere. That needs its own design before any replay.

## Must not influence
Any wall count or quantity expectation. Originals: counts only, before any use.
