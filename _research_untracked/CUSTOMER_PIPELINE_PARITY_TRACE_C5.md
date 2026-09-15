# Phase C5 — Customer pipeline parity trace

**Branch:** `cursor/live-extractor-accuracy-audit-v1`  
**Base:** `b76f084f8f28c7a8e2c2519386086b04fe5715a0`  
**Date:** 2026-09-15  
**Scope:** Read-only trace; no application rewrite.

## Verdict

Customer UI and benchmark extraction are **architecturally disconnected**. They do not share an orchestrator, prediction schema, or quantity publisher.

## Customer path

```text
RUN_PLANREADER_WINDOWS.bat
  → streamlit pb_planreader_v133_app.py
    → pb_planreader_reconstruction_v139_app (patch stack)
      → pb_planreader_v126_app → pb_planreader_v11_app → pb_planreader_3d_app
        → app.main() / process_document() / analyse_workspace()
          → pb_auto_geometry_v1219, pb_plan_read_engine_v1228,
             pb_opening_production_v175 (v174 pipeline), pb_accuracy_v13_engines_v145
```

**Not on this path:** `GenericPlanReaderExtractor.extract_from_pdf`.

## Benchmark path

```text
pb_benchmark_accuracy_engine.BenchmarkAccuracyEngine.evaluate_benchmark
  → extract_quantities_from_pdf
    → GenericPlanReaderExtractor.extract_from_pdf
      → schedule / OCR / footprint / F.9 opening deduction pipeline
```

## Shared vs disconnected

| Shared | Notes |
|---|---|
| `pb_hatch_detection_v160` | Same module; different APIs and orchestrators |

| Customer-only (examples) | Benchmark-only (examples) |
|---|---|
| Streamlit shell + patch stack | `pb_benchmark_accuracy_engine` |
| `pb_opening_production_v175` / v174 | `pb_planreader_pdf_extractor` |
| `pb_auto_geometry_v1219` | `pb_drawing_ocr_evidence_layer` |
| JobHub / commercial workspace | Extractor-only evidence modules |

## Firm authority modules — zero live customer callers

Per `AGENTS.md` firm seams (`pb_page_scale_calibration_authority`, `pb_viewport_scale_binding`, `pb_measurement_input_authority`, `pb_figured_dimension_authority`, `pb_wall_length_quantity`, `pb_wall_height_authority`): **none are wired into the v133 customer runtime path**. `build_wall_length_quantity` / `build_wall_height_quantity` have **zero production callers** on any path today.

## Minimum safe integration seam (C6 direction)

1. Keep `GenericPlanReaderExtractor` as benchmark/live extraction source.
2. Add **shadow-only** opening authority parity (`opening_authority_shadow`) that records publishability without mutating `pred_dict`.
3. Future promotion must route through existing firm authority modules — never convert `publication_blocked` / `quantity=None` rows into legacy numeric certainty.
4. Customer UI integration requires a new orchestrator bridging `ExtractedPrediction` → `TakeoffOutputRow` — out of scope for this pass.

## Parity implication

Improving benchmark extractor accuracy does **not** automatically improve customer UI takeoff until an explicit integration seam is promoted through authority review.
