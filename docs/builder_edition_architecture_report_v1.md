# Builder Edition Architecture & Multi-Trade Aggregator Report v1 (AG-30)

## 1. Executive Summary

As part of **AG-30 (Builder Edition Architecture)**, PlanReader-3D introduces the multi-trade commercial aggregation engine that unifies all specialized trade authorities (`AG-21` through `AG-29`) and architectural finishes into a cohesive, commercial-grade Bill of Quantities (BoQ), pricing engine, and project health audit system.

The Builder Edition architecture bridges the gap between atomic trade takeoff rows (adhering strictly to the 21-field SQLite contract) and whole-of-project commercial builder estimates, tenders, and construction cost plans.

---

## 2. 11 Master Trade Package Classification

PlanReader's master trade taxonomy organizes all project scope into 11 canonical trade packages:

| Code | Trade Package Name | Scope & Authority Coverage | Primary Units |
|---|---|---|---|
| `01_substructure` | Substructure & Groundworks | Slab on ground, strip/pad footings, bored piers, DPM/sand blinding (`AG-21`) | m², item, lm |
| `02_concrete_formwork` | Concrete & Formwork | Suspended slabs, beams, columns, stairs, soffit & edge formwork (`AG-21`, `AG-22`) | m², item, lm |
| `03_post_tensioning` | Post-Tensioning & Stressing | PT slabs, 1860 MPa 12.7mm strand mass, ducting, live/dead anchorages, stressing, grouting (`AG-23`) | item, No. |
| `04_structural_steel` | Structural Steel & Metalwork | UB/WB beams, UC/SHS columns, purlins, girts, bracing, connection tonnage allowance, protective coatings (`AG-24`) | lm, item, m² |
| `05_masonry` | Masonry, Brickwork & Blockwork | Face brick veneer, cavity ties, DPC flashings, 100/150/200mm core-filled blockwork, bond beams, lintels (`AG-25`) | m², No., lm |
| `06_carpentry` | Carpentry & Timber Framing | 90x45 wall frames, bottom/top plates, studs @ 450, noggings, floor joists, roof trusses, battens, weatherboards, eaves (`AG-27`) | m², lm |
| `07_flooring_tiling` | Flooring, Screeding & Tiling | Engineered timber, underlay, quads, carpet, porcelain tiles, sand/cement screeds to falls, liquid waterproofing upturns (`AG-26`) | m², lm |
| `08_linings_plasterboard` | Internal Linings & Plasterboard | Wall & ceiling plasterboard linings, cornices, bulkheads, reveal beads | m², lm |
| `09_painting` | Painting & Protective Finishes | Internal/external paint coats, primer/sealer, enamel trims, protective coatings | m², lm |
| `10_plumbing_drainage` | Plumbing, Drainage & Wet Services | Sanitary fixtures, rough-in points, 100mm DWV sewer pipework, inspection openings, hot/cold PEX reticulation, acoustic lagging stacks (`AG-28`) | No., lm |
| `11_electrical_comms` | Electrical, Lighting & Communications | Distribution switchboards, luminaires, emergency/exit lights, switches, double GPOs, dedicated circuits, Cat6 data, cable tray (`AG-29`) | No., lm |

---

## 3. Commercial Pricing Engine

The commercial pricing engine executes deterministic builder margin and on-cost calculations:

$$\text{Direct Cost Subtotal} = \sum (\text{Quantity} \times \text{Rate per Unit})$$

$$\text{Preliminaries Amount} = \text{Direct Cost Subtotal} \times \frac{\text{Preliminaries \%}}{100}$$

$$\text{Contingency Amount} = \text{Direct Cost Subtotal} \times \frac{\text{Contingency \%}}{100}$$

$$\text{Base Cost with Overheads} = \text{Direct Cost Subtotal} + \text{Preliminaries Amount} + \text{Contingency Amount}$$

$$\text{Builder Margin Amount} = \text{Base Cost with Overheads} \times \frac{\text{Builder Margin \%}}{100}$$

$$\text{Grand Total Contract Sum} = \text{Base Cost with Overheads} + \text{Builder Margin Amount}$$

### Default Commercial Rates
- **Preliminaries:** $8.0\%$ (site establishment, supervision, temporary services, scaffolding, waste management)
- **Contingency:** $5.0\%$ (latent conditions, design development allowance)
- **Builder Margin:** $15.0\%$ (builder overhead and profit)

---

## 4. Bill of Quantities (BoQ) Hierarchical Export

The engine generates standard CSV and JSON Bill of Quantities formats:
1. **Header Row:** Item No, Package Code, Section, Element, Location, Substrate, Quantity, Unit, Rate, Direct Cost, Quantity Status, Inclusion, Confidence, Notes, Source Reference.
2. **Trade Package Groupings:** Grouped by package code (`01_substructure` through `11_electrical_comms`) with subtotal lines per trade.
3. **Summary Section:**
   - Direct Cost Subtotal
   - Preliminaries ($8\%$)
   - Contingency ($5\%$)
   - Builder Margin ($15\%$)
   - Grand Total Contract Sum

---

## 5. Project Health & Completeness Audit Dashboard

The project health audit evaluates four key dimensions:
1. **Pricing Completeness %:** Percentage of line items with a non-zero unit rate assigned.
2. **Readiness Score %:** Composite metric incorporating measurement certainty (measured vs provisional), pricing coverage, and trade package diversity.
3. **Provisional Quantity Ratio:** Identifies unmeasured or estimated quantities exceeding safe risk thresholds ($> 20\%$).
4. **Automated Risk Warnings:** Highlights unpriced items, missing packages, zero-quantity entries, and unallocated trades.

---

## 6. Contract Compliance & Verification

- **21-Field Core Contract:** Strictly maintained in SQLite database table `takeoff_rows` with unit set restricted to `('m²', 'lm', 'No.', 'item', 'L', 'allowance')`.
- **Zero Hallucination / Zero Benchmark Alteration:** No modifications to benchmark golden files, expected values, tolerances, or scoring rules.
- **Unit Test Suite:** Validated in `tests/test_builder_edition_architecture.py` across 5 comprehensive test cases covering:
  1. Composite trade package classification across 11 master disciplines.
  2. Commercial pricing engine arithmetic and margin cascading.
  3. BoQ CSV hierarchical export generation and section formatting.
  4. Project health and completeness audit scoring and warning detection.
  5. SQLite 21-field core contract round-trip insertion and querying.
