# Claude register CL-R01–R30 (#4764 7235069043): ledger, from 28 Nov 2026

Tiers: **live** (changes default behaviour) · **opt-in** (default off) · **report** (changes nothing) · **synthetic**
(made-up drawings only). Nothing here is merged; MAX owns merge, pins and official scoring. Details of earlier work per
item: `claude_c01_c30_ledger_20261127.md`. No new verified benchmark match is claimed.

| item | from | status | tier | evidence / first gate |
| --- | --- | --- | --- | --- |
| R01 C03 default-off verification | C03 | DONE | live = main | `c216571f6`: W2 Lot16/Maryborough and full page byte-identical to main (7235084128) |
| R02 face-aware W2 snap | new | PARTIAL | opt-in | `order-free-snap-1.1.0`; Lot16 sheet 3 named rooms kept; Maryborough sheet 7 room face scope fails closed |
| R03 cold room and false sales cell | new | PARTIAL | report | traced: self-intersecting ring under the snap; sales area on a floor-grid cell; no fix |
| R04 positive wall support for finish edges | C05/C08 | PARTIAL | report | `face_wall_support` rejects the Office/Food Prep false cells; not wired; signed rows not checked |
| R05 Office doorway closure | C08 | PARTIAL | report | real Office ring via `door_jamb_returns`; union shadow keeps WSH/DRY; not wired |
| R06 Food Prep open plan | C22 | NOT STARTED | | |
| R07 inside-face rings and identities | C06–C08 | PARTIAL | report | ring builder candidates; edge-to-wall links ambiguous on Maryborough |
| R08 source-lineage wall identity | new | PARTIAL | report | `pb_wall_lineage_identity_shadow` built with vetoes (synthetic); offline: whole chains not enough for hosts; no live caller |
| R09 viewport crossing | C04 | NOT STARTED | | |
| R10 external footprint first | C09 | NOT STARTED | | |
| R11 garage closure | C10 | NOT STARTED | | |
| R12 party walls | C11 | NOT STARTED | | |
| R13 true junctions | C12 | PARTIAL | opt-in | `crossing_wall_negative_shadow`; originals before/after pending |
| R14 doorway closure | C13 | NOT STARTED | | |
| R15 angled doors | C14 | PARTIAL | opt-in | `angled_opening_precision_shadow`; signed check pending; two Maryborough candidates unhosted |
| R16 cavity sliders and robes | C15 | NOT STARTED | | |
| R17 exterior window hosts | C16 | NOT STARTED | | |
| R18 corner stacker / external doors | C17 | NOT STARTED | | donor #4751 |
| R19 3Laurel missed openings | C18 | NOT STARTED | | donor door stack B–E |
| R20 opening widths and heights | C19 | NOT STARTED | | |
| R21 jamb caps and stroke returns | C20 | NOT STARTED | | |
| R22 Lot16 stub candidates | C21 | PARTIAL | report | one rule explains 125 → 189; member recovery not done |
| R23 Lot16 raster wall lineage | C26 | PARTIAL | report | paint lineage classifier; picture walls have no native identity |
| R24 holes and exclusions | C23 | PARTIAL | report | loops and net area listed, not classified |
| R25 Q5446 finished faces | C24 | NOT STARTED | | |
| R26 curved and stepped walls | C25 | PARTIAL | synthetic | curved walls never candidates |
| R27 picture/vector corroboration | C26 | PARTIAL | opt-in | picture-only detection fails identity and Maryborough checks; stays off |
| R28 donor audit and preview wiring | C27/C28 | PARTIAL | report | donor audit written; nothing ported |
| R29 geometry runtime | C29 | NOT STARTED | | |
| R30 consolidated #4810 | C30 | IN PROGRESS | | #4810 draft |
