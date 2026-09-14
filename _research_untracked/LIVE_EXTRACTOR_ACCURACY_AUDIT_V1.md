# Live extractor accuracy audit v1

**Branch:** `cursor/live-extractor-accuracy-audit-v1`  
**Base SHA:** `b76f084f8f28c7a8e2c2519386086b04fe5715a0` (`origin/main`, merge of #288)  
**Audit commit:** `483e16a` (tests + report only)  
**Worktree:** `C:\Users\bryce\Documents\worktrees\live-extractor-accuracy-audit-v1`  
**Date:** 2026-09-15  
**Stop:** before merge. Benchmark gold untouched. No production fixes in this pass. Not pushed.

---

## Compliance

| Item | Detail |
|---|---|
| Files read | `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `pb_planreader_pdf_extractor.py` (pred_dict path), `pb_raster_schedule_extractor.deduplicate_schedule_rows`, `pb_drawing_ocr_evidence_layer.EvidenceReconciler`, `pb_opening_evidence_v170.merge_opening_evidence` |
| Functions traced | `GenericPlanReaderExtractor` → `pred_dict[tag]=…` → schedule merge → OCR reconcile → F.9 deduction; `EvidenceReconciler.reconcile`; `deduplicate_schedule_rows` |
| Authority boundaries | Confidence must not prove authority; conflicts must abstain; empty ≠ proven zero; do not weaken gates |
| Untouched | `CanonicalQuantityShadowProvider`, completeness manifests, GPT-2 enumerator work, wall-height remediation PRs, PDF glyph/clip branches, wall-role PR, benchmark gold, commercial pricing |

**Expected abstentions before fixes:** conflicting same-tag observations; schedule parser failures; default-height wall areas for firm commercial use.

---

## Observed live path (brief)

```text
PDF pages
  → GenericPlanReaderExtractor (pb_planreader_pdf_extractor)
       pred_dict: Dict[str, ExtractedPrediction]   # KEY = tag only
  → GenericScheduleTableExtractor → merge by tag+confidence
  → EvidenceReconciler (native vs OCR) by tag dict
  → GenericOpeningDeductionPipeline (F.9)
  → return list(pred_dict.values())
```

Shadow opening / provenance collectors are try/except and documented as non-mutating of `pred_dict`.

---

## Issue register

### P0 — can produce wrong FIRM/commercial-facing result

#### P0-1 — `EvidenceReconciler` last-write-wins on duplicate native tags
| Field | Value |
|---|---|
| File / function | `pb_drawing_ocr_evidence_layer.py` / `EvidenceReconciler.reconcile` |
| Behavior | `by_tag_native = {r.tag: r for r in native_records}` silently drops all but one native observation per tag **before** conflict logic |
| Minimal example | Native D1 qty=2 (page 1) + native D1 qty=5 (page 2); OCR agrees with 5 → status `confirmed` qty=5, **no CONFLICT** |
| Live? | Yes (wired from `pb_planreader_pdf_extractor` OCR reconcile block) |
| Benchmark-facing? | Yes (F.10 / mutation OCR tests exist for native-vs-OCR conflict only, not native-vs-native) |
| Commercial-facing? | Yes if confirmed openings feed deductions / counts |
| Coverage before | Native≠OCR conflict tested; **duplicate native not tested** |
| New regression | `tests/test_live_extractor_accuracy_audit_v1.py::test_reconciler_duplicate_native_same_tag_different_qty_must_conflict_or_retain_both` (**FAILS**) |
| Owner | **Cursor** (isolated reconciler fix) or Claude if merged with opening identity work — prefer Cursor: small fail-closed change |

#### P0-2 — Live `pred_dict` merge: higher confidence overwrites conflicting dimensions
| Field | Value |
|---|---|
| File / function | `pb_planreader_pdf_extractor.py` ~1675–1687 and ~1944–1945 |
| Behavior | `if tag not in pred_dict or new.confidence >= old.confidence: pred_dict[tag] = new` — no dimension/qty conflict check; no scope (level/page/revision) |
| Minimal example | Existing W1 1200×900 @0.80 replaced by W1 1800×1200 @0.95 → single prediction, no CONFLICT |
| Live? | Yes |
| Benchmark-facing? | Indirectly (schedule → predictions) |
| Commercial-facing? | Yes (opening sizes → deductions) |
| Coverage before | Schedule dedupe prefers complete agreeing rows; **does not protect pred_dict merge** |
| New regression | `…::test_pred_dict_confidence_overwrite_erases_conflicting_schedule_dims` (**FAILS**) |
| Owner | **Cursor** (pred_dict merge gate) — coordinate with GPT-2 if enumerator commitment lands on same seam |

### P1 — major incorrect / omitted quantity

#### P1-1 — Schedule conflicting dimensions erased to absence
| Field | Value |
|---|---|
| File / function | `pb_raster_schedule_extractor.py` / `deduplicate_schedule_rows` |
| Behavior | Same opening tag + disagreeing qty **or** dims → tag added to `conflicting_opening_tags` and **skipped** (no row emitted). Fail-closed for emission, but **looks like “no W1”** not CONFLICT |
| Minimal example | W1 1200×900 vs W1 1500×1200 (pages A101/A201) → `[]` for W1 |
| Live? | Yes |
| Benchmark-facing? | Schedule mutation tests cover agreeing duplicates, not conflict→marker |
| Commercial-facing? | Omitted openings / undercount risk if other detectors also miss |
| New regression | `…::test_schedule_conflicting_dimensions_must_not_look_like_absence` (**FAILS**) |
| Owner | **Cursor** (emit provisional CONFLICT row) or **GPT-2** if tied to enumerator completeness vocabulary |

#### P1-2 — Bare `except Exception: pass` on schedule / OCR / deduction seams
| Field | Value |
|---|---|
| File / function | `pb_planreader_pdf_extractor.py` (many: ~1688, 1728, 1762, 1822, 1964, 1981, 2039, 2053, 2067, …) |
| Behavior | Parser/runtime failure → empty contribution; indistinguishable from genuine absence |
| Classification | **AUTHORITY_DANGEROUS** when result feeds quantity; **SAFE** only if caller already treated path as optional shadow |
| New regression | `…::test_except_pass_schedule_failure_must_not_look_like_genuine_empty` (**FAILS** on desired status) |
| Owner | **Cursor** (record `extraction_status=error` metadata; do not invent zeros) |

#### P1-3 — Multi-page / multi-level tag identity
| Field | Value |
|---|---|
| Behavior | Keys are `tag` (and sometimes `tag_WxH` inside schedule dedupe only). No `level` / `viewport` / `revision` in `pred_dict` key |
| Example | Level1 D01 and Level2 D01 collide into one `ExtractedPrediction` |
| Live? | Yes |
| Owner | **Claude** (physical opening / canonical identity) + **Cursor** for interim scoped keys in live pred_dict |

### P2 — robustness / performance / defaults

#### P2-1 — Default ceiling height 2.80 m
| Field | Value |
|---|---|
| File | `pb_planreader_pdf_extractor.py` `__init__(default_ceiling_height_m=2.80)` → perimeter wall area |
| Classification | **LEGACY_QUANTITY_DEFAULT** with partial mitigation: metadata `wall_height_authority=PROVISIONAL`, confidence 0.6, description flags assumption |
| Still dangerous if | Commercial path ignores authority/confidence and consumes `quantity` |
| Owner | Overlaps **wall-height remediation** → **do not fix here**; assign **Claude** / existing height authority owners |

#### P2-2 — Other defaults census (sample)
| Location | Value | Class |
|---|---|---|
| `pb_wall_topology_v174.py` | `default_wall_height=2.7` | LEGACY_QUANTITY_DEFAULT |
| `pb_unified_building_v139.py` | height fallback 2.7 | LEGACY_QUANTITY_DEFAULT |
| `pb_takeoff_accuracy_v125.py` | workspace `default_wall_height_m` 2.7 | DISPLAY / LEGACY |
| `pb_wall_height_authority.py` | forbids assumed/default | SAFE (authority gate) |
| Schedule `is_provisional` skip | — | SAFE (omit uncertain) |

#### P2-3 — Confidence as ranking vs authority
| Location | Note |
|---|---|
| Schedule opening resolve | Uses completeness then confidence among **agreeing** rows — better | SAFE-ish |
| `pb_opening_evidence_v170` | Same-basis: higher confidence wins dimensions | P2 review — ensure conflicts still fail closed elsewhere |
| `pb_page_scale_calibration_authority` | Highest confidence among **agreeing** readings | Out of scope if agreement gated |

#### P2-4 — Performance note (optional)
Shadow/existence path (other branch research): `O(walls × atoms)` re-index. Live schedule path: per-document extract then O(rows) dedupe — not the hotspot. Record only: future immutable indexes must **retain** conflicts, never drop for speed.

### P3 — cleanup
- Reduce nested try/except pass; typed exceptions + status enum.
- `ExtractedPrediction.metadata` often rebuilt without prior keys (OCR path historically discarded derivation — partially fixed for non door/window).
- Document that `pred_dict` is tag-keyed and not physical-instance-keyed.

---

## Provenance loss (AUDIT 8)

| Boundary | What survives | What is lost |
|---|---|---|
| `ScheduleRow` → `ExtractedPrediction` | tag, qty, unit, dims, page, sheet, conf, bbox | level, revision, source_sha, evidence_id, multi-observation set |
| Native+OCR → pred_dict | method/status in metadata for reconcile path | Competing native pages; full observation list |
| `pred_dict` → list return | per-tag single object | Collision history |

---

## Zero vs unknown (AUDIT 5)

| Pattern | Status |
|---|---|
| Conflict → omit tag | Treated as unknown/absent — **defect P1-1** |
| `except: pass` → no rows | Treated as empty — **defect P1-2** |
| Schedule `quantity <= 0` skip | Omits row — OK if not emitting zero as proven |
| No openings in pred_dict | Downstream must not invent `0` openings as FIRM — F.9 skips missing; still risk in commercial aggregators (not fully traced this pass) |

---

## Tests / commits

| Item | Detail |
|---|---|
| Files changed (intended commit) | `tests/test_live_extractor_accuracy_audit_v1.py`, `_research_untracked/LIVE_EXTRACTOR_ACCURACY_AUDIT_V1.md` |
| Focused results | **4 failed** (desired: document defects on main) |
| Full suite | Not run (slow; not required for audit stop) |
| Benchmark gold | Untouched |
| Production fix | **None** this pass (overlap risk; tests first) |

---

## Recommended next owners

1. **Cursor:** P0-1 reconciler multi-native conflict; P0-2 pred_dict merge conflict gate; P1-2 extraction_status on except.  
2. **GPT-2:** P1-1 conflict-vs-empty if enumerator completeness owns “universe incomplete.”  
3. **Claude:** P1-3 physical instance / level-scoped opening identity; avoid CanonicalQuantityShadowProvider overlap.  
4. **ChatGPT / future:** Commercial consumer audit — does JobHub/export honor PROVISIONAL wall height?

---

## Explicit non-actions

No merge. No gold edits. No CanonicalQuantityShadowProvider / completeness / PDF integrity / wall-role / wall-height production changes in this branch.
