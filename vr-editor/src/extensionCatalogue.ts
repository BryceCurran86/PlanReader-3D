import type { CatalogueGroup, CatalogueItem, DesignAssembly, OpeningStyle } from "./itemCatalogue.ts";

type Finish = readonly [string, number];
const aluminium = [["White", 0xeeece5], ["Charcoal", 0x464d51], ["Black", 0x282c2e], ["Natural anodised", 0x9aa7aa]] as const;
const timber = [["Blackbutt", 0xb18a57], ["Spotted gum", 0x8e6845], ["White oak", 0xc5aa7d], ["Painted white", 0xe7e4da]] as const;
const fabric = [["White", 0xe9e5d9], ["Sand", 0xcdbda2], ["Smoke", 0x8b8c88], ["Charcoal", 0x4c515a]] as const;
const stone = [["Sandstone", 0xc4aa83], ["Pale concrete", 0xb8b8aa], ["Bluestone", 0x667279]] as const;
const water = [["Aqua", 0x39b2bc], ["Pacific blue", 0x318bbe], ["Deep blue", 0x275b8e]] as const;
const planting = [["Coastal green", 0x759251], ["Native green", 0x4f794d], ["Silver foliage", 0x91ad9b]] as const;

function options(group: CatalogueGroup, key: string, name: string, finishes: readonly Finish[],
  target: CatalogueItem["targets"][number], visual: Omit<DesignAssembly, "color"> | Omit<OpeningStyle, "color">,
): CatalogueItem[] {
  return finishes.map(([finish, color], index) => ({
    id: group + "-" + key + "-" + (index + 1), group, label: name + " · " + finish, targets: [target],
    keywords: group + " " + key + " " + name, visual: { ...visual, color },
  }));
}

const openingOptions: readonly [CatalogueGroup, OpeningStyle["type"], OpeningStyle["style"], string, readonly Finish[]][] = [
  ["sliding-doors", "door", "slider", "Two-panel glass sliding door", aluminium],
  ["sliding-doors", "door", "stacker", "Three-panel stacker sliding door", aluminium],
  ["sliding-doors", "door", "wide-stacker", "Four-panel centre-opening slider", aluminium],
  ["sliding-doors", "door", "lift-slide", "Lift-and-slide door", aluminium],
  ["sliding-doors", "door", "cavity", "Cavity sliding door", timber],
  ["sliding-doors", "door", "barn", "Barn sliding door", timber],
  ["sliding-doors", "door", "bypass", "Bypass sliding door", timber],
  ["windows", "window", "fixed", "Fixed picture window", aluminium],
  ["windows", "window", "slider", "Horizontal sliding window", aluminium],
  ["windows", "window", "awning", "Awning window", aluminium],
  ["windows", "window", "casement", "Casement window", aluminium],
  ["windows", "window", "double-hung", "Double-hung window", aluminium],
  ["windows", "window", "louvre", "Louvre window", aluminium],
  ["windows", "window", "bifold", "Bi-fold window", aluminium],
  ["window-coverings", "covering", "curtain", "S-fold curtain", fabric],
  ["window-coverings", "covering", "sheer", "Sheer curtain", fabric],
  ["window-coverings", "covering", "roller", "Roller blind", fabric],
  ["window-coverings", "covering", "roman", "Roman blind", fabric],
  ["window-coverings", "covering", "venetian", "Venetian blind", timber],
  ["window-coverings", "covering", "vertical", "Vertical blind", fabric],
  ["window-coverings", "covering", "shutter", "Plantation shutters", timber],
];

type AssemblyFamily = readonly [CatalogueGroup, DesignAssembly["shape"], string,
  "floor" | "site" | "wall", readonly [number, number, number], readonly Finish[]];
const assemblies: AssemblyFamily[] = [
  ["stairs", "straight-stair", "Straight stair", "floor", [1.05, 2.6, 3.85], timber],
  ["stairs", "l-stair", "Quarter-turn stair", "floor", [1.05, 2.6, 3.2], timber],
  ["stairs", "u-stair", "Switchback stair", "floor", [1.05, 2.6, 2.7], timber],
  ["stairs", "spiral-stair", "Spiral stair", "floor", [1.8, 2.6, 1.8], aluminium],
  ["stairs", "straight-stair", "Entry steps", "site", [1.4, 0.6, 1.2], stone],
  ["balustrading", "glass-rail", "Frameless glass balustrade", "floor", [2.4, 1.05, 0.08], aluminium],
  ["balustrading", "picket-rail", "Vertical metal balustrade", "floor", [2.4, 1.05, 0.10], aluminium],
  ["balustrading", "picket-rail", "Timber balustrade", "floor", [2.4, 1.05, 0.12], timber],
  ["balustrading", "wire-rail", "Wire balustrade", "floor", [2.4, 1.05, 0.10], aluminium],
  ["balustrading", "glass-rail", "Glass pool barrier panel", "site", [2, 1.2, 0.08], aluminium],
  ["balustrading", "picket-rail", "Metal pool barrier panel", "site", [2, 1.2, 0.10], aluminium],
  ["flyovers", "skillion", "Skillion flyover patio", "wall", [5.4, 3.3, 3.6], aluminium],
  ["flyovers", "gable", "Gable flyover patio", "wall", [5.4, 3.6, 3.6], aluminium],
  ["flyovers", "insulated", "Insulated-panel flyover patio", "wall", [5.4, 3.3, 3.6], aluminium],
  ["pools", "rectangle-pool", "Rectangular pool", "site", [6, 0.15, 3], water],
  ["pools", "rounded-pool", "Round plunge pool", "site", [3.2, 0.15, 3.2], water],
  ["pools", "rounded-pool", "Oval pool", "site", [6.5, 0.15, 3.4], water],
  ["pools", "rectangle-pool", "Lap pool", "site", [10, 0.15, 2.5], water],
  ["pools", "rounded-pool", "Raised spa", "site", [2.2, 0.75, 2.1], water],
  ["landscaping", "lawn", "Lawn area", "site", [4.5, 0.035, 3.6], planting],
  ["landscaping", "stepping", "Stepping stone path", "site", [0.7, 0.06, 4], stone],
  ["landscaping", "garden", "Raised garden bed", "site", [2.4, 0.45, 1.2], timber],
  ["landscaping", "hedge", "Hedge screen", "site", [2.8, 1.25, 0.65], planting],
  ["landscaping", "tree", "Feature tree", "site", [2.6, 3.8, 2.6], planting],
  ["landscaping", "retaining", "Retaining wall segment", "site", [2.6, 0.6, 0.22], stone],
];
export const EXTENSION_CATALOGUE = [
  ...openingOptions.flatMap(([group, type, style, name, finishes]) =>
    options(group, style, name, finishes, "opening", { kind: "opening-style", type, style })),
  ...assemblies.flatMap(([group, shape, name, target, [widthM, heightM, depthM], finishes]) =>
    options(group, name.toLowerCase().replaceAll(" ", "-"), name, finishes, target,
      { kind: "design-assembly", shape, widthM, heightM, depthM })),
];
