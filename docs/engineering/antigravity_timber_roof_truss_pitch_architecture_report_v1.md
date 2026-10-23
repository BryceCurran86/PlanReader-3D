# Architecture Report: Source Structural Timber Truss & Rafter Layout Pitch Geometry Shadow Authority (v1)

## Executive Summary
Pitched residential and light-commercial roofs utilize engineered prefabricated timber trusses and stick-framed rafter assemblies to support roof coverings (concrete tiles, metal sheeting) and ceiling finishes across structural loadbearing wall plates.

This module introduces `SourceTimberRoofTrussPitchShadowAuthority`, providing an authoritative shadow-mode extraction and multi-chord geometric takeoff framework for timber roof trusses, rafter spacings, pitch slopes, top/bottom chords, and eaves overhangs directly from structural framing plans and roof elevations.

## Domain Model & Truss Anatomy
1. **Truss Configuration (`TrussProfileType`)**:
   - `FINK`: Standard residential W-web dual-pitch truss spanning between perimeter walls.
   - `HOWE`: Dual-pitch truss with vertical tension webs and diagonal compression struts.
   - `MONO_PITCH`: Single-slope skillion roof truss.
   - `TRUNCATED_GIRDER`: Heavy truncated hip girder truss supporting perpendicular jack trusses.
   - `HIP_RAFTER`: Diagonal hip rafter member running from wall corner to ridge apex.
2. **Bearing Span (`span_mm`)**:
   - Out-to-out distance between structural wall top plates supporting the truss heel joints.
3. **Pitch Angle (`pitch_deg`)**:
   - Roof slope angle (typically 15° to 30°).
4. **Eaves Overhang (`eaves_overhang_mm`)**:
   - Horizontal projection past the wall face (standard 450mm–600mm) creating the eaves soffit.

## Mathematical Formulations
For a symmetrical dual-pitch truss with span \(S\), overhang \(O\), and pitch angle \(\theta\):
- **Half Horizontal Run with Overhang (\(R_{half}\))**:
  \[
  R_{half} = \frac{S}{2} + O
  \]
- **Top Chord Sloped Length per Side (\(L_{top\_side}\))**:
  \[
  L_{top\_side} = \frac{R_{half}}{\cos(\theta)}
  \]
- **Total Top Chord Length per Truss (\(L_{top\_total}\))**:
  \[
  L_{top\_total} = 2 \times L_{top\_side}
  \]
- **Bottom Chord (Ceiling Tie) Length (\(L_{bot}\))**:
  \[
  L_{bot} = S + 2 \times O
  \]
- **Internal Web Strut Estimate (\(L_{webs}\))**:
  For standard Fink configuration:
  \[
  L_{webs} \approx 1.8 \times \left(R_{half} \times \tan(\theta)\right)
  \]
- **Total Timber Linear Run per Truss (\(L_{timber\_total}\))**:
  \[
  L_{timber\_total} = L_{top\_total} + L_{bot} + L_{webs}
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for bearing wall intersections and layout lines.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
