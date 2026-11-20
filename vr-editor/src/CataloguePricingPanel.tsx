import { useEffect, useMemo, useState } from "react";
import { catalogueQuantityOwner, verifyCataloguePrice } from "./cataloguePricing";
import type { CataloguePrice, CataloguePriceRequest } from "./cataloguePricing";
import { getCatalogueItem } from "./itemCatalogue";
import type { PlacedItem } from "./itemPlacement";
import type { SceneManifest } from "./types";

export function CataloguePricingPanel({ scene, items, authenticated }: {
  scene: SceneManifest; items: readonly PlacedItem[]; authenticated: boolean;
}) {
  const selectable = useMemo(() => items.flatMap(item => {
    const owner = catalogueQuantityOwner(scene, item);
    return owner ? [{ item, owner }] : [];
  }), [scene, items]);
  const [itemId, setItem] = useState("");
  const [quantityId, setQuantity] = useState("");
  const [live, setLive] = useState(false);
  const [display, setDisplay] = useState<{ identity: string; result?: CataloguePrice; status?: string } | null>(null);
  const choice = selectable.find(row => row.item.id === itemId);
  const owner = choice?.owner;
  const chosenQuantity = owner?.quantityLinks.includes(quantityId) ? quantityId :
    owner?.quantityLinks.length === 1 ? owner.quantityLinks[0] : "";
  const identity = owner && choice && chosenQuantity
    ? JSON.stringify([scene.scope, owner.objectRevision, choice.item.id, choice.item.itemId, chosenQuantity]) : "";
  useEffect(() => {
    if (!live || !authenticated || !owner?.canonicalObjectId || !choice || !chosenQuantity || !identity) return;
    const controller = new AbortController();
    async function preview() {
      const csrf = document.querySelector<HTMLMetaElement>('meta[name="planreader-csrf-token"]')?.content;
      if (!csrf) {
        setDisplay({ identity, status: "The workspace does not provide an authenticated pricing session." });
        return;
      }
      const request: CataloguePriceRequest = { ...scene.scope,
        sourceSha256: scene.scope.sourceSha256.toLowerCase(),
        requestId: crypto.randomUUID(), objectId: owner!.objectId, objectRevision: owner!.objectRevision,
        canonicalObjectId: owner!.canonicalObjectId!, quantityId: chosenQuantity, catalogueItemId: choice!.item.itemId };
      try {
        const response = await fetch("/api/editor/workspaces/" + encodeURIComponent(scene.scope.workspaceId) + "/costing/catalogue", {
          method: "POST", credentials: "same-origin", cache: "no-store", signal: controller.signal,
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify(request),
        });
        const raw = await response.json();
        if (controller.signal.aborted) return;
        if (!response.ok) {
          const status = raw.error === "catalogue_rate_not_linked"
            ? "Your company rate book has no rate for this material and quantity."
            : "Verified material pricing is unavailable for this selection.";
          setDisplay({ identity, status });
          return;
        }
        setDisplay({ identity, result: verifyCataloguePrice(raw, request) });
      } catch {
        if (!controller.signal.aborted) setDisplay({ identity, status: "Verified material pricing is unavailable for this selection." });
      }
    }
    const timer = window.setTimeout(() => void preview(), 400);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [live, authenticated, owner, choice, chosenQuantity, scene, identity]);
  const current = live && display?.identity === identity ? display : null;
  return <details className="construction-pricing">
    <summary>Live material pricing</summary>
    {!authenticated || !selectable.length ? <p>Place a material on an authenticated source object with a linked construction quantity.</p> : <>
      <label>Material
        <select value={itemId} onChange={event => { setItem(event.currentTarget.value); setQuantity(""); setDisplay(null); }}>
          <option value="">Choose a placement</option>
          {selectable.map(({ item, owner: target }) => <option key={item.id} value={item.id}>
            {getCatalogueItem(item.itemId)?.label} · {target.source.sheet ?? target.objectId}
          </option>)}
        </select>
      </label>
      {owner && <label>Verified quantity
        <select value={chosenQuantity} onChange={event => { setQuantity(event.currentTarget.value); setDisplay(null); }}>
          <option value="">Choose a linked quantity</option>
          {owner.quantityLinks.map(id => <option key={id}>{id}</option>)}
        </select>
      </label>}
      <label><input type="checkbox" checked={live} onChange={event => { setLive(event.currentTarget.checked); setDisplay(null); }} /> Live price preview</label>
      {live && identity && <p role="status">{current?.result ? <>
        {current.result.quantity} {current.result.unit} · {current.result.currency} {current.result.priceIncTax} incl. tax
        <br /> Company rate {current.result.rateKey} · revision {current.result.rateBookRevision}
      </> : current?.status ?? "Checking verified quantity and company rate…"}</p>}
    </>}
  </details>;
}
