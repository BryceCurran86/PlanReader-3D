# Architecture Report: Source Penetration Firestop Collar & Intumescent Pipe Wrap Shadow Authority (v1)

## Executive Summary
Passive fire containment systems require penetration seals wherever plumbing, drainage, HVAC, and electrical services breach fire-rated floor slabs, ceilings, or compartment walls. Combustible drainage pipes (e.g. 100mm PVC stack pipes, HDPE stormwater, insulated refrigerant copper pairs) melt rapidly under fire exposure, leaving an open flume unless crushed shut by high-expansion intumescent material. Hydraulic and passive fire protection drawings schedule firestop assemblies detailing device typology (cast-in slab collar, retrofit surface-mounted collar, intumescent annular wrap, fire mastic sealant), pipe diameter (e.g. 50mm, 65mm, 100mm, 150mm), and fire resistance level (e.g. 2-hr, 3-hr, 4-hr).

This module introduces `SourceFirestopCollarWrapShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for penetration firestop collars, intumescent wraps, diameter sizing, and barrier rating schedules directly from hydraulic and fire compartment plans.

## Domain Model & Firestop Anatomy
1. **Firestop Device Type (`FirestopDeviceType`)**:
   - `CAST_IN_COLLAR`: Preset plastic/metal collar embedded in concrete slab during formwork before pour.
   - `SURFACE_FIRE_COLLAR`: Retrofit steel casing bolted to slab soffit or wall partition face around existing pipe.
   - `INTUMESCENT_PIPE_WRAP`: Flexible intumescent graphite wrap tucked into the core hole annular space.
   - `FIRE_PILLOW_TRANSIT`: Modular intumescent bags or elastomeric transit frames for grouped cable/pipe bundles.
2. **Pipe Material (`PipeMaterialType`)**:
   - `PVC_DWV`: Polyvinyl chloride drain, waste, and vent pipe.
   - `HDPE_DRAIN`: High-density polyethylene drainage or trade waste pipe.
   - `POLYPROPYLENE`: Acoustic polypropylene soil pipe.
   - `COPPER_INSULATED`: Insulated refrigeration / chilled water pipe.
3. **Barrier Rating (`fire_rating_hours`)**:
   - Tested fire resistance levels (FRL): typically 1-hr (-/60/60), 2-hr (-/120/120), 3-hr (-/180/180), or 4-hr (-/240/240).

## Mathematical Formulations
- **Total Firestop Units Count (\(N_{devices}\))**:
  \[
  N_{devices} = \sum_{i} 1
  \]
- **Device Count by Diameter (\(N_{D}\))**:
  \[
  N_{D} = \sum_{i \in \text{Diameter}(D)} 1
  \]
- **Total Intumescent Compound Volume Estimate (\(V_{intum}\))**:
  \[
  V_{intum} = \sum_{i} \pi \cdot \left(\left(\frac{D_i + 2 \cdot t_{c, i}}{2000}\right)^2 - \left(\frac{D_i}{2000}\right)^2\right) \cdot H_{c, i}
  \]
  where \(D_i\) is pipe outer diameter, \(t_{c, i}\) is intumescent casing thickness, and \(H_{c, i}\) is collar casing height.

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for penetration coordinates and wall/slab intersections.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
