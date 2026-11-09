# Claude: 3Laurel corner slider. Production host/frame seam, first failing gate (no code change)

Date: 2026-11-09. Answers MAX 6731504428 action 1. Base `22ebd4e3c`; builds on the accepted diagnostic head `4c5ede86e`. **Docs only.** The counterfactual below ran as a read-only scratch experiment with a throwaway in-memory authority object; no production module, registry, quantity or customer field was changed and nothing from it is committed. Short ids and counts only.

## 1. What was traced

`OpeningHostBindingProducer.publish`, `OpeningHostFrameProducer.publish`, the live composition's host-frame traces for page 3, and `pb_live_opening_area_quantity_publication._opening_quantity`, against the original 3Laurel page 3 (read in place).

## 2. Observed behaviour

| Gate | Observation |
|---|---|
| Host binding for the slider | `ABSTAINED`, `no_authenticated_host_wall_band`. The diagnostic shadow yields one `CANDIDATE` (collinear flank: 2 host members; distinct terminator witnesses: 4), which no production producer consumes |
| Counterfactual frame | I built, in memory only, the binding that the production producer *would* have issued from the collinear host members alone (terminator kept out) with the standard resolved reason codes, and asked `OpeningHostFrameProducer.publish` for a frame. Result: **`ABSTAINED`: `opening_host_frame_whole_wall_unproven`, `opening_host_frame_wall_unavailable`, `opening_host_frame_complete_wall_scope_unavailable`** |
| Why the frame fails | The live composition's wall scope for page 3 is `scope_complete = False` (`physical_wall_candidate_scope_bounds_unresolved`). The frame producer needs a complete wall scope to prove a whole wall. This is **not slider-specific: all 180 page-3 openings have a host-frame trace of `ABSTAINED` in the live composition**, including the 53 that already have a corroborated host binding |
| Complete-scope variant | Under the authenticated-viewport wall scope (`scope_complete = True`) the slider's binding still abstains (`raster_source_band_support_unavailable`), so scope completeness is not what blocks the host |
| Quantity gate in code | `_opening_quantity` returns a figured-label quantity when `host_wall_id` is present and **either** a host binding record **or** a host frame record is present in the evidence. It does not require a frame. A frame is a stricter policy gate set by MAX, not a condition in this function |
| Label | The slider's printed two-figure label already resolves (kind `door`, 2,100 x 1,500 as printed). It is only a candidate metric until the gates above are signed |

## 3. First failing gate and the exact missing pieces

**First failing gate: host binding.** No existing producer path can represent the slider's host, because:

1. `OpeningHostBindingRecord` carries one set of collinear host members and one `host_wall_id`. It has **no field for a distinct terminator witness**, so the perpendicular wall cannot be retained as a separate witness inside a promoted record. Storing it as a member would merge it into the host equivalence group, which MAX's condition 2 forbids.
2. `OpeningHostBindingProducer.publish` has no corner-terminated path; every existing path needs a collinear continuation on both flanks (traced in the architecture report).
3. The shadow derives its collinear owners from the same W4 candidates a production path would use, so it is **not independent** evidence. A promoted binding must be issued by the production producer from the existing W4 equivalence authority, not copied from the shadow.

**Second failing gate: frame.** Page-level complete wall scope is unavailable for the whole page (all openings), so `OpeningHostFrameProducer` cannot prove a whole wall for any opening here, slider included.

## 4. Decision

Retain **ABSTAIN** with first failing gate `host binding` (schema and producer path). The shadow `CANDIDATE` is not set to `CORROBORATED`, not wired into a registry, and not consumed by `_opening_quantity`. No width, height or area is promoted. The 3.15 m2 figured product stays a candidate metric.

## 5. Evidence a promoted binding would need (for an authority-promotion review, not implemented)

1. A binding record schema with a distinct terminator-witness field that is excluded from the host equivalence group, plus a production producer path that issues it from W4 equivalence, drawn two-face and jamb ownership, complete competition and taint checks, and exact document/revision/SHA/snapshot/page scope.
2. A complete page wall scope (or an opening-local proof that is complete by construction) so the frame producer can run; without it no frame can exist for any opening on this page.
3. Source-free look-alike, missing-face, foreign-source, wrong-thickness and two-terminator negatives on the real producer (the diagnostic already has them on the shadow), and a protected exact-head original replay.
4. Only then `_opening_quantity` and the seal and customer projection for the printed two-figure slider. Nothing here is a score claim.

## 6. Not proven

Whether authority review would accept a terminator-witness schema; protected-environment behaviour beyond MAX's accepted run of the diagnostic; any quantity or score. No benchmark item is newly eligible.
