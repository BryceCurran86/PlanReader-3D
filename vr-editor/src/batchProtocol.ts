/** Strictly untrusted batch response checks, no pricing or approval semantics. */
import { verifyPreviewResponse } from "./previewProtocol.ts";
import type { VerifiedPreview } from "./previewProtocol";
import type { BatchPreviewRequest } from "./batchRequest";

export interface VerifiedBatchPreview {
  receipt: string;
  commands: VerifiedPreview[];
  status: "review_only";
}

export function verifyBatchPreview(
  raw: unknown, request: BatchPreviewRequest,
): VerifiedBatchPreview {
  if (!raw || typeof raw !== "object" || Array.isArray(raw))
    throw new Error("Malformed batch response");
  const x = raw as Record<string, unknown>;
  if (x.accepted !== true || x.validationState !== "valid_batch_preview_only" ||
      x.persisted !== false || x.commercialPublicationAllowed !== false ||
      x.requiresApproval !== true || x.rateEstimateAvailable !== false ||
      x.simulationMode !== "independent_same_base_not_cumulative" ||
      !Array.isArray(x.blockingReasons) || x.blockingReasons.length !== 0 ||
      typeof x.batchReceiptSha256 !== "string" ||
      !/^[a-f0-9]{64}$/.test(x.batchReceiptSha256) ||
      !Array.isArray(x.commandPreviews) ||
      x.commandPreviews.length !== request.commands.length ||
      request.commands.length === 0 || request.commands.length > 20) {
    throw new Error("Batch approval, source or pricing contract rejected");
  }
  const previews = x.commandPreviews.map((item, index) => {
    const cmd = request.commands[index];
    const result = verifyPreviewResponse(item, {
      commandId: cmd.commandId, targetObjectId: cmd.targetObjectId,
      targetRevisionHash: cmd.targetRevisionHash,
    });
    // Prevent a swapped response/duplicate echo even if other IDs match.
    const candidate = item as Record<string, unknown>;
    if (candidate.idempotencyKey !== cmd.idempotencyKey)
      throw new Error("Batch idempotency mismatch");
    return result;
  });
  return { receipt: x.batchReceiptSha256, commands: previews, status: "review_only" };
}
