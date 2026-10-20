# Architecture Report: Producer-Owned Outlined and Vector-Font Text Recognition Shadow Authority (Item 26)

## Executive Summary
This document establishes the architecture for the **Producer-Owned Outlined and Vector-Font Text Recognition Shadow Authority** (`pb_source_outlined_vector_font_shadow.py`), resolving Workstream C, Item 26 of the Autonomous Core Accuracy Engineering Mission: "Improve recognition of outlined/vector-font text using source-supported evidence."

The primary blockers addressed are:
1. **Unrecognized Vector-Stroked Text Outlines in CAD Plans:** In dense CAD architectural sheets (such as Q5446 Standard Plans V1), annotations, drawing schedules, and dimensions are rendered as vector polylines (outlined character glyphs) rather than embedded TrueType or Type1 font streams. Conventional PDF text extractors (such as MuPDF TextPage) find zero native words across these sheets, leaving critical textual evidence unrecovered.
2. **False Classification as Structural Linework:** Prior geometry stages often either swallowed glyph outlines into wall topology (causing catastrophic complexity cap trips over the 20,000 segment limit) or dropped them indiscriminately without proving text provenance.
3. **Conjunction of Source-Owned Geometric Proofs:** This module implements a rigorous classifier (`classify_outlined_text_ink`) and an immutable producer/authority contract that evaluates character glyph geometry, baseline alignment, regular inter-character pitch, and negative structural wall separation to reliably group outlined character strokes into corroborated text runs without OCR rasterization.

---

## Technical Architecture & Invariants

### 1. Sealed Producer / Authority Pattern
- Standard `_PRODUCER_SEAL`, `_AUTHORITY_SEAL`, and `_RECORD_SEAL` internal singletons ensure immutable writer boundaries.
- Factory method `SourceOutlinedVectorFontProducer.create()` produces the mutable producer.
- Calling `.authority()` returns a frozen `SourceOutlinedVectorFontAuthority` mapping selectors to results.
- Direct instantiation of records or authorities raises `PermissionError`.

### 2. Conjunction of Geometric Proofs
- **Proof A: Bounded Path-Local Extent:**
  - Evaluates bounding box dimensions and maximum segment length for each vector path.
  - Character glyphs must satisfy $W \le 20.0$ pt, $H \le 20.0$ pt, and $L_{\text{segment}} \le 18.0$ pt. Paths exceeding these bounds are classified as `NOT_GLYPH_INK` with `PATH_EXTENT_OVER_BOUND`.
- **Proof B: Baseline Alignment:**
  - Identifies horizontal and vertical baselines across candidate glyph paths within tolerance $|y_i - y_{\text{base}}| \le 1.5$ pt.
  - Tagged with `GLYPH_BASELINE_ALIGNED`.
- **Proof C: Regular Pitch / Kerning Consistency:**
  - Evaluates inter-character spacing along the baseline ($0.2 \le \text{gap} \le 15.0$ pt).
  - Irregular gaps break run grouping.
  - Tagged with `GLYPH_KERNING_REGULAR`.
- **Proof D: Multi-Glyph Word Run Formation:**
  - Requires a minimum of $\ge 3$ consecutive character paths along the common baseline to corroborate a valid word run.
  - Isolated glyph paths that do not form a run remain safely `UNPROVEN` with `ISOLATED_PATH_NOT_RUN`.
  - Tagged with `GLYPH_RUN_CORROBORATED`.
- **Proof E: Negative Structural Stroke Contact Veto:**
  - Tests bounding box intersection against long structural lines ($L \ge 25.0$ pt) within $\le 2.5$ pt snap tolerance.
  - Paths contacting structural lines are vetoed from text classification and marked `UNPROVEN` with `STRUCTURAL_STROKE_CONTACT_VETO`.

### 3. Shadow Mode Guards
- Record `status = CANDIDATE`.
- Explicit flags: `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Preserves all 8 holdout customer quantities and SHA-256 fingerprint (`ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`).
