# Antigravity RCP Word and Viewport Scope Eligibility Shadow Authority Report (v1)

## Compliance & Context

### Files Actually Read
- `AGENTS.md`
- `docs/AI_ENGINEERING_PLAYBOOK.md`
- `pb_source_rcp_ceiling_region_shadow.py`
- PR #3462 (shared coordination hub)
- PR #3469 (GPT2 RCP word eligibility review)
- Issue #2843 (GPT2 Maryborough tracker)

### Exact Functions Traced
- `pb_source_rcp_ceiling_region_shadow.SourceRcpCeilingRegionProducer.evaluate_and_publish`: Lines 220–355
- `pb_source_rcp_ceiling_region_shadow.classify_material_role`: Lines 61–68
- `pb_page_scale_calibration_authority.resolve_page_scale_calibration`: Page scale seam

### Authority Boundaries Crossed
- Text token provenance, paragraph/block classification, and viewport boundary confinement.
- Purely non-publishing shadow authority (`status = CANDIDATE`, `commercial_projection_allowed = False`, `takeoff_eligible = False`).

### Expected Abstentions Before Any Tests
- Any text token located outside the authenticated plan drawing viewport (e.g., in title block, schedule table, or margin) is vetoed with `WORD_OUTSIDE_PLAN_VIEWPORT`.
- Any text token embedded within multi-word prose blocks (e.g., general specifications, notes) is vetoed with `WORD_IN_GENERAL_NOTE_BLOCK`.
- Any text token contained within tabular schedule grids is vetoed with `WORD_IN_SCHEDULE_TABLE`.
- Only isolated, compact annotations within the plan viewport receive `ROLE_IN_PLAN_CEILING_ANNOTATION`.
- Customer retention baseline preserved byte-for-byte.

### Files That Will Remain Untouched
- All benchmark gold and holdout definitions (`benchmarks/**`).
- Production extractors and commercial writers.
- 20,000 primitive safety cap and 2.5 pt snap tolerance.

---

## 1. Observed Repository Behavior

In `pb_source_rcp_ceiling_region_shadow.py`, candidate ceiling marks are supplied to `evaluate_and_publish` as raw dictionaries or text tokens. The module validates that:
1. The ceiling mark falls geometrically inside the candidate ceiling polygon (`poly.contains(Point(mark_pt))`).
2. There are no competing marks inside the same zone (`competing_marks`).
3. The material code matches the expected internal ceiling vs external cladding role.

However, the module currently has no mechanism to determine whether a word token from the PDF text stream actually represents an authentic *in-plan ceiling callout* versus:
- A cell in the "CEILING FINISHES SCHEDULE" table (e.g., Page 9 block 5).
- A word occurring inside a general note or mechanical ductwork sentence (e.g., Page 9 block 212).
- A word from an adjacent elevation or title block.

As demonstrated by GPT2 in PR #3469, without word eligibility filtering, text search over Page 9 indiscriminately gathers tokens like "OFFICE", "GRID", and "IPF1" from schedule tables and notes, polluting candidate zones and triggering false `COMPETING_CEILING_MARKS_IN_ZONE` conflicts or false assignments.

---

## 2. Inference

An authentic in-plan reflected ceiling annotation possesses distinct geometric and structural characteristics that distinguish it from prose notes and tabular schedules:
1. **Viewport Confinement**: It lies strictly within the drawing viewport polygon, with a safety margin away from sheet borders.
2. **Block Isolation / Compactness**: In-plan ceiling marks are concise callouts ($1 \le N_{words} \le 4$, e.g., "IPF1", "GRID / 2400 CLG", "CL03"), whereas general notes contain extended sentences ($N_{words} > 6$ or line length $> 35$ characters).
3. **Tabular Exclusion**: Words aligned in strict row/column lattices with repetitive headers (e.g., "MARK", "MATERIAL", "FINISH", "HEIGHT") represent schedule tables and must not be treated as room ceiling callouts.

---

## 3. Proposed Change

Implement `pb_source_rcp_word_eligibility_shadow.py` providing `SourceRcpWordEligibilityShadowAuthority`:
1. `WordRole` enum:
   - `IN_PLAN_CEILING_ANNOTATION`: Eligible in-room ceiling callout.
   - `SCHEDULE_TABLE_CELL`: Words belonging to schedule/legend tables.
   - `GENERAL_NOTE_PROSE`: Words belonging to general notes/specifications.
   - `TITLE_BLOCK_METADATA`: Words in title blocks / revision tables.
   - `OUT_OF_VIEWPORT`: Words outside the designated plan drawing viewport.
2. Classification rules:
   - Evaluates word bounding boxes against plan viewport boundaries.
   - Analyzes enclosing text block word count, line length, and character density.
   - Tests for tabular grid row/column collinearity.
3. Strict shadow mode invariants:
   - `status = CANDIDATE` or `ABSTAINED`.
   - `commercial_projection_allowed = False`, `takeoff_eligible = False`.

---

## 4. Benchmark Observations That Must Not Influence Implementation

- Maryborough Page 9 contains specific schedule headers ("CEILING FINISHES SCHEDULE") and blocks (block 5, block 9, block 10, block 212).
- The algorithm must not depend on Maryborough-specific block IDs or hardcoded coordinates.
- All filtering must be derived from generic 2D geometric bounding boxes, spatial alignment, and text block metrics.
