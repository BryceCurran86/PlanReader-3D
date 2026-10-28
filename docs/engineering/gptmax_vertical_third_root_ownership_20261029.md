# GPT MAX vertical source-root ownership across original raster seam — 2026-10-29

## Observed current producer
The source-only `pb_gptmax_raster_tile_seam_shadow.py::prove_tile_seam_source_pixels` checks every page image placement at the left/right endpoint samples, but `prove_contiguous_source_ink_across_tile_seam` subsequently checks each interior column against only `basis["image_roots"]`. A third original image placed on an interior segment (or the very narrow source seam) can be omitted from every membership test, and rendered dark pixels cannot prove unique original source ownership.

## Inference
Endpoint source-root uniqueness is not global scanline root uniqueness. A third painting image invalidates an otherwise positive source-lineage claim even if two rooted edge pixels remain dark. This remains a default-off diagnostic: no wall/host/frame, physical opening, metric quantity, customer, or frozen benchmark authority.

## Narrow remediation
Preserve existing 0.0001pt abutment and numerical seam source-edge checks. Before source pixel scanning, enumerate every actual page image xref/soft mask and transformed placement intersecting the bounded x scan at source y. Require membership only in the exact two original selected placements, unmasked and axis-aligned with supported original transform, and require both selected placements to remain present. An extra image with a different xref, same xref but new placement, foreign transform/mask, or seam-only footprint must return typed source membership ABSTAIN. Keep all negative/authority flags unchanged. Source-neutral regressions: extra painter in left interior, right interior and subpixel seam, repeated xref with alternate placement, and unrelated image off scanline; source original Lot16 2124 source-ink tests must remain unchanged.

## Boundary and validation
Only the previously claimed existing vertical #3863 producer and its tests plus this architecture report may change. No private PDF, source hashes, original text issuers, signed/customer artefacts, benchmark truth/evaluator, 20k primitive cap or 2.5pt snap changes. Required before merge: exact-head Python3.13/3.14 CI, source-positive immutable original replay at pinned library version and complete signed/customer retention. No new opening/quantity or frozen120 accuracy increase asserted.

## Additional first-failing inline-raster ownership gate
A synthetic PDF containing two distinct image XObjects plus a genuine black
0.2pt BI/ID/EI inline image crossing the source seam produces only two
entries from PyMuPDF 1.26.7 page.get_images(full=True), but
page.get_image_info(xrefs=True) reports a third raster with xref=0.
The original two-root census therefore missed a possible source painter.
The conservative remediation abstains on inline paint anywhere on the
bounded source scan and retains a positive off-scan metamorphic control.
This does not prove a host, kind, area, customer row or frozen score.
