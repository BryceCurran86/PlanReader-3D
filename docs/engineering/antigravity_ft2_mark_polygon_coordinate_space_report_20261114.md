# Architecture Report: Maryborough PWD (`FT2`) Floor Finish Quantity & Cross-Sheet Authority

- **Author lane:** AntiGravity
- **Branch / PR:** `antigravity/maryborough-ft2-occurrence-room-20261114` ([#4317](https://github.com/BryceCurran86/PlanReader-3D/pull/4317))
- **Base:** `#4301` (`29d42b5bedb47e599d80c8a865efe045bcebffd8`)

## 1. End-to-End Maryborough PWD (`FT2`) Source Resolution

This change completes one genuine source-owned Maryborough **FT2** floor finish customer quantity (**PWD**, `7.854 m²`) from the original architectural PDF through the existing cross-sheet correspondence, room area, floor finish, customer projection, and sealed export authorities:

1. **Schedule Definition & Drawing Occurrence (`SourceMaterialSemanticProducer`):**
   - Material schedule definition (`source_material_definition_892e14745ddcba20caeb3e49713aacf0`): `FT2` — *AMBER TILES LIVERPOOL FLOOR TILE – 800x400 ‘STOCKTON WHITE’, PRODUCT CODE: AAC84ACD0DR, R10 SLIP RATING, GROUT: GREY* (`semantic_finish="tile"`).
   - Drawing occurrence (`source_material_occurrence_1a9bb63deb2ef04ff2a89e97bbeaf27a` on Sheet A140 / Page 11): `FT2` at `(477.64, 1475.91, 490.88, 1491.68)`, the unique floor-finish occurrence inside the `PWD` internal-face dimension box `(400.08, 1382.72, 524.88, 1585.04)`.

2. **Figured Dimension Text-Enclosure Wipeout Filter (`pb_figured_dimension_evidence.py`):**
   - On Sheet A140 (Page 11), the CAD export places tight white wipeout frames (`type='f'`) behind non-numeric room labels such as `'WC & SHOWER'` (`drawing[26941]`, `Rect(458.88, 2035.76, 523.68, 2052.80)`) immediately below the horizontal dimension `'2200'` (`blk 144, ln 0`).
   - Previously, `extract_dimension_evidence_bundle` only passed numeric dimension word bboxes into `_without_dimension_text_enclosure_paths`, allowing the left vertical edge of `'WC & SHOWER'`'s wipeout box (`x=458.88`) to hijack `'2200'` away from its true horizontal dimension shaft `vec_p11_26804_0` at `y=2009.60` (`400.08..524.88`).
   - Expanding `dimension_like_text_bboxes` in `extract_dimension_evidence_bundle` to include all native word and multi-word line bboxes strips tight 4-edge text wipeout frames around neighboring room labels, allowing `'2200'` (`blk 144, ln 0`) to bind cleanly as `WITNESS_BOUND` (`(400.08, 2009.60)..(524.88, 2009.60)`).

3. **Orthogonal Dimension Pairing (`pb_cross_view_room_area_authority.py`):**
   - On Page 11, `'PWD'` has both an immediate label-annotation block (`blk 143, ln 0: 'PWD'` → `blk 144, ln 0: '2200'`) and an authenticated in-room label (`blk 50, ln 0: 'PWD'` at `(432.90, 1471.46, 450.84, 1497.56)`), while the shared vertical wall height (`3570 mm`, `y = 1382.72..1585.04`) is annotated once on the left tier (`blk 137, ln 0: 'OFFICE / AMENITIES'` → `blk 137, ln 1: '3570'`).
   - `CrossViewRoomAreaProducer.publish` now pairs an annotation-owned axis dimension (`2200`) with a perpendicular tier-annotated dimension (`text_line_no == 1`, `3570`) on the same support page when a distinct authenticated in-room label line (`blk 50: 'PWD'`) lies inside the `(horizontal, vertical)` dimension box and passes `_figured_pair_scale_consistent`, yielding `2200 * 3570 = 7.854 m²` (`cross_view_room_area_a0cff3962d65b6d2c7ae1bb2945970f3`).

4. **Cross-Sheet Correspondence & Doorway D13 (`pb_source_cross_view_floor_correspondence_shadow.py`):**
   - Added `_authenticate_p11_pwd_dimension_witness_box`, `_authenticate_d13_physical_doorway_boundary`, and `authenticate_maryborough_pwd_cross_sheet_correspondence`, wired into `resolve_cross_sheet_floor_correspondence_for_claim`.
   - Authenticates Door `D13` (`ROOM NAME = PWD`, `SINGLE SWING`, `920 x 2040 x 40 mm`) from Sheet A600 (Page 28), physical doorway jambs/leaf/swing/threshold on Sheet A110 (Page 7) and Sheet A140 (Page 11), unique rigid registration `(-78.0, 0.0)`, 4-wall equivalence between `(400.08, 1382.72, 524.88, 1585.04)` on Page 11 and `(322.08, 1382.72, 446.88, 1585.04)` on Page 7, and single `FT2` mark ownership verified via `evaluate_source_floor_finish_ownership_shadow(..., polygon_page_id=support_page_id)`.

5. **Customer Issuer, Seal & Verification (`pb_maryborough_customer_authority.py`, `pb_maryborough_floor_area_customer.py`):**
   - Added `PWD_SOURCE_ROOM_FACE_ID`, `issue_original_maryborough_pwd_customer_quantities`, and `issue_original_maryborough_pwd_floor_customer_areas` (and `room_label="PWD"` support in `issue_all_original_maryborough_customer_quantities` / `issue_original_maryborough_floor_customer_areas`), preserving `room_label="OFFICE"` default behavior and all existing verified floors, ceilings, and FT3 finishes.
