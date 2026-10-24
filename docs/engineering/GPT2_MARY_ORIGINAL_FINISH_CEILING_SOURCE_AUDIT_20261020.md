# GPT2 original floor/ceiling schedule versus occurrence source audit — 20 October 2026

## Architecture, first deliverable and boundaries

Architecture report posted on GPT2 [#2843](https://github.com/BryceCurran86/PlanReader-3D/issues/2843) before implementation. Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`, the floor plan and ceiling plan source authority paths, and the original p7/p9/p11/p25–p29 drawing views. Does **not** modify W2/W3/W4, Maryborough rooms, floor/ceiling metric issuers, commercial/customer contracts, any private source PDF or the frozen benchmark.

**Original immutable source:** 31 pages, SHA-256 `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`. The original was independently read outside the public repository; private bytes are not added to GitHub.

**Observed first failure:** FITZ `Page.get_text("words")` returns the **unrotated PDF content coordinate system**, while `Page.rect` gives the rotated visual page. Original Maryborough sheets p9 and p11 are rotated 90 degrees. A native word with y=2197 is on the printed visual sheet; discarding it as beyond `page.rect.height=1684` incorrectly deletes genuine material schedule words. Rotate with `page.rotation_matrix` for visual comparison; preserve native source boxes and extraction-scoped word addresses.

## Original-source evidence (not quantity)

| Original page | Mark | Schedule row source address | Source-native specification | Other same-token source marks outside schedule |
| --- | --- | --- | --- | ---: |
| p11 A140 | FT2 | block 243 / line 0 / word 0 | Amber Tiles Liverpool, floor tile **800x400 Stockton White**, **R10 slip** | **8** |
| p11 A140 | FT3 | block 244 / line 0 / word 0 | Amber Tiles Liverpool, floor tile **600x600 Dura Grey**, **min R12 slip**, epoxy grout | **5** |
| p9 A120 | IPF1 | block 308 / line 0 / word 0 | 13mm flush-set plasterboard ceiling linings, square-set edges | **11** |
| p9 A120 | CLD3 | block 307 / line 0 / word 0 | Cladding by signage contractor to tenant specifications | **3** |

The schedules are independently anchored by a *unique native heading* and *one source block containing every column header*, and the source rows include original source-word receipts for each column. The number in the rightmost column is a **native non-schedule word count**, NOT a construction quantity or an authenticated floor/ceiling count. Some such words can belong to legends or annotations and must remain unbound. FITZ block/line/word addresses vary by extractor; they are not stable physical identity, nor a cross-sheet join.

**Crucial material distinction:** FT2 and FT3 are different printed material specifications. Their equal membership in the same `floor tile` trade does not permit aggregation as one SKU or transfer of FT2 to an FT3 room. The owner instruction `FT2 and FT3 may have the same finish specification` is permissive, not an overriding claim that they are equal on this original source. Native punctuation glyphs on FT3 still need existing glyph/clip authority; this read-only diagnostic does not promote them.

**RCP caution:** p9 printed `CLD3` source token is not silently converted to the separate `CL03` requested ceiling code. Their equivalence and exact physical ceiling zone require an independent positive source proof. IPF1 schedule row ≠ an IPF1 room/ceiling polygon.

## Real source and test verification

The diagnostic was executed directly on the original immutable PDF with exact SHA and returned the above four schedule rows and source-role tallies. Local synthetic regression tests cover ten input-order permutations, absent/duplicate source headings or rows, missing independent header, altered PDF SHA, physical page duplicate, genuine 90-degree native-to-rendered transform, and owner-original positive assertions. The private-positive check must show SKIPPED rather than PASSED when source bytes are absent from public CI.

Invocation, on a machine that is authorised to hold original source files:

```bash
python -m tools.diag_gpt2_source_schedule_occurrence_census \
  --source-pdf 'documents/sources/Arch_Combined_Maryborough_Service_Station.pdf' \
  --expected-sha256 b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007 \
  --output original_native_source_audit.json
```

## Downstream first-failing authority and ownership

- GPT2: physical source-wall ring for each room, source-only matches between p11 and p7, all competing registrations retained (e.g. OFFICE), preserve existing owner-confirmed FOOD SERVICE/POS connected passages, not two fictitious closed rings.
- GPT2: ceiling plan p9 physical zones (IPF1, grid, CL03, external soffit) with *separately* verified material and level ownership, not a schedule word treated as geometry.
- GPT1: source-closed **finish-specific** floor area measured to internal face only, covering stops at walls and doorway material transitions. No empty room polygon and no under-wall finish.
- GPT MAX: independent W4 structural wall ID, junction and host equivalence gates; copied room labels, schedule words or office dimensions are never wall authority.
- GPT3: newly issued quantities only after authenticated physical source, producer record integrity, customer signing and independent frozen V2 evaluation; never turn these source counts into benchmark matches.

**Status:** source schedule/word role separation is IMPLEMENTED and locally original-SHA-VERIFIED; material/clip, occurrence→physical floor region, physical room boundary and ceiling zone are still **ABSTAIN**. No new FIRM output, signed quantity or score is claimed. Independent PR review, exact-head CI and owner release approval remain necessary.
