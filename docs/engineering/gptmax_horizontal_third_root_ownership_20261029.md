# GPT MAX horizontal third-root source ownership safety — 2026-10-29

## Observed
On the existing #3870 source-only horizontal tile shadow, `prove_horizontal_tile_seam_source_pixels` checks all original image placements ONLY at two flank points. `prove_contiguous_source_ink_across_horizontal_tile_seam` then uses `basis["image_roots"]` exclusively for every interior source row, so a separate third page image placement covering an interior interval (or only a tiny numerical seam) is invisible to the membership check. A black extra painter can preserve both the two source-root flank positives and the dark final render, despite ambiguous source lineage.

## Inference and first gate
Two independently sampled original roots are not proof of unique ORIGINAL image ownership throughout the full scan. Raster darkness cannot resolve a third source painter. This is source-lineage evidence only; no elevation→plan correspondence, structural host, opening kind, dimensions, count, FIRM quantity, or customer authorization may follow.

## Proposed isolated remediation
At the existing contiguous-source consumer, enumerate the complete original page image placement universe with native transform/mask identity and unique placement keys. Require that only the exact two flank-proven roots intersect the bounded vertical scanline interval; any third, masked, reused-xref-at-new-placement, rotated, or tiny seam-only painter abstains before any pixel scan. Keep strict 0.0001pt top/bottom source-placement guard, 300dpi per-row source/render agreement, and the existing shadow-only output flags. Never use benchmark labels to set tolerances. Add source-neutral third-image interior/seam and outside-scan controls while retaining original SHA-pinned Lot16 p5 xrefs116/115 source-positive tests.

## Verification and unmodified authority
Only existing #3870 horizontal producer/tests plus this architecture report are in scope. No original private PDF/credential, vertical #3863 lane, source issuer, customer seal, archived signed rows, frozen120 scorer, 20k primitive cap or 2.5pt snap are changed. Required: dual-Python exact-head CI, source-positive owner original replay, signed/customer retention and final main integration. No new measured opening or score gain is asserted.

## Additional observed inline-raster first gate
PyMuPDF 1.26.7 synthetic reproduction: a PDF with two distinct image
XObjects and one 0.2pt-high black inline BI/ID/EI image crossing the
source seam yields only two XObjects from `page.get_images(full=True)`,
but three painted images from `page.get_image_info(xrefs=True)`,
including inline xref=0. Therefore the earlier "complete" root census
was incomplete. This change conservatively abstains if any inline raster
overlaps the bounded horizontal source scan, and retains a positive
off-scan control. It does not establish any structural or commercial
authority; original-source and signed/customer release gates remain.
