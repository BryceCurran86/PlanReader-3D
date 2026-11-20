import type { CatalogueGroup, CatalogueItem } from "./itemCatalogue.ts";

export const CONSTRUCTION_STAGES = [
  { id: "finished", label: "Finished", description: "See the building and placed finishes." },
  { id: "slab", label: "Concrete slab", description: "Inspect source floor or slab surfaces. Thickness and reinforcement require structural drawings." },
  { id: "framing", label: "Framing", description: "See wall outlines and draft openings with linings and finishes hidden." },
  { id: "rough-in", label: "Rough-in", description: "Place and review plumbing, electrical and air-conditioning points before linings go on." },
  { id: "lock-up", label: "Lock-up", description: "Inspect the roof, envelope and external selections." },
] as const;

export type ConstructionStage = typeof CONSTRUCTION_STAGES[number]["id"];
export const stageDetails = (stage: ConstructionStage) => CONSTRUCTION_STAGES.find(entry => entry.id === stage)!;
export const CATALOGUE_DRAG_TYPE = "application/x-planreader-catalogue";
export const OPENING_DRAG_TYPE = "application/x-planreader-opening";
const roughIns: readonly CatalogueGroup[] = ["plumbing-rough-in", "electrical-rough-in", "air-conditioning"];
const envelope: readonly CatalogueGroup[] = ["roofing", "roof-components", "facades", "substrates", "soffits", "entry"];

export const isRoughIn = (item: CatalogueItem) => roughIns.includes(item.group);

export function showConstructionItem(stage: ConstructionStage, item: CatalogueItem) {
  if (stage === "slab" || stage === "framing") return false;
  if (stage === "rough-in") return roughIns.includes(item.group);
  if (stage === "lock-up") return envelope.includes(item.group);
  return !roughIns.includes(item.group);
}

export function showConstructionSurface(stage: ConstructionStage, kind?: "floor" | "ceiling" | "roof") {
  if (stage === "slab") return kind === "floor";
  if (stage === "framing" || stage === "rough-in") return kind !== "ceiling" && kind !== "roof";
  if (stage === "lock-up") return kind !== "ceiling";
  return true;
}
