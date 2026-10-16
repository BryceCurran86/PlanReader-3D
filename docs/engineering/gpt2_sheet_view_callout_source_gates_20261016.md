# GPT2 source-first sheet, view and callout authority (2026-10-16)

This record is **source-forensic guidance**, not a new source producer, a
quantity, a substitute title-block resolver or a certified viewport map.
It summarizes original-SHA findings recorded in [#2009](https://github.com/BryceCurran86/PlanReader-3D/issues/2009).
For any new quantity require exact producer-issued document/revision/SHA/page/
view/snapshot/decision-scope and explicit physical element lineage.

## Distinct sheet vs. drawing subview

| Original Maryborough PDF page | Title-block sheet | Independently printed local views / first gate |
| --- | --- | --- |
| p7 | A110 PROP. FLOOR PLAN | Physical building rooms; label and closed perimeter authority required |
| p9 | A120 PROP. REFLECTED CEILING PLAN | Building interior RCP; original `view_p9_2` still lacks unique original frame |
| p11 | A140 PROP. FLOOR FINISHES & PARTITIONS PLAN | Floor-finish plan and INTERNAL FINISHES SCHEDULE are distinct source roles; FT3 printed, occurrence and material gates remain incomplete |
| p16 | A251 TRUCK FORECOURT CANOPY ROOF & RCP | Separate roof and canopy RCP; not A120 building ceiling |
| p18 | A253 canopy RCP | Not building interior ceiling |
| p24 | A500 INTERNAL ELEVATIONS - AMENITIES | WC/shower named PLAN inset and distinct elevations |
| p25 | A501 INTERNAL ELEVATIONS - AMENITIES | LAUNDRY/AIRLOCK PLAN inset, dimension candidates 1520/1655, separate elevations |
| p26 | A502 INTERNAL ELEVATIONS - AMENITIES | PROP. PWD PLAN inset, **3570 × 2200 mm unverified candidate**, exact FT2 tag; 4 PWD elevations |
| p27 | A503 INTERNAL ELEVATIONS - AMENITIES | M-AMB/F-AMB plan and elevations |
| p28 | A600 DOOR SCHEDULE | Maryborough doors; must not become Lot16 door schedule |

These names and local observations were checked against original Maryborough
SHA-256 `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`;
they are **not** original-viewport producer seals. Mixed-view sheets must not
be assigned one scalar physical view type. The independent page title
reader `pb_page_title_authority.resolve_document` already owns sheet IDs.
Original plan/elevation inset must be independently bounded.

## GPT2 tasks 1–4: actual authority gates

1. **Sheet classification**: exact title-field sheet ID is distinct from
   local labelled view. No plan inherited from an elevation sheet, and no
   canopy RCP borrowed for the building ceiling. No per-PDF-page
   overclassification. [PR #2788](https://github.com/BryceCurran86/PlanReader-3D/pull/2788)
   is a merged read-only p9 title/frame census, not p9 frame promotion.
2. **FT3**: original A140 FT3 literal/source scope, *complete* definition,
   plan occurrence universe, authentic physical room perimeter and unique
   A140↔A110 wall-by-wall room correspondence required **in one coherent
   producer root**. The original mark-local OFFICE tile cell is GRID,
   **not** OFFICE. Merged [#2810](https://github.com/BryceCurran86/PlanReader-3D/pull/2810)
   retains D4/scale/alternate native side candidates but does not elect
   physical correspondence. No transfer from historical `floor_area` to
   `floor_finish_area`.
3. **Room boundaries**: Food Service and POS Counter are labels/zones in
   one sectioned enclosure, not two individually enclosed rooms.
   FREEZER retains the original source-ring self-intersection negative.
   PWD A502 3570 × 2200 is **7.854 m² arithmetic candidate only**:
   establish measured target, original bracket endpoints, structural ring,
   and exact p26↔p7 source-room owner before FIRM metric issuance; its FT2
   finish is independent of FT3. Other A500/A501/A503 local PLAN insets
   are likewise source candidates, not borrowed dimensions.
4. **Cross-sheet callouts**: the separate
   `pb_cross_sheet_printed_callout_shadow.py` enumerates literal printed
   `1/A-201`, `2/S-0.01`, and same-text-line pieces without changing
   existing `pb_cross_sheet_callout_evidence` or live registration.
   The matching target *sheet ID* must be resolved upstream by labelled
   title-block evidence. Matching a sheet does **not** prove a unique
   source wall, physical target, dimension endpoint, door or room.
   Keep all competing candidates, preserve exact punctuation, and ABSTAIN
   on collisions.

### Protected baseline

Do not change original PDFs, frozen Full Plan V2 truth, evaluator/denominator,
2.5pt snap, signed Maryborough Food Prep/Office/Cold Room floor areas or eight
Lot16 opening areas. Default-off diagnostics are not benchmark matches.
