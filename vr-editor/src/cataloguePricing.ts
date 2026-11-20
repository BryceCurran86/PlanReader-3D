import type { PlacedItem } from "./itemPlacement.ts";
import { makeItemHostId } from "./itemPlacement.ts";
import type { EditorObject, SceneManifest } from "./types.ts";

export function catalogueQuantityOwner(scene: SceneManifest, item: PlacedItem): EditorObject | undefined {
  const surface = scene.sourceSurfaces?.find(entry => entry.kind === item.target &&
    makeItemHostId(entry.kind, entry.surfaceId) === item.hostId);
  return scene.objects.find(row => row.renderState === "verified" && row.canonicalObjectId &&
    row.quantityLinks.length > 0 && (surface ? row.objectId === surface.objectId :
      item.target === "wall" && row.objectType === "wall" && makeItemHostId("wall", row.objectId) === item.hostId));
}

export type CataloguePriceRequest = SceneManifest["scope"] & {
  requestId: string; objectId: string; objectRevision: string; canonicalObjectId: string;
  quantityId: string; catalogueItemId: string;
};
export type CataloguePrice = {
  quantity: string; unit: string; currency: string; priceIncTax: string;
  rateKey: string; rateBookRevision: string;
};

export function verifyCataloguePrice(value: unknown, request: CataloguePriceRequest): CataloguePrice {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw Error("Malformed material price");
  const raw = value as Record<string, unknown>;
  const keys = Object.keys(request) as (keyof CataloguePriceRequest)[];
  const text = (x: unknown) => typeof x === "string" && x.length > 0 && x.length <= 180;
  const evidence = (x: unknown) => Array.isArray(x) && x.length > 0 && x.length <= 64 && x.every(text);
  if (keys.some(key => raw[key] !== request[key]) || raw.accepted !== true ||
      raw.previewOnly !== true || raw.commercialPublicationAllowed !== false ||
      typeof raw.currency !== "string" || !/^[A-Z]{3}$/.test(raw.currency) ||
      typeof raw.quantity !== "string" || !/^\d{1,10}(\.\d{1,18})?$/.test(raw.quantity) ||
      Number(raw.quantity) <= 0 ||
      typeof raw.priceIncTax !== "string" || !/^\d{1,13}\.\d{2}$/.test(raw.priceIncTax) ||
      ![raw.unit, raw.rateKey, raw.rateBookRevision].every(text) ||
      !evidence(raw.bindingEvidenceIds) || !evidence(raw.rateEvidenceIds)) {
    throw Error("Material price is missing or belongs to another quantity, item or revision");
  }
  return raw as CataloguePrice;
}
