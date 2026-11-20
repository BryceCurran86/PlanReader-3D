import type { CatalogueItem, FixtureShape, ItemTarget } from "./itemCatalogue.ts";

type Service = "plumbing-rough-in" | "electrical-rough-in" | "air-conditioning";
type Family = readonly [key: string, name: string, target: ItemTarget, shape: FixtureShape, sizes: readonly [number, number, number], variants: readonly string[]];

// Display dimensions size the coordination markers. They do not size the installed trade system.
const plumbing: Family[] = [
  ["cold-hot", "Water supply point", "wall", "outdoor-tap", [0.12, 0.12, 0.06], ["Cold water", "Hot water", "Hot and cold"]],
  ["waste", "Waste connection", "wall", "port", [0.12, 0.14, 0.06], ["Basin", "Sink", "Laundry", "Wall-hung WC"]],
  ["floor-waste", "Floor waste", "floor", "downlight", [0.12, 0.12, 0.035], ["Shower", "Bathroom", "Laundry"]],
  ["supply", "Plumbing fixture rough-in", "wall", "socket", [0.14, 0.14, 0.05], ["Bath", "Mixer", "Dishwasher", "Washing machine"]],
  ["vent", "Drainage vent point", "ceiling", "downlight", [0.15, 0.15, 0.06], ["Vertical vent", "Air admittance valve"]],
];
const electrical: Family[] = [
  ["outlet", "Power outlet rough-in", "wall", "socket", [0.12, 0.09, 0.04], ["Single", "Double", "Dedicated circuit", "Weatherproof"]],
  ["switch", "Switch rough-in", "wall", "switch", [0.12, 0.09, 0.04], ["Single gang", "Double gang", "Three gang"]],
  ["lighting", "Ceiling point rough-in", "ceiling", "downlight", [0.14, 0.14, 0.05], ["Light", "Ceiling fan", "Smoke alarm"]],
  ["data", "Communications rough-in", "wall", "port", [0.12, 0.09, 0.04], ["Data", "TV", "Security"]],
  ["supply", "Equipment supply point", "wall", "isolator", [0.14, 0.14, 0.05], ["Cooktop", "Oven", "Hot water", "A/C isolator"]],
  ["board", "Switchboard location", "wall", "isolator", [0.28, 0.32, 0.06], ["Main board", "Sub-board"]],
];
const cooling: Family[] = [
  ["split", "Wall-mounted split system", "wall", "service-box", [0.85, 0.28, 0.15], ["Reverse cycle", "Cooling only", "Multi-split indoor unit"]],
  ["console", "Floor console split system", "floor", "service-box", [0.68, 0.54, 0.17], ["Reverse cycle", "Multi-split indoor unit"]],
  ["ducted", "Ducted indoor unit", "ceiling", "service-box", [0.82, 0.48, 0.22], ["Reverse cycle", "Slimline bulkhead", "VRF indoor unit"]],
  ["cassette", "Ceiling cassette", "ceiling", "service-box", [0.55, 0.55, 0.11], ["One-way", "Four-way"]],
  ["outdoor", "Outdoor A/C unit", "floor", "service-box", [0.72, 0.56, 0.23], ["Single split", "Multi-split", "Ducted", "VRF"]],
  ["air", "Air grille rough-in", "ceiling", "service-box", [0.30, 0.18, 0.05], ["Supply grille", "Return grille", "Exhaust grille"]],
  ["lines", "Refrigerant and condensate point", "wall", "port", [0.14, 0.13, 0.05], ["Refrigerant pair", "Condensate drain", "Combined"]],
  ["control", "A/C control rough-in", "wall", "switch", [0.12, 0.10, 0.04], ["Wall controller", "Zone controller"]],
];

function identify(group: Service, families: Family[], color: number): CatalogueItem[] {
  return families.flatMap(([key, name, target, shape, [widthM, heightM, depthM], variants]) =>
    variants.map((variant, index) => ({
      id: group + "-" + key + "-" + (index + 1), group, label: name + " · " + variant,
      targets: [target], keywords: "rough in rough-in services coordination " + group,
      visual: { kind: "fixture", shape, widthM, heightM, depthM, color, count: 1, metalness: 0.05 },
    })));
}
export const ROUGH_IN_CATALOGUE = [
  ...identify("plumbing-rough-in", plumbing, 0x4fc8ff),
  ...identify("electrical-rough-in", electrical, 0xf9c451),
  ...identify("air-conditioning", cooling, 0x50d5a0),
];
