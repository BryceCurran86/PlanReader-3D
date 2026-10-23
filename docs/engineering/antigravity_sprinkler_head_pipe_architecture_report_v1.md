# Architecture Report: Source Fire Suppression Automatic Sprinkler Head & Distribution Range Pipe Shadow Authority (v1)

## Executive Summary
Life-safety active fire suppression systems installed pursuant to NFPA 13, AS 2118.1, and EN 12845 incorporate gridded networks of automatic fire sprinkler heads connected by hydraulic steel distribution range pipes and branch mains. Fire protection plans schedule sprinkler head hardware detailing discharge orientation (concealed pendent for architectural finished ceilings, exposed upright heads for open carparks/soffits, horizontal sidewall heads, and high-density ESFR warehouse heads), nominal discharge orifice K-factor (K80, K115, K160, K360 metric), bulb response temperature ratings (68°C standard red bulb), and range pipe nominal diameters (DN25 to DN100).

This module introduces `SourceSprinklerHeadPipeShadowAuthority`, providing an authoritative shadow-mode extraction and quantification framework for sprinkler head node locations, K-factor schedules, and distribution range pipe linear takeoff directly from hydraulic fire protection layout drawings.

## Domain Model & Sprinkler Network Anatomy
1. **Sprinkler Head Orientation (`SprinklerOrientation`)**:
   - `PENDENT_CONCEALED`: Flush ceiling cover plate with solder-drop release protecting commercial offices and hotel suites.
   - `PENDENT_STANDARD`: Drop pendent head with deflector plate directed downwards.
   - `UPRIGHT`: Upward directed head mounted above pipe centerline to prevent sediment accumulation and protect open structural beams.
   - `SIDEWALL_HORIZONTAL`: Wall-mounted horizontal discharge deflector for narrow corridors or where ceiling pipe drops are restricted.
   - `ESFR_HIGH_BAY`: Early Suppression Fast Response large-orifice pendent head for high-piled palletized warehouse storage.
2. **K-Factor Discharge Capacity (`k_factor_metric`)**:
   - Standard K80 (imperial K5.6), K115 (K8.0), K160 (K11.2), K242 (K16.8), or K360 (K25.2).
3. **Response Temperature (`temperature_rating_c`)**:
   - 68°C (red liquid bulb, standard ambient rooms), 79°C (yellow), 93°C (green), 141°C (blue).
4. **Distribution Range Pipework (`nominal_dia_dn`, `pipe_length_m`)**:
   - Medium/heavy wall black steel or galvanized pipe spanning from distribution sub-mains to individual head drops (DN25, DN32, DN40, DN50, DN65, DN80, DN100).

## Mathematical Formulations
- **Total Sprinkler Heads Count (\(N_{heads}\))**:
  \[
  N_{heads} = \sum_{i} 1
  \]
- **Sprinkler Heads by Type & K-Factor (\(N_{type, K}\))**:
  \[
  N_{type, K} = \sum_{i \in \text{Type}(t) \cap K(k)} 1
  \]
- **Total Range Pipe Linear Run (\(L_{pipe}\))**:
  \[
  L_{pipe} = \sum_{j} \text{Length}(\text{centerline}_j)
  \]
- **Range Pipe Linear Run by Diameter (\(L_{DN}\))**:
  \[
  L_{DN} = \sum_{j \in \text{Diameter}(DN)} \text{Length}(\text{centerline}_j)
  \]

## Safety & Governance Invariants
- **Candidate Mode Only**: `status = "CANDIDATE"`, `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- **Global Snap Tolerance**: 2.5 pt tolerance for head insertion points, pipe junctions, and tee intersections.
- **Zero Gold Dependency**: Pure deterministic geometric calculation without hardcoded heuristic offsets.
- **Customer Baseline Preservation**: Guarantees zero regression on baseline customer retention test suite.
