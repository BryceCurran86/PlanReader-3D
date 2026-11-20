const housing = "https://ncc.abcb.gov.au/system/files/ncc/ncc2022-combined-vol2-housing-provisions-20230501b.pdf";
const plumbing = "https://ncc.abcb.gov.au/sites/default/files/resources/2025/ncc2022-volume-three.pdf";

export const NCC_ADOPTION = "https://www.business.qld.gov.au/industries/building-property-development/building-construction/laws-codes-standards/building";
export const NCC_REFERENCES = "https://ncc.abcb.gov.au/editions-national-construction-code";
export const CONSTRUCTION_REFERENCES = [
  {
    area: "Slab and footings", scope: "NCC Volume Two H1D4 and Housing Provisions Section 4",
    documents: "AS 2870 residential slabs and footings. AS 3600 concrete structures where specified.",
    evidence: "Geotechnical classification, structural slab drawing and reinforcement details.", url: housing,
  },
  {
    area: "Wall, roof and ceiling framing", scope: "NCC Volume Two H1D6 and Housing Provisions Section 6",
    documents: "AS 1684 series for timber framing. AS 1720.1 for structural timber design. NASH Standard for residential and low-rise steel framing.",
    evidence: "Framing design, load paths, wind classification, bracing and tie-down details.", url: housing,
  },
  {
    area: "Door and frame openings", scope: "NCC Volume Two H1 and H2, and applicable access provisions",
    documents: "AS 2047 for external glazing assemblies within scope. AS 1288 for glass selection and installation where applicable.",
    evidence: "Approved opening schedule, structural supports, weatherproofing and access details.", url: housing,
  },
  {
    area: "Roof covering, fascia and flashing", scope: "NCC Volume Two H1D7, H2 and Housing Provisions Parts 7.2–7.3",
    documents: "AS 1562.1 for applicable metal sheet roof and wall cladding. AS 2050 and AS 2049 for roof tile installation and products.",
    evidence: "Roof and junction details, wind exposure, drainage paths and product installation information.", url: housing,
  },
  {
    area: "Gutters and stormwater", scope: "NCC Volume Two H2D6, Housing Provisions Part 7.4 and Volume Three",
    documents: "AS/NZS 3500.3 for relevant stormwater drainage design.",
    evidence: "Catchment areas, rainfall data, gutter capacity, overflow and downpipe design.", url: housing,
  },
  {
    area: "Plumbing rough-in", scope: "NCC Volume Three",
    documents: "AS/NZS 3500.1 water services, .2 sanitary plumbing and drainage, .3 stormwater, .4 heated water.",
    evidence: "Approved services layout and inspection evidence for the relevant connection.", url: plumbing,
  },
  {
    area: "Electrical rough-in", scope: "State or territory electrical safety rules",
    documents: "AS/NZS 3000 Wiring Rules, including applicable amendments.",
    evidence: "Electrical design and licensed installation, inspection and testing records.",
    url: "https://www.worksafe.qld.gov.au/__data/assets/pdf_file/0020/17534/38-wiring-rules-handout.pdf",
  },
  {
    area: "Air conditioning and ventilation", scope: "Applicable NCC ventilation and ductwork provisions",
    documents: "AS 1668.2 mechanical ventilation. AS 4254 series for applicable ductwork. Refrigeration safety and licensing requirements depend on the system.",
    evidence: "Mechanical design, equipment instructions, structural support, penetrations and condensate discharge details.",
    url: "https://ncc.abcb.gov.au/sites/default/files/resources/2025/ncc2022-volume-one.pdf",
  },
  {
    area: "Stairs and balustrades", scope: "NCC Volume Two Part H5 and Housing Provisions Section 11",
    documents: "Stair, ramp, barrier and handrail provisions. AS 1288 for applicable glazed assemblies.",
    evidence: "Stair geometry, landings, falls, barrier design and glazing details.", url: housing,
  },
  {
    area: "Windows, glazed sliders and coverings", scope: "NCC Volume Two H1D8, with applicable fall and access provisions",
    documents: "AS 2047 and AS 1288 where the glazing product and use fall within scope.",
    evidence: "Window and door schedule, glazing, safety, opening restriction and product details.", url: housing,
  },
  {
    area: "Patio flyovers and landscaping structures", scope: "NCC structural provisions and applicable site requirements",
    documents: "AS/NZS 1170.2 or AS 4055 where applicable for wind actions. Confirm the structural design pathway.",
    evidence: "Engineered supports and connections, site levels, retaining and drainage designs.", url: housing,
  },
  {
    area: "Swimming pools and spas", scope: "NCC and the applicable state or territory pool safety rules",
    documents: "Confirm the barrier standard, applicable AS 1926 documents and local variations with the pool certifier.",
    evidence: "Pool and barrier layout, gates, clearances, approvals and inspection evidence.",
    url: "https://www.qbcc.qld.gov.au/home-owner-hub/swimming-pools/pool-safety-standard",
  },
  {
    area: "Gypsum linings and ceilings", scope: "Applicable support, lining and fire or acoustic assembly requirements",
    documents: "AS/NZS 2589 for gypsum lining application and finishing.",
    evidence: "Ceiling system specification, fixing and support details and any required rated assembly evidence.",
    url: "https://store.standards.org.au/product/as-nzs-2589-2017-amd-2-2021",
  },
] as const;
