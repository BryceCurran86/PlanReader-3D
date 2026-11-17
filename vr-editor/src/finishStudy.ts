/**
 * Local, explicitly noncommercial wall-finish colour study.
 * A swatch has NO finish schedule, rate, source authority or material identity.
 * It must never mutate the scene manifest or correction ledger.
 */
import type { EditorObject } from "./types";

export type FinishSwatch = "chalk" | "slate" | "sage" | "clay";
export type FinishStudy = Readonly<{ objectId: string; swatch: FinishSwatch }>;

export const FINISH_SWATCHES: ReadonlyArray<Readonly<{
  id: FinishSwatch; label: string; color: number;
}>> = [
  { id: "chalk", label: "Warm white · visual only", color: 0xece3ce },
  { id: "slate", label: "Slate grey · visual only", color: 0x7a858f },
  { id: "sage", label: "Soft green · visual only", color: 0x91a794 },
  { id: "clay", label: "Terracotta · visual only", color: 0xb97e62 },
];

export function visualStudyAllowed(row: EditorObject | null): boolean {
  return row?.objectType === "wall" &&
    row.geometry?.kind === "wallFace" &&
    Number.isFinite(row.geometry.heightM) &&
    row.geometry.heightM > 0;
}

export function studyColor(row: EditorObject, study: FinishStudy | null): number | null {
  if (!study || !visualStudyAllowed(row) || study.objectId !== row.objectId)
    return null;
  return FINISH_SWATCHES.find(s => s.id === study.swatch)?.color ?? null;
}
