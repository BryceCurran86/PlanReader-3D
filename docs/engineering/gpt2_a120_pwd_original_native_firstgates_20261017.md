# GPT2 original Maryborough A120/A502 source gates — 2026-10-17

**Status:** original-source read-only architecture and negative-proof report. **NOT** material, metric, room, ceiling, wall, cross-page, QuantityEvidence or customer authority. The original PDF was not edited. Pending source-authority review before any code change.

## Compliance

Read: `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`; `pb_source_native_dimension_stroke_shadow.py`; `pb_structural_wall_ink_shadow.py`; `pb_source_composite_room_face_authority.py`; `pb_cross_view_floor_finish_authority.py`; `pb_cross_view_ceiling_finish_authority.py`; `pb_source_visibility_authority.py`; `docs/engineering/claude_ft3_p11_p7_floor_correspondence_architecture_20261015.md`. This report makes **no** edit to those files, source PDF, 2.5pt W2 snap, 20k guard, source takeoffs, frozen V2, signed quantities or customer records.

**Original input, independently SHA-verified locally:** `documents/sources/Arch_Combined_Maryborough_Service_Station.pdf`, 5,709,675 bytes, 31 pages, SHA-256 `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`. Page references below are **1-based PDF numbers**, not local sheet numbers. The supplied original file is read-only. PyMuPDF `get_text('words', flags=fitz.TEXTFLAGS_WORDS)` and `get_drawings()`; `page.set_rotation(0)` was used **only on an in-memory page for visual rendering**, not on source bytes or production input. Coordinates are native unrotated page points; all listed sheets have `/Rotate 90`. Native word block ordinals can vary with MuPDF version, so they are **diagnostic addresses only**, never production identity by themselves.

## 1. A120 p9 RCP: source-positive marks versus authenticated viewport coverage

Original source-visible A120 is one continuous drawing of the ceiling systems. The already-derived F.07 proposed RCP scope `view_p9_5` has native bbox `[0, 1379.6826171875, 1684, 2384]`, while `view_p9_2` remains unsupported; separately `view_p9_4` is the CEILING FINISHES SCHEDULE. The proposed viewport does **not** contain every main in-plan ceiling mark:

| Exact original native word | Native bbox, pt | Source address (block,line,word) | Inside existing `view_p9_5`? |
|---|---|---|---|
| `GRID` next to `3000`, physically printed inside SALES | `[983.74,1077.53,995.68,1096.64]` | `(114,1,0)` | **No** |
| `SALES` room word | `[955.19,1068.50,971.24,1106.36]` | `(45,0,0)` | **No** |
| `GRID` next to `2400`, near OFFICE | `[391.46,1501.13,403.35,1520.24]` | `(10,1,0)` | Yes |
| `IPF1` plan mark | `[289.01,1830.40,300.86,1846.64]` | `(51,0,0)` | Yes |
| `IPF1` plan mark | `[394.54,909.26,406.48,925.52]` | `(129,0,0)` | **No** |
| `IPF1` plan mark | `[1014.70,523.10,1026.64,539.36]` | `(130,0,0)` | **No** |

The raw lexical census returns 3 `GRID` words (one legend, one OFFICE, one SALES), 12 `IPF1` words (including the finish schedule), and 4 `CLD3` words (including the finish schedule). Of the `IPF1` word bboxes, 9 are inside `view_p9_5`, 3 outside; **raw location is not material-occurrence authority**. `CLD3` is signage contractor cladding and cannot be assumed a normal room ceiling. `FPB`, `WFPB`, `IP` and `GRID` must remain distinct material codes.

**Original uninterrupted native geometry spans the current derived viewport division**, i.e. the boundary y = 1379.6826171875 cuts source drawing strokes. Examples from the original `get_drawings` index (all stroke colour black, no layer, native source `d<path>i0`):
- `d9755i0`, x=265.44 from native y=457.28 to 1959.92, stroke 0.48pt;
- `d1118i0`, x=275.04 from y=470.72 to 1951.52, stroke 0.48pt;
- `d3900i0`, x=1217.04 from y=646.40 to 1550.00, stroke 0.48pt;
- `d9747i0`, x=275.04 from y=1208.72 to 1580.00, stroke 0.96pt.

A strict geometrical census found **70 original black vertical line primitives** with width at least 0.46pt crossing this y-boundary (unverified roles; many may be GRID, dimensions, frame or drafting, not walls). Crucially, original source-native building candidate geometry and in-plan marks occur on **both sides**. The first F.07 gate is to prove complete exact main RCP physical viewport extent from original title/boundary/clip ancestry without borrowing the schedule or choosing a nearest title. Simply expanding `view_p9_5` to cover all ink, combining with unsupported `view_p9_2`, or promoting 3D/ceiling quantities is forbidden. The 70 crossings are evidence to investigate viewport truncation, **not** automatic proof of one physical room or wall.

## 2. A502 p26 PWD: source endpoints meet outer drawing faces, not yet actual finished faces

`3570` native black dimension line `d12615i0` runs at x=157.68 from y=1774.64 to 2179.52 (**404.88pt**). `2200` native black dimension line `d12656i0` runs at y=2245.76 from x=217.44 to 466.80 (**249.36pt**). Exact source line/stroke ids were already diagnosed in merged #2837; merged #2848's structural ink is candidate-only.

The native line endpoint coordinates agree at 0.000pt (native printed precision) with **outer** parallel wall-face candidates:
- 3570 y endpoints: `d487i0` at y=1774.64 and `d511i0` at y=2179.52;
- 2200 x endpoints: `d514i0` at x=217.44 and `d498i0` at x=466.80.

**Competing inner-face original ink remains present:** x=219.60 (`d1125i0`) and x=464.64, y=1777.04 (`d1137i0`) and y=2177.36 (`d1129i0`). The nominal *outer* spans 404.88pt and 249.36pt; inner-to-inner candidate distances are **400.32pt and 245.04pt**. This is a concrete positive endpoint coincidence **and a semantic counterexample**: it is not established that the outer faces are the finished internal net-area faces. The figured annotations also have separate `92` wall component chains and `870` fixture setout. Do not publish 7.854m² or transpose the axes from PDF rotation.

Exact original source printed PWD word on p7 is at native `[406.79,1470.50,...]`; p26 A502 PWD plan source word at `[359.27,1964.90,...]`. Matching label strings is **not** a cross-sheet physical-room join. Need unique p26 actual structural ring, exact p26-to-p7 identity, and owner-positive interior face selection. The door symbol is `D13`, and A600 source schedule specifies `D13 / PWD / SINGLE SWING / 920 × 2040` with 40mm leaf thickness; the `870` on A502 is not scheduled D13 width.

## 3. A140 p11 FT3 and p7 room: separate mark from room ring

The original p11 `FT3` source word at native bbox `[321.16,1429.59,...]` and `OFFICE` near `[317.46,1461.12,...]` are visually inside the same drawn room but in **different native text blocks**. A source mark's visual proximity does not satisfy `CrossViewFloorFinishProducer.publish`'s exact native-block fallback. The five in-plan FT3 words and one separate FT3 schedule code are also not equivalent occurrence objects. Source-owned OFFICE physical page11 perimeter still has competing wall and crop roles; p11→p7 registration has rival hypotheses (-78,0) and (-43.92,0), neither can be elected by maximum overlap alone. Existing plain FIRM OFFICE 9.05352m² is unchanged.

## 4. Required next generic, read-only authority precursor

1. F.07 RCP extent witness: original caption/title-block field vs in-plan physical enclosure, with independent native external wall/clip frame. Account for each source text/line on both sides of candidate bbox; retain rival candidate extents. Segmentation changes are **shadow-first**; cannot enlarge the live viewport from a location-only report.
2. PWD dimension-face semantic ledger: source dimension line → original terminal/tick ancestry → **all** original structural wall-face candidates, source paint/style, correct inner vs outer face in a single closed non-self-crossing physical ring, and independently authoritative A502→A110 room identity. Retain all alternate parallel strokes and failed role decisions.
3. FT2/FT3 text meaning: original byte/embedded glyph, exact visual paint/clip and trusted schedule line + plan mark source scope; physical floor correspondence separately. No source-only text extraction is a material grant.

**Required tests:** original SHA and immutable bytes; adversarial false frame/title, schedule in viewport, grid crossing falsely structural, crop boundary epsilon, partial building outline, 90° rotation, multiple rival viewports, order/permutation, segment splitting, source IDs preserved, malformed/ambiguous native text, PWD inner-vs-outer false positive, competitor room ring, source-only no-mutation/no-quantity, frozen V2 and old signed row retention. Seek owner and separate source-authority review before implementing or changing any producer.

## Reproduce source-only facts

```python
import fitz, hashlib
p = 'documents/sources/Arch_Combined_Maryborough_Service_Station.pdf'
data = open(p,'rb').read()
assert hashlib.sha256(data).hexdigest() == 'b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007'
with fitz.open(stream=data, filetype='pdf') as doc:
    p9 = doc[8]; p26 = doc[25]
    assert p9.rotation == p26.rotation == 90
    words = p9.get_text('words', flags=fitz.TEXTFLAGS_WORDS)
    print([(w[4],tuple(w[:4]),tuple(w[5:8])) for w in words if w[4] in ('GRID','IPF1')])
    for i in (12615, 12656, 487, 511, 514, 498, 1125, 1137, 1129):
        drawing = p26.get_drawings()[i]
        print(i, drawing['items'], drawing['width'])
```

**The figures above have not been used as production measurements or benchmark input.** The architecture-first issue note is #2843, and this document remains review-only.
