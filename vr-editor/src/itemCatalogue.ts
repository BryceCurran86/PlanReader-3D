import { EXTERIOR_CATALOGUE } from "./exteriorCatalogue.ts";
import { EXTENSION_CATALOGUE } from "./extensionCatalogue.ts";
import { ROOF_COMPONENTS } from "./roofComponents.ts";
import { ROUGH_IN_CATALOGUE } from "./roughInCatalogue.ts";

export const CATALOGUE_GROUPS = [
  ["paint", "Paint"], ["boards", "Plasterboard"], ["skirting", "Skirting"],
  ["architraves", "Architraves"], ["floors", "Floor coverings"], ["walls", "Wall coverings"],
  ["tapware", "Tapware"], ["electrical", "Electrical points"], ["lights", "Lighting"],
  ["bathroom", "Bathroom fixtures"], ["cabinets", "Cabinetry"], ["doors", "Door finishes"],
  ["timber", "Timber profiles"], ["entry", "Front doors"], ["substrates", "Exterior substrates"],
  ["facades", "Exterior wall finishes"], ["decking", "Decking and paving"], ["soffits", "Soffits and eaves"],
  ["roofing", "Roof finishes"], ["roof-components", "Roof components"],
  ["plumbing-rough-in", "Plumbing rough-in"], ["electrical-rough-in", "Electrical rough-in"],
  ["air-conditioning", "Air conditioning"],
  ["stairs", "Stairs"], ["balustrading", "Balustrading"], ["sliding-doors", "Sliding doors"],
  ["windows", "Windows"], ["window-coverings", "Curtains and blinds"],
  ["flyovers", "Patio flyovers"], ["pools", "Pools and spas"], ["landscaping", "Landscaping"], ["furniture","Furniture"],
] as const;
export type CatalogueGroup = typeof CATALOGUE_GROUPS[number][0];
export type ItemTarget = "wall" | "floor" | "ceiling" | "roof" | "opening" | "worktop" | "site";
export type Pattern = "solid" | "grain" | "plank" | "tile" | "woven" | "fleck" | "rib" |
  "masonry" | "lap" | "seam" | "sheet" | "corrugation" | "profiled-tile";
export type TrimProfile = "square" | "pencil" | "bullnose" | "splay" | "step" | "ogee" | "colonial" | "lamb";
export type FixtureShape =
  | "mixer" | "gooseneck" | "square-spout" | "wall-spout" | "outdoor-tap" | "shower"
  | "socket" | "switch" | "port" | "isolator" | "alarm"
  | "downlight" | "batten" | "pendant" | "sconce" | "fan"
  | "basin" | "toilet" | "bath" | "vanity" | "cabinet" | "bench" | "rail" | "service-box"
  | "sofa" | "bed" | "coffee-table";

type SurfaceVisual = { kind: "surface"; slot: "finish" | "lining"; pattern: Pattern;
  color: number; roughness: number; repeatM?: readonly [number, number] };
type TrimVisual = { kind: "trim"; profile: TrimProfile; widthM: number; depthM: number; color: number };
type FixtureVisual = { kind: "fixture"; shape: FixtureShape; widthM: number; heightM: number; depthM: number;
  color: number; count: number; metalness: number };
export type TimberProfile = "square" | "eased" | "bullnose" | "chamfer" | "rebate" |
  "shiplap" | "v-joint" | "bevelback" | "half-round";
export type TimberVisual = { kind: "timber"; profile: TimberProfile; mount: "face" | "post";
  widthM: number; depthM: number; lengthM: number; color: number; grain: number };
export type EntryStyle = "flush" | "shaker" | "craftsman" | "vertical-lite" | "strip-lite" |
  "full-lite" | "batten" | "arched-lite" | "double" | "sidelight" | "pivot";
export type EntryVisual = { kind: "entry"; style: EntryStyle; minWidthM: number; minHeightM: number;
  color: number; grain: number | null };
export type RoofComponentVisual = { kind: "roof-component"; component: "gutter" | "fascia" | "flashing";
  profile: "quad" | "half-round" | "square" | "eaves" | "barge" | "apron" | "ridge" | "valley"; color: number };
export type OpeningStyle = { kind: "opening-style"; type: "door" | "window" | "covering";
  style: "slider" | "stacker" | "wide-stacker" | "lift-slide" | "cavity" | "barn" | "bypass" |
    "fixed" | "awning" | "casement" | "double-hung" | "louvre" | "bifold" |
    "curtain" | "sheer" | "roller" | "roman" | "venetian" | "vertical" | "shutter"; color: number };
export type DesignAssembly = { kind: "design-assembly";
  shape: "straight-stair" | "l-stair" | "u-stair" | "spiral-stair" | "glass-rail" | "picket-rail" | "wire-rail" |
    "skillion" | "gable" | "insulated" | "rectangle-pool" | "rounded-pool" | "lawn" | "stepping" |
    "garden" | "hedge" | "tree" | "retaining";
  widthM: number; heightM: number; depthM: number; color: number };
export type ItemVisual = SurfaceVisual | TrimVisual | FixtureVisual | TimberVisual | EntryVisual |
  RoofComponentVisual | OpeningStyle | DesignAssembly;
export type CatalogueItem = {
  id: string;
  group: CatalogueGroup;
  label: string;
  targets: readonly ItemTarget[];
  keywords: string;
  visual: ItemVisual;
};

const colours = [
  ["Chalk White", 0xf4f0e6], ["Cotton White", 0xeeeae2], ["Paper White", 0xf8f5ed],
  ["Ivory", 0xe9ddbf], ["Linen", 0xe5d6bc], ["Oatmeal", 0xc9b69a],
  ["Sandstone", 0xc1a987], ["Bone", 0xcac2ad], ["Warm Stone", 0xa9a096],
  ["Putty", 0xb6a797], ["Mushroom", 0x9a887b], ["Mocha", 0x68564a],
  ["Pale Grey", 0xd3d6d3], ["Dove Grey", 0xa7adae], ["Silver Mist", 0x8e9ca2],
  ["Slate Grey", 0x586773], ["Graphite", 0x45494b], ["Charcoal", 0x31363a],
  ["Ink", 0x252831], ["Soft Black", 0x252625], ["Terracotta", 0xb46b55],
  ["Clay", 0x9a5846], ["Burnt Umber", 0x754433], ["Brick Red", 0x933a35],
  ["Blush", 0xe0bab3], ["Dusty Rose", 0xb17f82], ["Plum", 0x694b67],
  ["Lilac", 0xb0a0bf], ["Shell Pink", 0xf1d5cc], ["Apricot", 0xe1a477],
  ["Butter", 0xe8d997], ["Mustard", 0xb9903d], ["Ochre", 0xac7644],
  ["Pale Mint", 0xc1d7c7], ["Eucalyptus", 0x8da29a], ["Sage", 0x96a28d],
  ["Olive", 0x6f7650], ["Moss", 0x5f6a50], ["Fern", 0x42745b],
  ["Forest", 0x2d5448], ["Bottle Green", 0x24473e], ["Sea Glass", 0x82aeb1],
  ["Deep Teal", 0x23646a], ["Powder Blue", 0xa5bfd2], ["Cloud Blue", 0x83a0b1],
  ["Denim", 0x537892], ["Cobalt", 0x34569b], ["Navy", 0x283c59],
] as const;
const sheens = [["Flat", 0.95], ["Low sheen", 0.72], ["Satin", 0.44], ["Semi-gloss", 0.23]] as const;
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-$/, "");

function surface(group: CatalogueGroup, label: string, targets: readonly ItemTarget[], color: number,
  pattern: Pattern, roughness: number, repeatM?: readonly [number, number],
  slot: SurfaceVisual["slot"] = "finish", keywords = ""): CatalogueItem {
  return { id: group + "-" + slug(label), group, label, targets, keywords,
    visual: { kind: "surface", slot, color, pattern, roughness, repeatM } };
}

const paint = colours.flatMap(([name, color]) => sheens.map(([sheen, roughness]) =>
  surface("paint", name + " · " + sheen, ["wall", "ceiling"], color, "solid", roughness,
    undefined, "finish", "colour color paint interior")));

const boards = [
  ["Standard plasterboard", [10, 13], 0xe2ddcf],
  ["Ceiling plasterboard", [10, 13], 0xece6d7],
  ["Moisture-resistant plasterboard", [10, 13], 0xb5cbb6],
  ["Fire-resistant plasterboard", [13, 16], 0xd9b7ad],
  ["Acoustic plasterboard", [13, 16], 0xc4c6ce],
  ["Impact-resistant plasterboard", [13, 16], 0xd8cbad],
  ["Flexible plasterboard", [6.5], 0xe1daca],
  ["Perforated acoustic plasterboard", [12.5], 0xd5d1c5],
] as const;
const plasterboard = boards.flatMap(([label, gauges, color]) => gauges.map(gauge =>
  surface("boards", label + " · " + gauge + " mm",
    label.startsWith("Ceiling") ? ["ceiling"] : ["wall", "ceiling"], color,
    label.startsWith("Perforated") ? "fleck" : "solid", 0.94,
    undefined, "lining", "gypsum drywall lining sheet board")));

const trimProfiles = [
  ["Square edge", "square"], ["Pencil round", "pencil"], ["Bullnose", "bullnose"],
  ["Splayed", "splay"], ["Stepped", "step"], ["Ogee", "ogee"], ["Colonial", "colonial"],
  ["Lamb's tongue", "lamb"],
] as const;
const trims = [
  { group: "skirting", target: "wall", sizes: [67, 92, 112, 138, 185] },
  { group: "architraves", target: "opening", sizes: [42, 66, 90, 115] },
] as const;
const trimItems: CatalogueItem[] = trims.flatMap(({ group, target, sizes }) =>
  trimProfiles.flatMap(([name, profile]) => Array.from(sizes, (width): CatalogueItem => ({
    id: group + "-" + profile + "-" + width, group, label: name + " · " + width + " mm",
    targets: [target], keywords: "trim profile primed moulding molding architrave baseboard jamb",
    visual: { kind: "trim", profile, widthM: width / 1000, depthM: width >= 100 ? 0.018 : 0.015, color: 0xe8e4d9 },
  }))));

type CoveringFamily = readonly [string, Pattern, readonly [number, number], number,
  readonly (readonly [string, number])[]];
const floorFamilies: CoveringFamily[] = [
  ["Engineered timber", "plank", [0.19, 1.8], 0.55, [["Natural Oak", 0xad8558], ["Smoked Oak", 0x72583f], ["Blackbutt", 0xa48054], ["Walnut", 0x654633], ["Limed Oak", 0xd0bf9f]]],
  ["Solid timber", "plank", [0.13, 1.6], 0.52, [["Spotted Gum", 0x9b7657], ["Tasmanian Oak", 0xc6a279], ["Jarrah", 0x795248], ["Cypress", 0xcba572]]],
  ["Laminate plank", "plank", [0.2, 1.3], 0.62, [["Honey Oak", 0xb89264], ["Grey Ash", 0xa5a29a], ["Dark Walnut", 0x685143], ["Whitewashed Pine", 0xd6c9b2]]],
  ["Hybrid plank", "plank", [0.18, 1.45], 0.65, [["Coastal Oak", 0xc3ad8e], ["Natural Ash", 0xb3a187], ["Driftwood", 0x988d7f], ["Warm Gum", 0x9e7853]]],
  ["Vinyl plank", "plank", [0.18, 1.22], 0.71, [["Blond Oak", 0xbdaa8d], ["Brown Oak", 0x927152], ["Grey Timber", 0x8b8c88], ["Pale Elm", 0xc9baa2]]],
  ["Sheet vinyl", "fleck", [0.08, 0.08], 0.63, [["Sand", 0xbab3a0], ["Pebble", 0xa1a9a8], ["Grey", 0x73787b], ["Sky", 0x748f9b]]],
  ["Porcelain tile 600 × 600", "tile", [0.6, 0.6], 0.53, [["Warm White", 0xe4ddd0], ["Bone", 0xcbc4b7], ["Ash", 0x9b9f9e], ["Charcoal", 0x4b4d4e], ["Travertine Look", 0xc5b191]]],
  ["Porcelain tile 300 × 600", "tile", [0.3, 0.6], 0.57, [["Dune", 0xc8b9a3], ["Smoke", 0x929596], ["Graphite", 0x494d52]]],
  ["Mosaic tile 50 × 50", "tile", [0.05, 0.05], 0.55, [["Cream", 0xe3d6ba], ["Sea Green", 0x8da49a], ["Ink", 0x3d4b52]]],
  ["Loop pile carpet", "woven", [0.07, 0.07], 0.98, [["Hessian", 0x93816c], ["Mist", 0xb3b1aa], ["Granite", 0x646568], ["Ink", 0x414955]]],
  ["Cut pile carpet", "woven", [0.03, 0.03], 0.99, [["Linen", 0xa99d89], ["Fawn", 0xa98f76], ["Cinder", 0x686764], ["Soft Blue", 0x657781]]],
  ["Polished concrete", "fleck", [0.45, 0.45], 0.39, [["Natural", 0x9c9b90], ["Salt and Pepper", 0x777873], ["Warm Aggregate", 0x9e9280]]],
  ["Epoxy flake", "fleck", [0.12, 0.12], 0.49, [["Garage Grey", 0x7c8185], ["Quartz", 0xa4a19a], ["Basalt", 0x575a62]]],
  ["Terrazzo tile 600 × 600", "tile", [0.6, 0.6], 0.56, [["Ivory Mix", 0xc9beb0], ["Grey Mix", 0x929b9e]]],
  ["Cork tile 300 × 300", "tile", [0.3, 0.3], 0.82, [["Natural", 0xa47b51], ["Dark Cork", 0x795839]]],
  ["Rubber tile 500 × 500", "tile", [0.5, 0.5], 0.88, [["Graphite", 0x45474d], ["Blue Fleck", 0x546d7e]]],
];
const wallFamilies: CoveringFamily[] = [
  ["Subway tile 75 × 150", "tile", [0.15, 0.075], 0.35, [["Gloss White", 0xeeeae2], ["Pale Grey", 0xc8cecf], ["Ocean", 0x678d91], ["Sage", 0x9da891]]],
  ["Square tile 100 × 100", "tile", [0.1, 0.1], 0.54, [["White", 0xe3e0d6], ["Oat", 0xcbbba1], ["Steel", 0x909aa0], ["Ink", 0x4a535a]]],
  ["Large format tile 600 × 1200", "tile", [1.2, 0.6], 0.56, [["Stone White", 0xddd6c5], ["Greige", 0xb2a995], ["Mid Grey", 0x8e9595]]],
  ["Timber battens", "rib", [0.04, 1], 0.65, [["Natural Oak", 0xb69063], ["Walnut", 0x755241], ["Blackened Timber", 0x4d4844]]],
  ["V-groove lining", "rib", [0.1, 1], 0.73, [["Warm White", 0xe8e1d1], ["Pale Sage", 0xabb9a4], ["Deep Navy", 0x495b70]]],
  ["Acoustic felt panels", "woven", [0.09, 0.09], 0.96, [["Cloud", 0xb3b6b4], ["Charcoal", 0x5c6067], ["Olive", 0x7a8369]]],
  ["Textile wallcovering", "woven", [0.2, 0.2], 0.88, [["Natural Linen", 0xc4b79f], ["Mushroom", 0xa49483], ["Seagrass", 0x8a9d89]]],
  ["Exposed brick", "tile", [0.23, 0.077], 0.91, [["Red Blend", 0x9d604d], ["Cream Blend", 0xc9b599], ["Grey Blend", 0x8a8680]]],
];
function coverings(group: "floors" | "walls", families: CoveringFamily[]) {
  return families.flatMap(([family, pattern, repeatM, roughness, colours]) => colours.map(([name, color]) =>
    surface(group, family + " · " + name, group === "floors" ? ["floor"] : ["wall"],
      color, pattern, roughness, repeatM, "finish", group === "floors" ? "flooring floor covering" : "wall finish wallcovering")));
}

type FixtureFamily = readonly [string, ItemTarget, FixtureShape,
  readonly [number, number, number], number?];
type Colourway = readonly [string, number, number?];
function fixtureItems(group: CatalogueGroup, family: FixtureFamily[], finishes: readonly Colourway[], keywords: string): CatalogueItem[] {
  return family.flatMap(([label, target, shape, [widthM, heightM, depthM], count = 1]) => finishes.map(([finish, color, metalness = 0]) => {
    const name = finish ? label + " · " + finish : label;
    return { id: group + "-" + slug(name), group, label: name, targets: [target], keywords,
      visual: { kind: "fixture", shape, color, metalness, widthM, heightM, depthM, count } };
  }));
}
const tapFinishes = [["Chrome", 0xbec9ce, 0.78], ["Brushed nickel", 0xa8a5a0, 0.62],
  ["Matte black", 0x323437, 0.15], ["Brushed brass", 0xb99b63, 0.66], ["Gunmetal", 0x626a70, 0.62]] as const;
const taps: FixtureFamily[] = [
  ["Basin mixer", "worktop", "mixer", [0.05, 0.17, 0.13]],
  ["Tall basin mixer", "worktop", "mixer", [0.05, 0.29, 0.18]],
  ["Gooseneck kitchen mixer", "worktop", "gooseneck", [0.05, 0.39, 0.23]],
  ["Pull-out kitchen mixer", "worktop", "gooseneck", [0.06, 0.42, 0.27], 2],
  ["Square kitchen mixer", "worktop", "square-spout", [0.05, 0.33, 0.24]],
  ["Laundry mixer", "worktop", "gooseneck", [0.05, 0.30, 0.19]],
  ["Wall basin spout", "wall", "wall-spout", [0.06, 0.06, 0.19]],
  ["Wall bath spout", "wall", "wall-spout", [0.08, 0.07, 0.25]],
  ["Shower mixer", "wall", "mixer", [0.11, 0.11, 0.07]],
  ["Overhead shower rose", "wall", "shower", [0.24, 0.20, 0.38]],
  ["Hand shower and rail", "wall", "shower", [0.10, 0.65, 0.14], 2],
  ["Garden hose tap", "wall", "outdoor-tap", [0.08, 0.12, 0.12]],
];

const electrical: FixtureFamily[] = [
  ["Single power point", "wall", "socket", [0.075, 0.075, 0.014]],
  ["Double power point", "wall", "socket", [0.12, 0.075, 0.014], 2],
  ["Four-outlet power point", "wall", "socket", [0.15, 0.075, 0.014], 4],
  ["Power point with USB", "wall", "port", [0.12, 0.075, 0.014], 2],
  ["Single light switch", "wall", "switch", [0.075, 0.12, 0.014]],
  ["Two-gang light switch", "wall", "switch", [0.075, 0.12, 0.014], 2],
  ["Three-gang light switch", "wall", "switch", [0.075, 0.12, 0.014], 3],
  ["Four-gang light switch", "wall", "switch", [0.12, 0.075, 0.014], 4],
  ["Dimmer control", "wall", "isolator", [0.075, 0.12, 0.023]],
  ["Data point", "wall", "port", [0.075, 0.12, 0.014]],
  ["Double data point", "wall", "port", [0.12, 0.075, 0.014], 2],
  ["TV point", "wall", "port", [0.075, 0.075, 0.014], 3],
  ["Appliance isolator", "wall", "isolator", [0.075, 0.075, 0.022], 2],
  ["Outdoor socket cover", "wall", "socket", [0.115, 0.09, 0.033], 2],
  ["Smoke alarm", "ceiling", "alarm", [0.105, 0.105, 0.036]],
];
const plates = [["White", 0xe5e5df], ["Black", 0x37383b], ["Silver", 0xaeb5bb, 0.45]] as const;
const lights: FixtureFamily[] = [
  ["Recessed downlight 70 mm", "ceiling", "downlight", [0.07, 0.07, 0.035]],
  ["Recessed downlight 90 mm", "ceiling", "downlight", [0.09, 0.09, 0.04]],
  ["Adjustable spotlight", "ceiling", "downlight", [0.11, 0.11, 0.074], 2],
  ["Flush ceiling light", "ceiling", "downlight", [0.26, 0.26, 0.065]],
  ["Linear batten 600 mm", "ceiling", "batten", [0.6, 0.065, 0.055]],
  ["Linear batten 1200 mm", "ceiling", "batten", [1.2, 0.072, 0.062]],
  ["Dome pendant", "ceiling", "pendant", [0.32, 0.44, 0.32]],
  ["Globe pendant", "ceiling", "pendant", [0.24, 0.39, 0.24], 2],
  ["Wall sconce", "wall", "sconce", [0.14, 0.24, 0.115]],
  ["Up-down wall light", "wall", "sconce", [0.095, 0.19, 0.095], 2],
  ["Ceiling exhaust grille", "ceiling", "fan", [0.23, 0.23, 0.04]],
];
const bathrooms: FixtureFamily[] = [
  ["Round countertop basin", "worktop", "basin", [0.36, 0.14, 0.36]],
  ["Oval countertop basin", "worktop", "basin", [0.51, 0.145, 0.34]],
  ["Rectangular inset basin", "worktop", "basin", [0.48, 0.07, 0.35], 2],
  ["Single bowl kitchen sink", "worktop", "basin", [0.51, 0.075, 0.38], 2],
  ["Double bowl kitchen sink", "worktop", "basin", [0.76, 0.085, 0.39], 3],
  ["Close-coupled toilet", "floor", "toilet", [0.39, 0.79, 0.66]],
  ["Back-to-wall toilet", "floor", "toilet", [0.36, 0.75, 0.62], 2],
  ["Freestanding bath 1500 mm", "floor", "bath", [1.5, 0.56, 0.73]],
  ["Freestanding bath 1700 mm", "floor", "bath", [1.7, 0.60, 0.76]],
  ["Single towel rail", "wall", "rail", [0.6, 0.08, 0.08]],
  ["Double towel rail", "wall", "rail", [0.75, 0.12, 0.11], 2],
];
const cabinets: FixtureFamily[] = [
  ["Vanity 600 mm", "floor", "vanity", [0.6, 0.84, 0.46]],
  ["Vanity 900 mm", "floor", "vanity", [0.9, 0.84, 0.46], 2],
  ["Double vanity 1200 mm", "floor", "vanity", [1.2, 0.84, 0.49], 2],
  ["Base cabinet 450 mm", "floor", "cabinet", [0.45, 0.9, 0.57]],
  ["Base cabinet 600 mm", "floor", "cabinet", [0.6, 0.9, 0.57]],
  ["Drawer base cabinet 900 mm", "floor", "cabinet", [0.9, 0.9, 0.59], 3],
  ["Tall pantry cabinet", "floor", "cabinet", [0.6, 2.08, 0.60], 2],
  ["Kitchen island 1600 mm", "floor", "bench", [1.6, 0.9, 0.8], 2],
  ["Kitchen island 2100 mm", "floor", "bench", [2.1, 0.9, 0.88], 3],
];
const doorFinishes = [
  ["Painted door leaf · Warm white", 0xeee9de, "solid"],
  ["Painted door leaf · Charcoal", 0x4a4b4d, "solid"],
  ["Painted door leaf · Sage", 0x89988a, "solid"],
  ["Timber door leaf · Oak", 0xb6926b, "grain"],
  ["Timber door leaf · Walnut", 0x765842, "grain"],
  ["Timber door leaf · Ash", 0xc1ac91, "grain"],
] as const;

export const ITEM_CATALOGUE: readonly CatalogueItem[] = [
  ...paint, ...plasterboard, ...trimItems, ...coverings("floors", floorFamilies),
  ...coverings("walls", wallFamilies),
  ...fixtureItems("tapware", taps, tapFinishes, "tap mixer spout shower plumbing"),
  ...fixtureItems("electrical", electrical, plates, "electrical outlet gpo power point socket switch"),
  ...fixtureItems("lights", lights, plates, "light ceiling lamp electrical lighting"),
  ...fixtureItems("bathroom", bathrooms, [["White", 0xe9e7e0], ["Soft grey", 0xaaa9a6]], "bathroom basin sink bath toilet laundry"),
  ...fixtureItems("furniture", [["Three-seat sofa","floor","sofa",[2.1,.82,.86]],["Queen bed","floor","bed",[1.6,.85,2.1]],["Single bed","floor","bed",[.96,.82,1.98]],["Round coffee table","floor","coffee-table",[.8,.42,.8]]], [["Linen",0xc5bba9],["Oak",0xad8965],["Charcoal",0x606365]],"editable furniture sofa bed coffee table"),
  ...fixtureItems("cabinets", cabinets, [["Polar white", 0xe3dfd4], ["Pale oak", 0xad8965],
    ["Walnut", 0x705240], ["Graphite", 0x4e5154]], "cabinet kitchen vanity joinery benchtop worktop"),
  ...doorFinishes.map(([label, color, pattern]) => surface("doors", label, ["opening"], color,
    pattern, 0.55, [0.22, 1.3], "finish", "door leaf opening door finish")),
  ...EXTERIOR_CATALOGUE, ...ROOF_COMPONENTS, ...ROUGH_IN_CATALOGUE, ...EXTENSION_CATALOGUE,
];

export const itemCanRotate = (item: CatalogueItem) =>
  item.visual.kind === "fixture" || item.visual.kind === "timber" ||
  (item.visual.kind === "design-assembly" && item.group !== "flyovers");

const byId = new Map(ITEM_CATALOGUE.map(item => [item.id, item]));
export const getCatalogueItem = (id: string | null) => id === null ? undefined : byId.get(id);
export const catalogueGroupLabel = (group: CatalogueGroup) =>
  CATALOGUE_GROUPS.find(([id]) => id === group)?.[1] ?? group;

export function searchCatalogue(query: string, group?: CatalogueGroup): CatalogueItem[] {
  const terms = query.toLowerCase().split(/[\s.,×-]+/).filter(Boolean);
  return ITEM_CATALOGUE.filter(item => {
    if (group && item.group !== group) return false;
    const haystack = (item.label + " " + item.keywords + " " + catalogueGroupLabel(item.group)).toLowerCase();
    return terms.every(term => haystack.includes(term));
  });
}
