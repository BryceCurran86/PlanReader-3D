import type { CatalogueGroup, CatalogueItem } from "./itemCatalogue.ts";

export const CONSTRUCTION_STAGES = [
  { id: "finished", label: "Finished", description: "See the building and placed finishes." },
  { id: "slab", label: "Concrete slab", description: "Inspect source floor or slab surfaces. Thickness and reinforcement require structural drawings." },
  { id: "framing", label: "Framing & rough-in", description: "See illustrative timber framing and installed draft service points with linings hidden." },
  { id: "rough-in", label: "Services only", description: "Inspect placed plumbing, electrical and air-conditioning points before linings go on." },
  { id: "lock-up", label: "Lock-up", description: "Inspect the roof and envelope preview." },
  { id: "insulation", label: "Insulation", description: "Illustrative insulation before linings." },
  { id: "sheeted", label: "Bare plasterboard", description: "Nominal sheet joints and fastener positions; not a fixing specification." },
  { id: "set", label: "Trowelled plasterboard", description: "Metric sheet joints with feathered compound and fixing patches." },
  { id: "sanded", label: "Sanded plasterboard", description: "Illustrative sanded compound before paint." },
  { id: "undercoat", label: "Undercoated", description: "Uniform primed lining preview." },
] as const;

export type ConstructionStage = typeof CONSTRUCTION_STAGES[number]["id"];
export const stageDetails = (stage: ConstructionStage) => CONSTRUCTION_STAGES.find(entry => entry.id === stage)!;
export const isLiningStage=(stage:ConstructionStage):stage is "sheeted"|"set"|"sanded"|"undercoat"=>["sheeted","set","sanded","undercoat"].includes(stage);
export const CATALOGUE_DRAG_TYPE = "application/x-planreader-catalogue";
export const OPENING_DRAG_TYPE = "application/x-planreader-opening";
const roughIns: readonly CatalogueGroup[] = ["plumbing-rough-in", "electrical-rough-in", "air-conditioning"];
const envelope: readonly CatalogueGroup[] = ["roofing", "roof-components", "facades", "substrates", "soffits",
  "entry", "windows", "sliding-doors", "flyovers"];

export const isRoughIn = (item: CatalogueItem) => roughIns.includes(item.group);

export function showConstructionItem(stage: ConstructionStage, item: CatalogueItem) {
  if (stage === "slab") return false;
  if (stage === "framing") return item.group === "stairs" || roughIns.includes(item.group);
  if (stage === "rough-in") return roughIns.includes(item.group);
  if (stage === "lock-up" || stage === "insulation") return envelope.includes(item.group) || item.group === "boards";
  if(isLiningStage(stage))return envelope.includes(item.group)||item.group==="boards";
  return !roughIns.includes(item.group);
}

export function showConstructionSurface(stage: ConstructionStage, kind?: "floor" | "ceiling" | "roof") {
  if (stage === "slab") return kind === "floor";
  if (stage === "framing" || stage === "rough-in") return kind !== "ceiling" && kind !== "roof";
  if (stage === "lock-up" || stage==="insulation") return kind !== "ceiling";
  return true;
}
