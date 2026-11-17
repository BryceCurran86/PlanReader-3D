/** Treat live costing HTTP as untrusted presentation data, NEVER quote authority. */
import { verifyPreviewResponse } from "./previewProtocol.ts";
import type { PreviewRequestIdentity, VerifiedPreview } from "./previewProtocol";

const MONEY = /^\d{1,13}\.\d{2}$/;
const SIGNED_MONEY = /^-?\d{1,13}\.\d{2}$/;
const SHA = /^[a-f0-9]{64}$/;
const FIELDS = [
  "material", "waste", "labour", "subcontract", "plant", "direct",
  "overhead", "contingency", "costBeforeMargin", "margin",
  "sellExTax", "tax", "sellIncTax",
] as const;
type CostField = typeof FIELDS[number];
export type MoneyComponents = Record<CostField, string>;
export interface CostLine {
  target: string;
  rateKey: string;
  rateRevision: string;
  rateEvidenceIds: string[];
  bindingEvidenceIds: string[];
  previousQuantity: string;
  proposedQuantity: string;
  unit: string;
  before: MoneyComponents;
  after: MoneyComponents;
  deltaIncTax: string;
}
export interface CostUnpriced { target: string; reason: string }
export interface VerifiedCostPreview {
  accepted: true;
  validationState: "cost_preview_only";
  commandId: string;
  targetObjectId: string;
  previousObjectRevision: string;
  previewObjectRevision: string;
  workspaceId: string;
  snapshotId: string;
  rateBookRevision: string;
  currency: string;
  taxPct: string;
  contingencyPct: string;
  pricedComplete: boolean;
  partialTotalsOnly: boolean;
  quoteReady: false;
  requiresApproval: true;
  persisted: false;
  commercialPublicationAllowed: false;
  lines: CostLine[];
  unpriced: CostUnpriced[];
  totals: { before: MoneyComponents; after: MoneyComponents; delta: MoneyComponents };
  costPreviewReceiptSha256: string;
}
export interface LiveCostResponse {
  accepted: true;
  quantityPreview: VerifiedPreview;
  costingPreview: VerifiedCostPreview;
}
export interface CostRequestIdentity extends PreviewRequestIdentity {
  workspaceId: string;
  snapshotId: string;
}
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Malformed live costing response");
  return value as Record<string, unknown>;
}
function cents(value: string): bigint {
  const negative = value.startsWith("-");
  const clean = negative ? value.slice(1) : value;
  const [major, minor] = clean.split(".");
  const result = BigInt(major) * 100n + BigInt(minor);
  return negative ? -result : result;
}
function money(value: unknown, signed = false): value is string {
  return typeof value === "string" &&
    (signed ? SIGNED_MONEY : MONEY).test(value);
}
function amounts(value: unknown, signed = false): MoneyComponents {
  const x = object(value);
  if (!FIELDS.every(field => money(x[field], signed)))
    throw new Error("Incomplete exact-cent live cost component");
  return x as unknown as MoneyComponents;
}
function foots(x: MoneyComponents): void {
  const total = (...fields: CostField[]) =>
    fields.reduce((n, field) => n + cents(x[field]), 0n);
  if (cents(x.direct) !== total("material", "waste", "labour", "subcontract", "plant") ||
      cents(x.costBeforeMargin) !== total("direct", "overhead", "contingency") ||
      cents(x.sellExTax) !== total("costBeforeMargin", "margin") ||
      cents(x.sellIncTax) !== total("sellExTax", "tax"))
    throw new Error("Live cost components do not foot to the cent");
}
function positiveText(v: unknown): v is string {
  return typeof v === "string" && v.length > 0 && v.length <= 256;
}
function receipts(v: unknown): v is string[] {
  return Array.isArray(v) && v.length > 0 && v.length <= 32 &&
    v.every(positiveText) && new Set(v).size === v.length;
}
/** Bind a quote-shaped response to the exact current user request/scene. */
export function verifyLiveCostingResponse(
  candidate: unknown,
  request: CostRequestIdentity,
): LiveCostResponse {
  const outer = object(candidate);
  if (outer.accepted !== true)
    throw new Error("Live costing request was not accepted");
  const quantityPreview = verifyPreviewResponse(outer.quantityPreview, request);
  const cost = object(outer.costingPreview);
  if (cost.accepted !== true || cost.validationState !== "cost_preview_only" ||
      cost.commandId !== request.commandId ||
      cost.targetObjectId !== request.targetObjectId ||
      cost.previousObjectRevision !== request.targetRevisionHash ||
      cost.previewObjectRevision !== quantityPreview.previewObjectRevision ||
      cost.workspaceId !== request.workspaceId ||
      cost.snapshotId !== request.snapshotId ||
      cost.quoteReady !== false || cost.persisted !== false ||
      cost.requiresApproval !== true ||
      cost.commercialPublicationAllowed !== false ||
      !positiveText(cost.rateBookRevision) ||
      typeof cost.currency !== "string" || !/^[A-Z]{3}$/.test(cost.currency) ||
      typeof cost.taxPct !== "string" ||
      typeof cost.contingencyPct !== "string" ||
      !/^(?:\d{1,3})(?:\.\d+)?$/.test(cost.taxPct) ||
      !/^(?:\d{1,3})(?:\.\d+)?$/.test(cost.contingencyPct) ||
      typeof cost.costPreviewReceiptSha256 !== "string" ||
      !SHA.test(cost.costPreviewReceiptSha256))
    throw new Error("Live cost authority or current source revision mismatch");
  if (!Array.isArray(cost.lines) || !Array.isArray(cost.unpriced) ||
      cost.lines.length > 100 || cost.unpriced.length > 100 ||
      typeof cost.pricedComplete !== "boolean" ||
      cost.partialTotalsOnly !== !cost.pricedComplete)
    throw new Error("Live cost pricing completeness invalid");
  const targetMap = new Map(quantityPreview.quantityImpacts.map(i => [i.target, i]));
  const seen = new Set<string>();
  const priced = cost.lines.map(item => {
    const line = object(item);
    const target = line.target;
    if (!positiveText(target) || seen.has(target) ||
        !targetMap.has(target) || targetMap.get(target)?.status !== "recalculated" ||
        !positiveText(line.rateKey) || line.rateRevision !== cost.rateBookRevision ||
        !receipts(line.rateEvidenceIds) || !receipts(line.bindingEvidenceIds) ||
        typeof line.unit !== "string" || !line.unit ||
        typeof line.previousQuantity !== "string" ||
        typeof line.proposedQuantity !== "string" ||
        !/^\d+(?:\.\d+)?$/.test(line.previousQuantity) ||
        !/^\d+(?:\.\d+)?$/.test(line.proposedQuantity) ||
        !money(line.deltaIncTax, true))
      throw new Error("Live cost line is not source-quantity-bound");
    seen.add(target);
    const before = amounts(line.before);
    const after = amounts(line.after);
    foots(before);
    foots(after);
    if (cents(line.deltaIncTax) !==
        cents(after.sellIncTax) - cents(before.sellIncTax))
      throw new Error("Cost line delta does not foot to the cent");
    return { ...line, before, after } as unknown as CostLine;
  });
  const unpriced = cost.unpriced.map(item => {
    const entry = object(item);
    if (!positiveText(entry.target) || !positiveText(entry.reason) ||
        seen.has(entry.target) || !targetMap.has(entry.target))
      throw new Error("Unpriced line has invalid target or reason");
    seen.add(entry.target);
    return { target: entry.target, reason: entry.reason };
  });
  if (seen.size !== quantityPreview.quantityImpacts.length ||
      cost.pricedComplete !== (priced.length > 0 && unpriced.length === 0))
    throw new Error("Not all source quantity impacts are accounted for");
  const totals = object(cost.totals);
  const before = amounts(totals.before);
  const after = amounts(totals.after);
  const delta = amounts(totals.delta, true);
  foots(before); foots(after);
  for (const field of FIELDS) {
    if (cents(before[field]) !== priced.reduce((n, l) => n + cents(l.before[field]), 0n) ||
        cents(after[field]) !== priced.reduce((n, l) => n + cents(l.after[field]), 0n) ||
        cents(delta[field]) !== cents(after[field]) - cents(before[field]))
      throw new Error("Live cost totals do not foot to the cent");
  }
  return {
    accepted: true, quantityPreview,
    costingPreview: { ...cost, lines: priced, unpriced,
      totals: { before, after, delta } } as VerifiedCostPreview,
  };
}
