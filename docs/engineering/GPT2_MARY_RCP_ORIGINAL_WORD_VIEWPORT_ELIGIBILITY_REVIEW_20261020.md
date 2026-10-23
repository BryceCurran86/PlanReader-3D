# GPT2 authority-first architecture — original RCP word and viewport eligibility

**2026-10-20 | GPT2 tracker #2843 | hub #3462 | architecture / source audit ONLY**

## 1. Observed original source (not scorer gold)

Read exact 31-page `Arch_Combined_Maryborough_Service_Station.pdf` in private runtime: SHA-256 `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`; page 9 (0-based index 8), A120 reflected ceiling plan, displayed rotation 90°, **native PyMuPDF word/drawing coordinates remain unrotated**. No original bytes added to repository.

Original page-9 native `get_text('dict')` block/line receipts:
- `OFFICE` source block **9**, one original line, bbox **(295.42,1465.44,311.48,1503.56)**, independently a room-name *candidate*, not a physical W4 polygon.
- `GRID`/`2400` source block **10**, two original lines, bbox **(391.46,1500.42,416.54,1520.96)**, i.e. a source code/numeric *pair*, not same-text-block office ownership.
- Original block **212**, bbox **(407.02,1388.34,418.96,1491.92)**, contains the full native **`REVIEW IN OFFICE AREA`** mechanical/drafting sentence. Word `OFFICE` inside this line is **not** another room-name instance.
- Original block **5**, bbox (1361.27,120.18,1500.64,356.72), is the **ceiling finishes schedule** and includes `IP`, `FPB`, `GRID`, `WFPB`, `STP`, `CLD` definitions, not six distinct in-room ceiling zones.
- Original blocks **21**, **29**, **36**, **85**, **87**, **114**, **115** contain respectively a `WFPB/2400` pair, `M-AMB`, `F-AMB`, `IPF1` within a multicomponent device/text block, standalone `IPF1`, a second `GRID/3000` pair, and `CLD3` signage/external cladding. These remain source-role competitors until viewport/zone and material authority resolve.
- Full page-9 source census includes **12** native `IPF1` words (includes remote annotation), **3** `GRID`, **9** `WFPB`, **6** `FPB`, **4** `CLD3`. Counts are observational, not quantities or evidence of FIRM ceiling areas.

## 2. Traced actual repository first failure

`pb_source_rcp_ceiling_region_shadow.SourceRcpCeilingRegionProducer.evaluate_and_publish` calls `evaluate_synthetic` with caller-injected `zone_polygons`, `marks` and optional floating `scale_px_per_m`. It stores these in `_results` and later `SourceRcpCeilingRegionAuthority.resolve` returns a `CANDIDATE` physical-room reference even though the original page/eligible viewport, word-block role, source glyph/clip/paint, boundary W4 wall-face ancestors, two-room competitor census and independently authenticated scale were not re-proved at that boundary. The optional `SourceVisibilityProducer` input is retained but **not consumed** by `evaluate_synthetic`.

`SourceRcpCeilingRegionRecord.__post_init__` currently `pass`es if the private seal is wrong, so its record can be caller-constructed. `area_m2` from `area_pts2 / scale_px_per_m**2` is therefore candidate metadata, **not FIRM ceiling quantity**. Existing `tests/test_source_rcp_ceiling_region_shadow.py` intentionally exercises synthetic metrics; those tests do not prove original ceiling source or physical room identity.

Existing narrower read-only upstream producers #3315 (`GRID/FPB/WFPB` callout pairs) and #3324 (M-AMB/F-AMB `IPF1` opposite-side original mark evidence) are separate, still source-only. #3455 narrow doorway-threshold review and Cursor #3466 own transverse passage fix/threshold-flags: DO NOT edit their files/branches.

## 3. Inference — concrete risk if this shadow is promoted

- An original OFFICE token inside a mechanical sentence could win nearest-label election, and schedule GRID code could be treated as an in-room ceiling mark.
- An original GRID/2400 callout could be misclassified as structural zone boundary or as exactly belonging to `OFFICE` before W4 wall/region proof.
- Physical room/ceiling identity and quantified m² could be forged via synthetic caller `zone_polygons`, `physical_room_id`, `canonical_room_id`, `marks` and `scale_px_per_m`. These must not cross GPT1 source-closed issuer.
- CLD3 external signage and any legitimate soffit/eave/canopy areas must not be counted as internal ceilings; a negative source-role finding must be retained.

## 4. Proposed general source-owned solution for owner/authority review

**Stop at review; do not implement or promote without clearance per AGENTS.md.**

1. Introduce a **new, opt-in, source-only original RCP word/viewport eligibility adapter** (not a new scale/identity authority), taking an existing producer-owned page-9 `SourceVisibilityProducer` snapshot and full original word-native receipts; validate exact original bytes SHA+revision+snapshot+page, eligible one-plan viewport and block/line ownership, original visibility/clip/text integrity and all competing words in that viewport, preserving schedule/drafting-note exclusions as typed negatives.
2. Retain whole **native source line identity**, not isolated OFFICE or GRID tokens; require typed plan code/height multi-line source block where actually present. Office standalone room word and separate GRID/2400 block alone MUST NOT assert zone ownership.
3. Link only after original W4 source-owned, closed inside-face ceiling zone and full physical room correspondence (or genuinely independent ceiling zone), separate source material definition and all competitor marks. Distinct `IPF1`, `WFPB`, `GRID`, `FPB`, external `CLD3` and soffit/eave roles may never alias by nearest name/coordinate.
4. New output remains `CANDIDATE` or `ABSTAINED` and `source_original_rcp_word_scope_only=True`; **all** physical zone, W4 wall, metric scale, source-closed FIRM, signed customer and benchmark grants remain false. No change to existing `pb_live_ceiling_area_quantity_publication` or other commercial seams in same PR.
5. Keep 2.5pt global W2 snap and 20,000 raster limit unchanged, preserve all source negatives and derived input-order invariance; never use title-block scale, labels, known m², frozen V2, or QTO gold as prediction inputs.

## 5. Required proof before implementation and review

- Synthetic positive: source-private one-line standalone ROOM and distinct two-line numeric+code annotations; preserve distinct original block/line IDs; no link to physical room/ceiling.
- Look-alikes: “REVIEW IN OFFICE AREA” same isolated word (reject as room), schedule/legend GRID and WFPB (reject as in-plan mark), CLD3 external role vs IPF1, separate block/line but close coordinates (never nearest).
- Negative: wrong SHA/revision/snapshot/page or viewport, stale/removed original words, duplicate native IDs, unreadable glyph/occluded text, conflicting marks, fragmented original line, foreign-source word, split/reordered source geometry, invalid synthetic page scale input; everything fail-closed.
- Invariance: original source word ordering, extraneous unrelated page/title notes, 90° displayed page rotation vs unchanged native coordinates; stable replay IDs and input no-mutation.
- Exact owner original private PDF test on page9 SHA above and original native blocks 5/9/10/21/212 plus separately scoped wet-area marks. Compare complete source inventory, not a hand-picked nearest label.
- Verify no new signed rows, customer parity and frozen V2 truth untouched, exact-head Python 3.13+3.14 CI.
- Handoff to GPT1 only after separate owner-reviewed physical W4 ceiling ring, occurrence material, measurement and canonical identity can be independently proven.

## 6. Frozen benchmark observations excluded

Three generic plain room areas do NOT equal FT2/FT3 floor finish or IPF1/WFPB/GRID ceiling area. Historical 8/51 frozen score is not a p9 area measurement and is never read by this adapter. No original PDFs, benchmark/tolerances, existing quantities, W4 production authorship or owner-controlled PRs change in this first review.
