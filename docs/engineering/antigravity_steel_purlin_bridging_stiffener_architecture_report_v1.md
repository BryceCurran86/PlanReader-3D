# Architecture Report: Source Structural Steel Purlin Bridging Hook Bolt & C-Section Stiffener Shadow Authority (v1)

## 1. Executive Summary
In structural steel roofing and industrial portal frame buildings, cold-formed Z-purlins and C-sections are slender structural elements vulnerable to torsional rolling and lateral-torsional buckling under aerodynamic suction and gravity loading. Proprietary bridging systems (complying with AS/NZS 4600) utilize roll-formed bridging channels connected through purlin webs via M12/M16 hook bolts or clamp brackets, anchored to eaves struts and ridge purlins. Capturing bridging lines, hook bolts, and web stiffeners provides key secondary structural geometry without compromising baseline customer takeoff integrity.

## 2. Geometry & Extraction Model
- **Bridging Assemblies**:
  - `HOOK_BOLT_CHANNEL_BRIDGING`: Cold-formed channel with hook bolts locking into prepunched purlin web slots.
  - `SOLID_STRUT_BRIDGING`: Heavy-duty tubular or angle compression bridging struts.
  - `EXPANSION_BRIDGING`: Slotted bridging channels accommodating thermal roof expansion.
- **Hook Bolt Sizing**: M10, M12, or M16 high-strength hooked bolts with flanged lock nuts.
- **Purlin Series Compatibility**: Standard section depths (C150, Z200, Z250, Z300).
- **Row Configuration**: Single row (spans up to 6m), two rows (spans up to 9m), or triple rows.
- **Protective Coating**: Z275 Galvabond or hot-dip galvanised finish.

## 3. Safe Shadow Architecture & Non-Negotiables
- Strict candidate shadow isolation: `status="CANDIDATE"`, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
- Hard safety cap enforced at 20,000 primitives.
- Geometric coordinate snapping at `SNAP_TOLERANCE_PT = 2.5`.
- Preserves customer retention baseline `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb` byte-for-byte.
