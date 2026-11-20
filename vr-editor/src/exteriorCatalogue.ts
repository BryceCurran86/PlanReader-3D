import type { CatalogueGroup, CatalogueItem, EntryStyle, ItemTarget, Pattern, TimberProfile } from "./itemCatalogue.ts";

const species = [
  ["Radiata Pine", 0xc5a979], ["Blackbutt", 0xb99461], ["Spotted Gum", 0x96714f],
  ["Merbau", 0x88563e], ["Jarrah", 0x804d3d], ["Tasmanian Oak", 0xc2a07a],
  ["Victorian Ash", 0xc9b28c], ["Western Red Cedar", 0xaa724a],
  ["Australian Cypress", 0xb69768], ["American Oak", 0xb8996f],
] as const;

const slug = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-$/, "");

type TimberSection = readonly [string, TimberProfile, number, number, readonly number[], ("face" | "post")?];
const sections: readonly TimberSection[] = [
  ["DAR board", "square", 90, 19, [900, 1800]],
  ["DAR framing timber", "square", 90, 45, [1800, 2400]],
  ["Eased-edge timber board", "eased", 135, 19, [900, 1800]],
  ["Bullnose trim", "bullnose", 66, 18, [900, 1800]],
  ["Chamfered trim", "chamfer", 42, 18, [900, 1800]],
  ["Rebated board", "rebate", 90, 19, [900, 1800]],
  ["Shiplap board", "shiplap", 135, 19, [900, 1800]],
  ["V-joint lining board", "v-joint", 90, 14, [900, 1800]],
  ["Bevelback weatherboard", "bevelback", 170, 22, [900, 1800]],
  ["Timber batten", "square", 42, 30, [900, 1800]],
  ["Half-round moulding", "half-round", 30, 15, [900, 1800]],
  ["Square timber post", "square", 90, 90, [900, 1800], "post"],
  ["Chamfered timber post", "chamfer", 140, 140, [1200, 2100], "post"],
];
const timber = sections.flatMap(([name, profile, width, depth, lengths, mount = "face"]) =>
  lengths.flatMap(length => species.map(([speciesName, color], grain): CatalogueItem => {
    const size = width + " × " + depth + " × " + length + " mm";
    return { id: "timber-" + slug(name + " " + size + " " + speciesName), group: "timber",
      label: name + " " + size + " · " + speciesName, targets: mount === "post" ? ["floor"] : ["wall"],
      keywords: "timber wood profile species moulding lumber dressed all round " + (mount === "post" ? "upright post" : "board trim batten section"),
      visual: { kind: "timber", profile, mount, widthM: width / 1000, depthM: depth / 1000,
        lengthM: length / 1000, color, grain } };
  })));

const entryStyles: readonly (readonly [string, EntryStyle, number, number])[] = [
  ["Flush timber entry", "flush", 0.82, 1.95],
  ["Shaker two-panel entry", "shaker", 0.82, 1.95],
  ["Craftsman top-light entry", "craftsman", 0.86, 2],
  ["Vertical glazed lite entry", "vertical-lite", 0.85, 2],
  ["Three horizontal glazed lites", "strip-lite", 0.86, 2],
  ["Full-length glazed entry", "full-lite", 0.86, 2],
  ["Vertical batten entry", "batten", 0.9, 2],
  ["Heritage arched-lite entry", "arched-lite", 0.88, 2.05],
  ["Double-leaf entry", "double", 1.42, 2.05],
  ["Entry with glazed sidelight", "sidelight", 1.18, 2.05],
  ["Offset pivot entry", "pivot", 1.08, 2.1],
];
const doorFinishes: readonly (readonly [string, number, number | null])[] = [
  ["Natural Blackbutt", 0xb69267, 1], ["Spotted Gum", 0x896447, 2],
  ["Oiled Merbau", 0x864e38, 3], ["Victorian Ash", 0xc5ac89, 6],
  ["Western Red Cedar", 0xaa7046, 7], ["Limed Oak", 0xc8ba9f, 9],
  ["Painted Off White", 0xefebe0, null], ["Painted Graphite", 0x42484b, null],
];
const entries = entryStyles.flatMap(([name, style, minWidthM, minHeightM]) => doorFinishes.map(([finish, color, grain]): CatalogueItem => ({
  id: "entry-" + slug(name + " " + finish), group: "entry", label: name + " · " + finish,
  targets: ["opening"], keywords: "front door entry entrance hinged panel gable glass hardware timber",
  visual: { kind: "entry", style, minWidthM, minHeightM, color, grain },
})));

type Family = readonly [string, Pattern, readonly [number, number], number, readonly (readonly [string, number])[]];
const substrate: Family[] = [
  ["Fibre cement exterior sheet 6 mm", "sheet", [1.2, 2.4], 0.91, [["Grey", 0xacaaa1], ["Primed", 0xd6d3c8]]],
  ["Fibre cement exterior sheet 9 mm", "sheet", [1.2, 2.4], 0.9, [["Grey", 0xaaa69d], ["Primed", 0xd7d4c7]]],
  ["Fibre cement exterior sheet 12 mm", "sheet", [1.2, 2.4], 0.91, [["Grey", 0xa5a49d], ["Primed", 0xd9d3c5]]],
  ["Exterior plywood sheathing 9 mm", "grain", [1.2, 2.4], 0.86, [["Pine", 0xc2a77e], ["Hardwood", 0xa7825b]]],
  ["Exterior plywood sheathing 12 mm", "grain", [1.2, 2.4], 0.86, [["Pine", 0xbfa175], ["Hardwood", 0x9e7952]]],
  ["Exterior plywood sheathing 15 mm", "sheet", [1.2, 2.4], 0.86, [["Pine", 0xc7a97e], ["Hardwood", 0xa87f5b]]],
  ["OSB sheathing 9 mm", "fleck", [0.16, 0.22], 0.92, [["Natural", 0xad916f]]],
  ["OSB sheathing 12 mm", "fleck", [0.17, 0.22], 0.92, [["Natural", 0xb39771]]],
  ["Glass-mat gypsum sheathing", "sheet", [1.2, 2.4], 0.94, [["Ochre facing", 0xc3ac6f], ["Grey facing", 0xadaeac]]],
  ["AAC backing panels", "sheet", [0.6, 2.4], 0.96, [["50 mm", 0xd0cbbd], ["75 mm", 0xc3beaf]]],
  ["Masonry backing", "masonry", [0.39, 0.19], 0.97, [["Concrete block", 0xa5a29b], ["Clay block", 0xb38a71], ["Sandstone block", 0xc0ac88]]],
  ["Precast concrete substrate", "sheet", [2.4, 3], 0.91, [["Light concrete", 0xbcbab1], ["Medium concrete", 0xa3a099]]],
  ["Exterior wrap", "sheet", [1.35, 2.7], 0.94, [["Blue", 0x859cac], ["Charcoal", 0x626877], ["White", 0xdad9d0]]],
];
const exterior: Family[] = [
  ["Bevelback weatherboards", "lap", [1.2, 0.17], 0.66, [["White", 0xe8e6dd], ["Eucalyptus", 0x879891], ["Sandstone", 0xc0af95], ["Charcoal", 0x4e5353]]],
  ["Timber shiplap cladding", "lap", [1.4, 0.14], 0.72, [["Cedar", 0xaa774d], ["Blackbutt", 0xb89d74], ["Charred timber", 0x463d37], ["Weathered silver", 0xa09e92]]],
  ["Board-and-batten cladding", "rib", [0.18, 1], 0.72, [["Painted white", 0xe3ded3], ["Dune", 0xb3a690], ["Olive", 0x737c6c], ["Blackened oak", 0x504c45]]],
  ["Fibre cement lap siding", "lap", [1.2, 0.2], 0.77, [["Off white", 0xe2dfd2], ["Greige", 0xb6afa2], ["Slate", 0x666d70], ["Dark green", 0x526057]]],
  ["Standing seam metal", "seam", [0.38, 1], 0.43, [["Basalt", 0x53595e], ["Zinc", 0x91999d], ["Dune", 0xa59b89], ["Night Sky", 0x373e43], ["Copper tone", 0x91664d]]],
  ["Corrugated metal", "corrugation", [0.076, 1], 0.52, [["Zinc", 0xaeb5b5], ["Surf grey", 0xb2afa1], ["Charcoal", 0x53585e], ["Forest grey", 0x737f72]]],
  ["Face brick veneer", "masonry", [0.24, 0.086], 0.9, [["Pressed red", 0xa76f56], ["Recycled blend", 0xa9836a], ["Cream", 0xc4af8f], ["Ironstone", 0x71635e], ["Whitewashed", 0xd4c9b8]]],
  ["Exterior stone slips", "masonry", [0.47, 0.19], 0.92, [["Sandstone", 0xba9d76], ["Limestone", 0xc8bba2], ["Bluestone", 0x747a7e], ["Granite", 0x9d968b]]],
  ["Smooth exterior render", "solid", [1, 1], 0.83, [["Limestone", 0xe1d9cb], ["Warm white", 0xeee9dc], ["Soft stone", 0xafaaa1], ["Olive grey", 0x7d8172]]],
  ["Sand-float render", "fleck", [0.055, 0.055], 0.96, [["Natural", 0xc6b69b], ["Ecru", 0xd8ccba], ["Pumice", 0xa5a29b], ["Graphite", 0x535456]]],
  ["Bagged brick finish", "masonry", [0.24, 0.086], 0.96, [["White bag", 0xdacfbc], ["Sand bag", 0xc6b493], ["Grey bag", 0x9b9b98]]],
  ["Precast facade panel", "sheet", [1.2, 2.4], 0.79, [["Off-form concrete", 0xb1ada3], ["Sandblast", 0xb7ad96], ["White cement", 0xd5d1c6]]],
  ["Board-formed concrete", "lap", [1.2, 0.14], 0.91, [["Pale concrete", 0xc4bfb3], ["Warm grey", 0xa59c90], ["Graphite", 0x5f6060]]],
  ["Exterior porcelain panels", "sheet", [0.6, 1.2], 0.56, [["Pale Travertine", 0xc8b79d], ["Basalt", 0x55585d], ["Limestone", 0xd3cab8]]],
];
const decking: Family[] = [
  ["Smooth timber decking 90 mm", "plank", [0.09, 2.1], 0.68, species],
  ["Smooth timber decking 140 mm", "plank", [0.14, 2.4], 0.67, species],
  ["Grooved decking 135 mm", "rib", [0.135, 1.8], 0.75, [["Natural timber", 0xb08c62], ["Smoked timber", 0x7f634b], ["Weathered timber", 0x9c9a8e]]],
  ["Composite decking", "plank", [0.138, 2.2], 0.74, [["Driftwood", 0x989086], ["Smoked Oak", 0x785d49], ["Iron Grey", 0x62666a], ["Sand", 0xab997f]]],
  ["Pavers 600 × 400", "tile", [0.6, 0.4], 0.88, [["Sandstone", 0xc3ab86], ["Limestone", 0xc8bc9f], ["Bluestone", 0x69737a], ["Concrete grey", 0x9d9d95]]],
  ["Terrace porcelain 600 × 600", "tile", [0.6, 0.6], 0.68, [["Warm Stone", 0xc1b198], ["Salt", 0xdfd9c9], ["Basalt", 0x54565a]]],
];
const soffits: Family[] = [
  ["Fibre cement eaves lining", "sheet", [1.2, 2.4], 0.85, [["Primed", 0xdddad0], ["Off white", 0xe9e5d9], ["Pale grey", 0xbabbb5], ["Charcoal", 0x565b5e]]],
  ["Timber V-joint soffit", "rib", [0.091, 1], 0.71, [["Cedar", 0xad774d], ["Victorian Ash", 0xc4ad88], ["Blackbutt", 0xaf895e], ["Sealed pine", 0xc6aa7f]]],
  ["Metal soffit tray", "seam", [0.15, 1], 0.54, [["Cloud white", 0xe2e3dd], ["Smoke", 0x9fa7a7], ["Charcoal", 0x50565a]]],
  ["Perforated soffit panel", "fleck", [0.075, 0.075], 0.76, [["White", 0xdedcd5], ["Slate", 0x6f7779], ["Natural zinc", 0xaeb5b7]]],
];

const roofing: Family[] = [
  ["Corrugated steel roof", "corrugation", [0.076, 1], 0.52, [
    ["Natural zinc", 0xafb5b4], ["Surf grey", 0xb5b1a3], ["Sandstone", 0xb7a18a],
    ["Dune", 0xa9a59a], ["Blue grey", 0x66747a], ["Charcoal", 0x494d50],
    ["Forest green", 0x59685a], ["Slate grey", 0x73777b], ["Black", 0x35393c],
  ]],
  ["Trapezoidal rib steel roof", "rib", [0.21, 1], 0.49, [
    ["Zinc", 0xabb3b2], ["Off white", 0xd7d5c9], ["Pale sand", 0xb4a592],
    ["Slate", 0x747b7e], ["Basalt", 0x5b5e61], ["Charcoal", 0x46494c],
  ]],
  ["Standing-seam metal roof", "seam", [0.42, 1], 0.43, [
    ["Zinc", 0x939c9f], ["Copper", 0xa66f5b], ["Weathered copper", 0x728f85],
    ["Sand", 0xb6ab96], ["Blue grey", 0x727d87], ["Graphite", 0x4f5258], ["Black", 0x33363a],
  ]],
  ["Concealed-fix ribbed metal roof", "rib", [0.23, 1], 0.48, [
    ["Glacier white", 0xdde0da], ["Zinc", 0xa5abaa], ["Pale olive", 0x9a9b88],
    ["Ash", 0x9e9e98], ["Charcoal", 0x4c5053], ["Deep green", 0x515b4d],
  ]],
  ["Flat concrete roof tile", "masonry", [0.3, 0.32], 0.91, [
    ["Mid grey", 0x8e8d87], ["Sandstone", 0xaa9a85], ["Mocha", 0x7e6d60],
    ["Slate", 0x606367], ["Charcoal", 0x4d4e4f],
  ]],
  ["Low-profile concrete roof tile", "profiled-tile", [0.31, 0.31], 0.89, [
    ["Clay", 0x997660], ["Earth", 0x80756a], ["Cocoa", 0x79655a],
    ["Charcoal", 0x545758], ["Pewter", 0x878a8d],
  ]],
  ["Flat terracotta roof tile", "masonry", [0.27, 0.32], 0.78, [
    ["Natural terracotta", 0xb47862], ["Rust red", 0x955e52], ["Baked clay", 0xb0836e], ["Smoke", 0x70605c],
  ]],
  ["Barrel terracotta roof tile", "profiled-tile", [0.24, 0.32], 0.74, [
    ["Natural terracotta", 0xb7795c], ["Antique red", 0x996557], ["Sand", 0xb49b80], ["Pale ochre", 0xb78f6a],
  ]],
  ["Slate roof tile", "masonry", [0.28, 0.21], 0.86, [
    ["Blue slate", 0x5d6874], ["Heather grey", 0x756e76], ["Green slate", 0x5d6d64], ["Black slate", 0x42474d],
  ]],
  ["Asphalt roof shingle", "masonry", [0.24, 0.145], 0.97, [
    ["Weathered wood", 0x84796c], ["Estate grey", 0x777a7e], ["Brown blend", 0x776659], ["Charcoal", 0x4f5155],
  ]],
  ["Metal roof shingle", "masonry", [0.29, 0.19], 0.59, [
    ["Weathered zinc", 0x889091], ["Copper", 0xa36f5e], ["Graphite", 0x55595d],
  ]],
  ["Single-ply roof membrane", "solid", [1, 1], 0.85, [
    ["White", 0xe4e2db], ["Light grey", 0xb7b9b6], ["Charcoal", 0x535658],
  ]],
  ["Bituminous roof membrane", "fleck", [0.058, 0.058], 0.96, [
    ["Mineral grey", 0x7e7b76], ["Bitumen black", 0x444447],
  ]],
];

function surfaces(group: CatalogueGroup, families: Family[], target: ItemTarget,
  slot: "finish" | "lining", keywords: string): CatalogueItem[] {
  return families.flatMap(([family, pattern, repeatM, roughness, variants]) => variants.map(([finish, color]) => {
    const label = family + " · " + finish;
    return { id: group + "-" + slug(label), group, label, targets: [target], keywords,
      visual: { kind: "surface", slot, color, pattern, roughness, repeatM } };
  }));
}

export const EXTERIOR_CATALOGUE: readonly CatalogueItem[] = [
  ...timber,
  ...entries,
  ...surfaces("substrates", substrate, "wall", "lining", "exterior substrate backing sheathing underlay wall"),
  ...surfaces("facades", exterior, "wall", "finish", "facade exterior external cladding wall finish siding"),
  ...surfaces("decking", decking, "floor", "finish", "exterior deck decking floor outdoor terrace paver"),
  ...surfaces("soffits", soffits, "ceiling", "finish", "exterior soffit ceiling veranda eaves lining"),
  ...surfaces("roofing", roofing, "roof", "finish", "roof roofing covering finish exterior"),
];
