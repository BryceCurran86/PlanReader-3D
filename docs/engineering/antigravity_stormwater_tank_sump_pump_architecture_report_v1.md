# Architecture Report: Source Stormwater Retention Tank, Sump Pit & Submersible Pump Shadow Authority (v1)

## Executive Summary
Urban flood mitigation guidelines and municipal stormwater regulations mandate On-Site Detention (OSD) and retention storage tanks to attenuate peak rainfall runoff discharge into public stormwater mains. In multi-level subterranean basements below the gravity water table, stormwater and subsoil drainage collect into heavily reinforced concrete sump pits equipped with duplex alternating submersible vortex pumps to discharge water up to street council mains. Civil engineering plans and hydraulic plumbing schedules specify tank/pit geometry (length, width, depth, wall/base thickness), gross retention volume (m³), orifice control plates, and submersible pumping configurations.

This module introduces `SourceStormwaterTankSumpPumpShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for OSD retention tanks, basement drainage sump pits, gross detention capacity, pit structural concrete volume, and submersible pump hardware directly from civil and hydraulic foundation drawings.

## Domain Model & Stormwater Infrastructure Anatomy
1. **Facility Typology (`StormwaterFacilityType`)**:
   - `ON_SITE_DETENTION_OSD_TANK`: Below-ground detention vault with controlled orifice plate and overflow weir.
   - `RAINWATER_RETENTION_REUSE_TANK`: Storage tank collecting rainwater for toilet flushing, cooling tower makeup, or landscape irrigation.
   - `BASEMENT_DRAINAGE_SUMP_PIT`: Deep cast-in-place concrete sump pit receiving car park driveway runoff and subsoil perimeter drains.
   - `SURFACE_STORMWATER_CATCH_PIT`: Heavy-duty grated catch basin (e.g. 600x600, 900x900).
2. **Pumping System (`PumpingEquipmentConfig`)**:
   - `DUPLEX_SUBMERSIBLE_PUMPS`: Duty/standby paired pumps on guide rail brackets with automatic alternating float controls.
   - `SIMPLEX_SUMP_PUMP`: Single submersible utility pump for light-duty collection.
   - `GRAVITY_DISCHARGE`: Direct non-pumped gravity outflow.
3. **Traffic Loading Cover (`GrateCoverClass`)**:
   - `CLASS_D_HEAVY_DUTY`: 210 kN wheel load rating for roadway/delivery loading dock traffic.
   - `CLASS_B_LIGHT_VEHICLE`: 80 kN rating for residential car park spaces.
   - `SOLID_ALUMINIUM_GAS_TIGHT`: Sealed gas-tight access hatch over enclosed tanks.

## Mathematical Formulations
- **Net Storage Volume (\(V_{storage}\))**:
  \[
  V_{storage} = \sum_{i} \text{length}_i \cdot \text{width}_i \cdot \text{effective\_depth}_i
  \]
- **Pit Structure Concrete Volume (\(V_{conc}\))**:
  \[
  V_{conc} = \sum_{i} \left( (L_i + 2 t_{w, i}) \cdot (W_i + 2 t_{w, i}) \cdot (D_i + t_{b, i}) - L_i \cdot W_i \cdot D_i \right)
  \]
  where \(t_w\) is wall thickness (e.g. 0.20m–0.25m) and \(t_b\) is base slab thickness (e.g. 0.25m).
- **Submersible Pumps Takeoff (\(N_{pumps}\))**:
  \[
  N_{pumps} = \sum_{i \in \text{Duplex}} 2 + \sum_{j \in \text{Simplex}} 1
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for pit/tank center coordinates and footprint polygons.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
