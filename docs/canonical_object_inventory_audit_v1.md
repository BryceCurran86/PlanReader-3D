# Canonical Building Object Inventory Audit (v1.0)
**Task Reference:** AG-10 — CANONICAL OBJECT INVENTORY  
**Authority:** PlanReader Autonomous Integration Authority  
**Repository:** `PlanReader-3D`  
**Date:** 2026-10-01  

---

## Executive Summary

This document establishes the authoritative inventory of all canonical building elements within the PlanReader-3D codebase. It audits the data models defined primarily in [`pb_canonical_building.py`](file:///C:/Users/bryce/source/repos/BryceCurran86/PlanReader-3D/pb_canonical_building.py) and related modules ([`pb_auto_geometry_v1219.py`](file:///C:/Users/bryce/source/repos/BryceCurran86/PlanReader-3D/pb_auto_geometry_v1219.py), [`pb_model_masses.py`](file:///C:/Users/bryce/source/repos/BryceCurran86/PlanReader-3D/pb_model_masses.py), [`pb_room_face_takeoff.py`](file:///C:/Users/bryce/source/repos/BryceCurran86/PlanReader-3D/pb_room_face_takeoff.py), [`pb_bound_wall_finish_quantity_authority.py`](file:///C:/Users/bryce/source/repos/BryceCurran86/PlanReader-3D/pb_bound_wall_finish_quantity_authority.py), [`pb_opening_detail_definition_bridge.py`](file:///C:/Users/bryce/source/repos/BryceCurran86/PlanReader-3D/pb_opening_detail_definition_bridge.py), [`pb_structural_member_coverage_snapshot.py`](file:///C:/Users/bryce/source/repos/BryceCurran86/PlanReader-3D/pb_structural_member_coverage_snapshot.py)).

The core architectural principle is:  
> **ONE PHYSICAL BUILDING OBJECT = ONE CANONICAL IDENTITY**  
> Multiple pieces of evidence (from plans, elevations, schedules, sections) attach to that single physical object, and multiple trade takeoff rows derive quantities from its geometry and attributes.

---

## Comprehensive Object Inventory Table

| Object Type | Class / Representation | Current Status | Primary Source | Geometry Model | Identity Scheme | Takeoff Trades | 3D Consumer |
|---|---|---|---|---|---|---|---|
| **Project** | `CanonicalProject` | First-class Dataclass | Project Setup / Metadata | Bounding Box | UUID4 / String | Project Summary | BIM Scene Root |
| **Building** | `CanonicalBuilding` | First-class Dataclass | Multi-building Masterplan | Bounding Box | UUID4 / String | Multi-building Takeoff | Building Group |
| **Level / Storey** | `CanonicalLevel` | First-class Dataclass | Level Datum / Elevation | Datum Elevation (`z`), Height | UUID4 / Level Index | Level Grouping | Floor Slices |
| **Room / Space** | `CanonicalSpace` | First-class Dataclass | Plan Boundary / OCR Labels | 2D Boundary Polygon + Height | UUID4 / Room Number | Finishes, Ceilings, Tiling | Spatial Volumes |
| **Slab / Floor** | `CanonicalFloor` | First-class Dataclass | Floor Plan / Slab Edge | 2D Boundary Polygon + Thick | UUID4 / Floor Tag | Concrete, Formwork, Finishes | Extruded Slab Mesh |
| **Wall** | `CanonicalWall` | First-class Dataclass | Wall Runs / Parallel Vectors | Start (x,y), End (x,y), Thick, H | UUID4 / Wall Ref | Net Wall, Framing, Masonry | Extruded Wall Solid |
| **Wall Face / Surface** | `CanonicalFinishSurface` | First-class Dataclass | Room Boundary / Wall Boundary | 2D Area + Orientation (Side) | Derived: `{wall_id}_{side}` | Plaster, Paint, Render, Tile | Wall Face Layers |
| **Opening (General)** | `CanonicalOpening` | First-class Dataclass | Plan Void / Elevation Detection | Offset on Wall, Sill, W, H | UUID4 / Mark | Deductions, Void Allowance | Wall Cutout / Punches |
| **Door** | `CanonicalOpening(DOOR)` | First-class Dataclass | Plan Arc / Schedule Entry | Offset, Sill, Width, Height | UUID4 / Door Mark (e.g. D01) | Doors, Hardware, Architraves | Door Leaf & Frame Solid |
| **Window** | `CanonicalOpening(WINDOW)` | First-class Dataclass | Glazing Callout / Schedule | Offset, Sill, Width, Height | UUID4 / Window Mark (W01) | Glazing, Flashings, Sills | Glazing & Frame Solid |
| **Ceiling** | `CanonicalCeiling` | First-class Dataclass | RCP / Room Spatial Boundary | 2D Polygon + Elevation Offset | UUID4 / Ceiling Ref | Plasterboard, Grid, Cornice | Horizontal Plane Mesh |
| **Roof** | `CanonicalRoof` | First-class Dataclass | Roof Plan / Pitch Callout | 2D Polygon, Pitch, Overhang | UUID4 / Roof Tag | Metal/Tile Roofing, Truss/Rafter| Pitched Sloped Meshes |
| **Beam** | `StructuralMemberCoverageSnapshot` | Shadow / Specialized | Structural Plan / Schedule | Centerline Start/End, Profile | Mark (e.g. 200UB, B1) | Structural Steel, Concrete Beam| Linear Profile Extrusion |
| **Column** | `CanonicalColumn` | First-class Dataclass | Column Grid / Schedule | Center (x,y), W, D, Height | UUID4 / Column Mark (C1) | Concrete, Structural Steel | Vertical Prism Mesh |
| **Footing** | Extractor / DPC Evidence | Unregistered Dataclass | Substructure / Footing Plan | Centerline / Pad Boundary | Footing Ref / Mark (e.g. F1) | Earthworks, Footing Concrete | Substructure Solid |
| **Stair** | 3D Editable Model Reference | Unregistered Dataclass | Architectural Plan / Section | Flight Polyline, Rise/Going | Stair Ref (e.g. ST01) | Carpentry, Concrete, Handrails | Stepped Prism Mesh |
| **Finish** | `CanonicalFinishSurface` | First-class Dataclass | Finish Schedule / Legend | Area ($m^2$), Substrate, Finish | Finish Code / Key | Paint, Render, Carpet, Tiles | Surface Texture / Material|
| **Fixture** | Symbol / Viewer Entity | Unregistered Dataclass | Hydraulic / Joinery Symbols | Point (x,y,z), Rotation | Tag (e.g. WC, BASIN, SHWR) | Plumbing Fixtures, Joinery | 3D Component Glyph |
| **Service** | Room Service Tag / Annot | Unregistered Dataclass | MEP / Hydraulic Annotations | Run Polyline / Fixture Point | Service Run ID | Hydraulic, Electrical Runs | Pipe / Conduit Path |
| **Structural Member** | `StructuralMemberCoverageSnapshot` | Shadow / Specialized | Engineering Layouts | Polyline / Section Designation | Mark / Section ID | Steel Framing, Timber Trusses | 3D Structural Skeleton |
| **Soffit** | `CanonicalSoffit` | First-class Dataclass | Eaves / Overhang Geometry | 2D Polygon + Elevation Offset | UUID4 / Soffit Tag | Eaves Lining, External Cladding| Inverted Horizontal Mesh |
| **Balcony** | `CanonicalBalcony` | First-class Dataclass | External Floor Slab Plan | 2D Polygon + Balustrade IDs | UUID4 / Balcony Ref | Waterproofing, Tiling, Concrete | Projecting Slab Mesh |
| **Parapet** | `CanonicalParapet` | First-class Dataclass | Perimeter Roof Elevation | Start/End (x,y), Height, Thick | UUID4 / Parapet Ref | Parapet Framing, Capping | Perimeter Upstand Mesh |
| **Balustrade** | `CanonicalBalustrade` | First-class Dataclass | Balcony Edge / Stair Void | Start/End (x,y), Height | UUID4 / Balustrade Mark | Metalwork, Glazing, Handrails | Vertical Barrier Mesh |
| **Screen** | `CanonicalScreen` | First-class Dataclass | Privacy Screen / Louvres | Start/End (x,y), Height | UUID4 / Screen Tag | Privacy Screening, Cladding | Perforated / Slat Mesh |
| **Evidence Observation** | `CanonicalEvidenceObservation` | First-class Dataclass | OCR / Annotation / Extraction | 2D Bounding Box / Coords | UUID4 / Obs Ref | Audit / Traceability Chain | Annotation Overlay Glyph |

---

## Detailed Object Specifications

### 1. Project (`CanonicalProject`)
- **SOURCE:** Workspace initialization / PDF Document Properties / Title Block Extraction.
- **IDENTITY:** String UUID4 or slug (`project_id`).
- **GEOMETRY:** `BoundingBox3D` covering all child buildings.
- **PROVENANCE:** Workspace metadata, primary drawing set references, client/project name.
- **RELATIONSHIPS:** Root parent. Contains `List[CanonicalBuilding]` and `List[CanonicalEvidenceObservation]`.
- **TAKEOFF CONSUMERS:** Project overview, summary preliminaries, tender aggregation.
- **3D CONSUMERS:** Top-level Three.js / pydeck coordinate frame origin.
- **MISSING FIELDS:** Global project datum/CRS, north rotation angle, site boundary coordinates, default level-to-level height fallback.

### 2. Building (`CanonicalBuilding`)
- **SOURCE:** Site plan, multi-block masterplans, or default single-building container.
- **IDENTITY:** String ID (`bld_001`).
- **GEOMETRY:** `BoundingBox3D` containing all level boundaries.
- **PROVENANCE:** Drawing reference, building identification tags on site plan.
- **RELATIONSHIPS:** Child of `CanonicalProject`. Parent of `List[CanonicalLevel]`.
- **TAKEOFF CONSUMERS:** Multi-building building-level division of quantities.
- **3D CONSUMERS:** Transform group in 3D viewer.
- **MISSING FIELDS:** Building gross external area (GEA), building classification / BCA class, base ground elevation relative to AHD.

### 3. Level (`CanonicalLevel`)
- **SOURCE:** Floor plan drawing, elevation datum markers (`pb_level_datum_extraction.py`).
- **IDENTITY:** Unique string ID (e.g. `lvl_ground_01`), indexed by `level_index` integer.
- **GEOMETRY:** Datum elevation `elevation_m` ($Z$), story height `height_m` ($\Delta Z$).
- **PROVENANCE:** Level name on drawing title, datum callout marker.
- **RELATIONSHIPS:** Child of `CanonicalBuilding`. Parent of all level-specific physical elements (`walls`, `spaces`, `floors`, `ceilings`, `roofs`, `soffits`, `balconies`, `parapets`, `columns`, `balustrades`, `screens`, `surfaces`).
- **TAKEOFF CONSUMERS:** Grouping and breakdown for all trade takeoff rows (`level_name` column in `takeoff_rows`).
- **3D CONSUMERS:** Vertical layer slicing, storey toggle visibility in BIM viewer.
- **MISSING FIELDS:** Structural vs architectural floor levels (FSL vs FFL), floor-to-ceiling clear height.

### 4. Room / Space (`CanonicalSpace`)
- **SOURCE:** Room boundary detection (`pb_room_boundary_v1214.py`), OCR text labels.
- **IDENTITY:** UUID or deterministic string: `space_{level_id}_{room_number}`.
- **GEOMETRY:** `boundary_polygon` (`List[Vector2D]`), `height_m` (room clear height), `specified_floor_area_m2`.
- **PROVENANCE:** Sheet page number, OCR coordinates of room name label.
- **RELATIONSHIPS:** Child of `CanonicalLevel`. Associated with perimeter `CanonicalWall` objects and enclosing `CanonicalFloor`/`CanonicalCeiling`.
- **TAKEOFF CONSUMERS:** Room floor finishes ($m^2$), skirting lengths ($lm$), ceiling linings ($m^2$), cornice ($lm$), internal wall face finishes ($m^2$).
- **3D CONSUMERS:** Semi-transparent spatial volume massing (`model_masses`), spatial boundary wireframes.
- **MISSING FIELDS:** Explicit adjacency graph (list of bounding wall IDs with boundary segments), room usage category (Wet Area vs Dry Area classification).

### 5. Slab / Floor (`CanonicalFloor`)
- **SOURCE:** Floor plan perimeter extraction, structural slab layouts (`pb_slab_classification_geometry.py`).
- **IDENTITY:** UUID or string: `floor_{level_id}_{tag}`.
- **GEOMETRY:** `polygon` (`List[Vector2D]`), `thickness_m`, `elevation_offset_m`, `specified_floor_area_m2`.
- **PROVENANCE:** Floor plan slab boundary, structural notes for slab thickness.
- **RELATIONSHIPS:** Child of `CanonicalLevel`. Host to floor finishes, base support for walls.
- **TAKEOFF CONSUMERS:** Concrete slab volume ($m^3$), slab formwork ($m^2$), vapor barrier ($m^2$), mesh reinforcement ($m^2$).
- **3D CONSUMERS:** Horizontal extruded solid in 3D viewer.
- **MISSING FIELDS:** Slab depression / set-down zones, step-downs for wet areas/balconies, edge beam integral thickenings, reinforcement mesh specification.

### 6. Wall (`CanonicalWall`)
- **SOURCE:** Vector line pairs, parallel wall runs (`pb_auto_geometry_v1219.py`), wall assemblies (`pb_wall_room_topology_wall_assembly.py`).
- **IDENTITY:** Deterministic ID: `wall_{level_id}_{x1}_{y1}_{x2}_{y2}` or UUID.
- **GEOMETRY:** `start_point` (`Vector2D`), `end_point` (`Vector2D`), `thickness_m`, `height_m`, `is_external` (bool).
- **PROVENANCE:** Plan drawing sheet, scale factor, vector path signatures, callout references.
- **RELATIONSHIPS:** Child of `CanonicalLevel`. Host to `openings` (`List[CanonicalOpening]`). Bounded by spaces on left/right.
- **TAKEOFF CONSUMERS:** Linear wall length ($lm$), gross wall area ($m^2$), net wall area after opening deductions ($m^2$), wall volume ($m^3$).
- **3D CONSUMERS:** Extruded vertical box solid with window/door cutouts punched out.
- **MISSING FIELDS:** Construction type (brick veneer, cavity brick, lightweight stud, precast concrete), fire resistance level (FRL), acoustic rating (Rw).

### 7. Wall Face / Surface (`CanonicalFinishSurface`)
- **SOURCE:** Room boundary segmentation, wall finish callouts (`pb_bound_wall_finish_quantity_authority.py`, `pb_room_face_takeoff.py`).
- **IDENTITY:** Deterministic composite ID: `{wall_id}_face_internal` or `{wall_id}_face_external`.
- **GEOMETRY:** `surface_area_m2`, `orientation` (string: `INTERNAL_LEFT`, `INTERNAL_RIGHT`, `EXTERNAL`).
- **PROVENANCE:** Room finish schedule, elevation finish callouts.
- **RELATIONSHIPS:** Child of `CanonicalWall` and linked to `CanonicalSpace`.
- **TAKEOFF CONSUMERS:** Plasterboard lining ($m^2$), internal paint ($m^2$), wall tiling ($m^2$), external render/cladding ($m^2$).
- **3D CONSUMERS:** Material shader/texture applied to wall prism side faces.
- **MISSING FIELDS:** Vertical finish banding / tile height (e.g. full height vs 2000mm vs 1200mm dado), waterproofing membrane boundary.

### 8. Opening (`CanonicalOpening`)
- **SOURCE:** Plan door swings/voids, elevation openings, window schedules (`pb_opening_detail_definition_bridge.py`, `pb_opening_deduction_v174.py`).
- **IDENTITY:** UUID or Mark (`D01`, `W03`, `OP05`).
- **GEOMETRY:** `offset_along_wall_m`, `sill_height_m`, `width_m`, `height_m`.
- **PROVENANCE:** Plan vector coords, elevation detail sheet, window schedule row, page reference.
- **RELATIONSHIPS:** Child of `CanonicalWall` (`wall_id`). Connects adjacent spaces.
- **TAKEOFF CONSUMERS:** Wall opening deductions ($m^2$), lintel length ($lm$), head and sill flashings ($lm$).
- **3D CONSUMERS:** Boolean subtraction cutout from host wall solid; door/window insert geometry.
- **MISSING FIELDS:** Frame material (timber, aluminium, steel), glazing specification (single/double, Low-E), acoustic/fire rating.

### 9. Door (`CanonicalOpening` with `opening_type='DOOR'`)
- **SOURCE:** Plan door swings, door schedules.
- **IDENTITY:** Unique door mark (e.g. `D01`, `D-02`).
- **GEOMETRY:** Width ($m$), height ($m$), sill height ($m$, usually $0.0$).
- **PROVENANCE:** Door schedule row reference, plan door swing coordinates.
- **RELATIONSHIPS:** Sub-kind of `CanonicalOpening`. Child of host `CanonicalWall`.
- **TAKEOFF CONSUMERS:** Door unit count (each), door frame (each), hardware furniture (sets), architraves ($lm$), paint to leaf & frame ($m^2$).
- **3D CONSUMERS:** 3D door leaf, swing arc, and frame profile.
- **MISSING FIELDS:** Door operation type (hinged, sliding, cavity slider, bi-fold), core type (hollow core, solid core), threshold detail.

### 10. Window (`CanonicalOpening` with `opening_type='WINDOW'`)
- **SOURCE:** Plan window marks, elevation drawings, window schedule.
- **IDENTITY:** Unique window mark (e.g. `W01`, `W-04`).
- **GEOMETRY:** Width ($m$), height ($m$), sill height ($m$).
- **PROVENANCE:** Window schedule row, elevation dimensions, plan vector markers.
- **RELATIONSHIPS:** Sub-kind of `CanonicalOpening`. Child of host `CanonicalWall`.
- **TAKEOFF CONSUMERS:** Window unit count (each), glazing area ($m^2$), window sills ($lm$), cavity closers/flashings ($lm$).
- **3D CONSUMERS:** 3D glazed window unit with mullions and frame.
- **MISSING FIELDS:** Number of sashes/panels, flyscreen requirement, reveal depth / plaster return details.

### 11. Ceiling (`CanonicalCeiling`)
- **SOURCE:** Reflected Ceiling Plan (RCP), room boundary projection (`pb_ceiling_lining_quantity.py`, `pb_live_primary_ceiling_integration.py`).
- **IDENTITY:** Deterministic ID: `ceiling_{level_id}_{space_id}`.
- **GEOMETRY:** `polygon` (`List[Vector2D]`), `thickness_m`, `elevation_offset_m` (height above FFL), `specified_floor_area_m2`.
- **PROVENANCE:** RCP plan sheet, room finish schedule ceiling tag.
- **RELATIONSHIPS:** Child of `CanonicalLevel`, paired with `CanonicalSpace`.
- **TAKEOFF CONSUMERS:** Ceiling plasterboard lining ($m^2$), ceiling battens / suspension grid ($m^2$), ceiling insulation ($m^2$), cornice ($lm$).
- **3D CONSUMERS:** Horizontal overhead ceiling plane mesh.
- **MISSING FIELDS:** Ceiling construction system (suspended grid, direct-fix metal batten, timber joist), ceiling drop/bulkhead transitions.

### 12. Roof (`CanonicalRoof`)
- **SOURCE:** Roof plan, elevation roof pitch annotations (`pb_phase5m_roof_closure.py`).
- **IDENTITY:** UUID or roof plane mark: `roof_{level_id}_{plane_idx}`.
- **GEOMETRY:** `polygon` (`List[Vector2D]`), `pitch_deg`, `overhang_m`, `roof_type` (hip, gable, skillion, flat), `elevation`.
- **PROVENANCE:** Roof plan sheet, elevation slope notes.
- **RELATIONSHIPS:** Child of `CanonicalLevel` (usually top level) or `CanonicalBuilding`.
- **TAKEOFF CONSUMERS:** True surface roofing area ($m^2$ factored by $\sec \theta$), ridge capping ($lm$), valley gutters ($lm$), barge/fascia ($lm$), roof insulation ($m^2$).
- **3D CONSUMERS:** Pitched planar facet solids in 3D viewer.
- **MISSING FIELDS:** Truss system vs rafter framing, roof drainage catchment zones, gutter and downpipe connections.

### 13. Beam (Structural Element)
- **SOURCE:** Structural engineering plans, beam schedules (`pb_structural_member_coverage_snapshot.py`).
- **IDENTITY:** Structural member mark (e.g. `B1`, `250UB31.4`, `GL8`).
- **GEOMETRY:** Start point $(x,y,z)$, end point $(x,y,z)$, section profile depth and width.
- **PROVENANCE:** Structural drawing sheet, schedule mark.
- **RELATIONSHIPS:** Associated with supporting `CanonicalColumn` or `CanonicalWall` objects.
- **TAKEOFF CONSUMERS:** Structural steel weight (tonnes), timber beam length ($lm$), reinforced concrete beam volume ($m^3$), beam formwork ($m^2$).
- **3D CONSUMERS:** 3D linear beam profile extrusion.
- **MISSING FIELDS:** First-class dataclass missing from `pb_canonical_building.py` (currently tracked only in shadow extractors).

### 14. Column (`CanonicalColumn`)
- **SOURCE:** Architectural grid, structural column schedule (`pb_column_detection_v150.py`).
- **IDENTITY:** Column mark (e.g. `C1`, `C02`, `COL_01`).
- **GEOMETRY:** `center` (`Vector2D`), `width_m`, `depth_m`, `height_m`.
- **PROVENANCE:** Structural drawing, column detail schedule.
- **RELATIONSHIPS:** Child of `CanonicalLevel`. Supports overhead beams and slabs.
- **TAKEOFF CONSUMERS:** Column concrete volume ($m^3$), column formwork ($m^2$), structural steel column weight (kg), finish paint ($m^2$).
- **3D CONSUMERS:** Vertical column prism mesh in 3D viewer.
- **MISSING FIELDS:** Column shape (circular, rectangular, universal column section), base plate and capital details.

### 15. Footing (Substructure Element)
- **SOURCE:** Foundation / footing plan (`pb_substructure_run_evidence.py`, `pb_dpc_substructure_authority.py`).
- **IDENTITY:** Footing mark (e.g. `F1`, `SF1`, `PAD_01`).
- **GEOMETRY:** Centerline path or pad boundary, width ($m$), depth ($m$).
- **PROVENANCE:** Foundation engineering plan.
- **RELATIONSHIPS:** Base foundation supporting `CanonicalWall`, `CanonicalColumn`, or `CanonicalFloor`.
- **TAKEOFF CONSUMERS:** Trench excavation ($m^3$), footing concrete ($m^3$), edge formwork ($m^2$), trench mesh ($lm$).
- **3D CONSUMERS:** Subterranean massing mesh.
- **MISSING FIELDS:** First-class dataclass in `pb_canonical_building.py` (needs `CanonicalFooting` with pad, strip, and pile classifications).

### 16. Stair (Vertical Circulation)
- **SOURCE:** Architectural floor plan stair flight, section drawings (`pb_editable_3d_model.py`).
- **IDENTITY:** Stair tag (e.g. `ST01`).
- **GEOMETRY:** Flight polygon, going length, rise height, number of risers/treads.
- **PROVENANCE:** Architectural plan and section.
- **RELATIONSHIPS:** Spans between consecutive `CanonicalLevel` entities.
- **TAKEOFF CONSUMERS:** Stair flights (count/each), stair treads and risers ($m^2$), stringers ($lm$), stair balustrade/handrail ($lm$).
- **3D CONSUMERS:** Stepped prism solid or sloped stair massing in 3D viewer.
- **MISSING FIELDS:** Dedicated `CanonicalStair` dataclass in `pb_canonical_building.py`.

### 17. Finish (`CanonicalFinishSurface`)
- **SOURCE:** Internal finish schedule, room callouts, specification document.
- **IDENTITY:** Material code or key (e.g. `P1`, `TL-01`, `CP-02`).
- **GEOMETRY:** Net surface area ($m^2$), substrate thickness ($m$).
- **PROVENANCE:** Room schedule table, elevation finish tag.
- **RELATIONSHIPS:** Bound to host `CanonicalWall`, `CanonicalFloor`, or `CanonicalCeiling`.
- **TAKEOFF CONSUMERS:** Trade-specific finish lines: Painting ($m^2$), Tiling ($m^2$), Carpet ($m^2$), Skirting ($lm$).
- **3D CONSUMERS:** Visual material appearance, PBR texture mapping.
- **MISSING FIELDS:** Waterproofing membrane specification, acoustic underlay specification.

### 18. Fixture (Architectural & MEP Fixture)
- **SOURCE:** Architectural joinery layout, hydraulic fixture legend (`pb_bim_viewer.py`).
- **IDENTITY:** Fixture code (e.g. `WC`, `BASIN`, `SINK`, `SHOWER_SCREEN`).
- **GEOMETRY:** Point location $(x,y,z)$, rotation, bounding envelope $(w,d,h)$.
- **PROVENANCE:** Floor plan fixture symbol detection, joinery schedule.
- **RELATIONSHIPS:** Located within `CanonicalSpace`, mounted on `CanonicalWall` or `CanonicalFloor`.
- **TAKEOFF CONSUMERS:** Fixture counts (each), rough-in supply/waste points (each), joinery lengths ($lm$).
- **3D CONSUMERS:** Parametric box or glTF fixture model in BIM viewer.
- **MISSING FIELDS:** Dedicated `CanonicalFixture` dataclass in `pb_canonical_building.py`.

### 19. Service (MEP Infrastructure)
- **SOURCE:** Electrical, mechanical, hydraulic service drawings.
- **IDENTITY:** Run mark or circuit/service ID (e.g. `HYD_COLD_01`, `ELEC_CKT_1A`).
- **GEOMETRY:** Polyline path $(x,y,z)$, nominal diameter / duct cross-section.
- **PROVENANCE:** Services drawing sheet, legend.
- **RELATIONSHIPS:** Traverses `CanonicalSpace`, penetrates `CanonicalWall` / `CanonicalFloor`.
- **TAKEOFF CONSUMERS:** Pipe / conduit lengths ($lm$), ductwork ($m^2$), service penetration fire collars (each).
- **3D CONSUMERS:** 3D extruded pipe/duct polyline paths.
- **MISSING FIELDS:** Dedicated `CanonicalServiceRun` dataclass in `pb_canonical_building.py`.

### 20. Structural Member (Generic Structural Skeleton)
- **SOURCE:** Structural framing plans (`pb_structural_member_coverage_snapshot.py`).
- **IDENTITY:** Member mark or structural section label.
- **GEOMETRY:** Axis curve, section designation, connection node coordinates.
- **PROVENANCE:** Engineering schedule, structural vector lines.
- **RELATIONSHIPS:** Connected to structural nodes and framing members.
- **TAKEOFF CONSUMERS:** Steel tonnage, timber volume, fastener/bracket counts.
- **3D CONSUMERS:** Structural frame skeleton in 3D BIM viewer.
- **MISSING FIELDS:** Promotion from shadow snapshot to core `pb_canonical_building.py` element.

### 21. Additional Pre-Existing Objects in Schema
- **Soffit (`CanonicalSoffit`):** Eaves lining, balcony soffits. 2D polygon with elevation offset. Consumed by external lining takeoff ($m^2$).
- **Balcony (`CanonicalBalcony`):** Projecting floor slab with waterproofing and balustrade relationships. Consumed by concrete, waterproofing, tiling.
- **Parapet (`CanonicalParapet`):** Perimeter roof barrier wall run with height and thickness. Consumed by framing, external cladding, metal capping.
- **Balustrade (`CanonicalBalustrade`):** Fall protection barrier. Start/End points and height. Consumed by metalwork/glazing ($lm$).
- **Screen (`CanonicalScreen`):** Architectural privacy or louvre screen. Consumed by carpentry/cladding ($m^2$, $lm$).
- **Evidence Observation (`CanonicalEvidenceObservation`):** Raw extracted OCR/vector observation prior to synthesis into physical objects. Critical for provenance.

---

## Synthesis of Missing Fields and Architectural Gap Analysis

1. **Substructure & Structural Gaps:**
   - `CanonicalFooting` and `CanonicalBeam` are not yet first-class dataclasses in `pb_canonical_building.py`. They exist as specialized shadow extractors or helper routines.
2. **Vertical Circulation Gaps:**
   - `CanonicalStair` is currently represented in editable 3D viewer helpers, but lacks a canonical dataclass with rise/going geometry.
3. **MEP & Fixtures Gaps:**
   - `CanonicalFixture` and `CanonicalServiceRun` are needed to natively bridge electrical and plumbing symbol counts into canonical building objects.
4. **Adjacency & Face Provenance:**
   - `CanonicalWall` needs explicit spatial adjacency (`left_space_id`, `right_space_id`) to directly synthesize inner/outer finish surfaces without downstream heuristic recalculation.

---

## Verification & Parity Sign-Off
- Audited against `pb_canonical_building.py` (v1.0 schema) and all 30 repository callers.
- Confirmed strict boolean and enum parsing via `test_3d_canonical_foundation.py` (12 passing tests).
- Confirmed compatibility with customer-runtime net-wall and opening parity harness (40 passing tests).
