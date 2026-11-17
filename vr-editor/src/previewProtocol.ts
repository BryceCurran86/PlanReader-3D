/** Decode a server impact preview as untrusted data, never publication truth. */
export interface PreviewImpact {
  target: string;
  status: string;
  oldValue: number | null;
  proposedValue: number | null;
  unit: string;
  reason: string | null;
}
export interface VerifiedPreview {
  accepted: true;
  validationState: "valid_preview_only";
  commandId: string;
  targetObjectId: string;
  previousObjectRevision: string;
  previewObjectRevision: string;
  requiresApproval: true;
  persisted: false;
  commercialPublicationAllowed: false;
  quantityImpacts: PreviewImpact[];
  blockingReasons: [];
}
export interface PreviewRequestIdentity {
  commandId: string;
  targetObjectId: string;
  targetRevisionHash: string;
}

function finiteNumberOrNull(value: unknown): value is number | null {
  return value === null ||
    (typeof value === "number" && Number.isFinite(value));
}

export function verifyPreviewResponse(
  candidate: unknown,
  request: PreviewRequestIdentity,
): VerifiedPreview {
  if (candidate === null || typeof candidate !== "object" || Array.isArray(candidate)) {
    throw new Error("Malformed quantity preview response");
  }
  const c = candidate as Record<string, unknown>;
  // A stale HTTP response, even from a legitimate endpoint, is not a preview
  // for the newly selected object or revision. Never show it as current.
  if (c.commandId !== request.commandId ||
      c.targetObjectId !== request.targetObjectId ||
      c.previousObjectRevision !== request.targetRevisionHash) {
    throw new Error("Quantity preview does not match the selected source revision");
  }
  if (c.accepted !== true || c.validationState !== "valid_preview_only" ||
      c.requiresApproval !== true || c.persisted !== false ||
      c.commercialPublicationAllowed !== false) {
    throw new Error("Quantity preview has invalid approval or publication authority");
  }
  if (typeof c.previewObjectRevision !== "string" ||
      !c.previewObjectRevision ||
      !Array.isArray(c.quantityImpacts) ||
      c.quantityImpacts.length > 500 ||
      !Array.isArray(c.blockingReasons) ||
      c.blockingReasons.length !== 0) {
    throw new Error("Malformed quantity preview result");
  }
  for (const v of c.quantityImpacts as unknown[]) {
    if (!v || typeof v !== "object" || Array.isArray(v)) {
      throw new Error("Malformed quantity impact");
    }
    const q = v as Record<string, unknown>;
    if (typeof q.target !== "string" || !q.target ||
        typeof q.status !== "string" || !q.status ||
        typeof q.unit !== "string" ||
        !finiteNumberOrNull(q.oldValue) ||
        !finiteNumberOrNull(q.proposedValue) ||
        !(q.reason === null || typeof q.reason === "string")) {
      throw new Error("Malformed quantity impact values");
    }
  }
  return candidate as VerifiedPreview;
}
