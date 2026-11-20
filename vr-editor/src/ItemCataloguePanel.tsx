import { useMemo, useRef, useState } from "react";
import {
  CATALOGUE_GROUPS, catalogueGroupLabel, getCatalogueItem, itemCanRotate, searchCatalogue,
} from "./itemCatalogue";
import type { CatalogueGroup, CatalogueItem } from "./itemCatalogue";
import { itemGuide, itemSchedule, itemScheduleCsv } from "./itemPlacement";
import type { PlacedItem } from "./itemPlacement";
import { CATALOGUE_DRAG_TYPE } from "./constructionStages";

const PAGE_SIZE = 16;
type Props = {
  active: CatalogueItem | undefined;
  items: readonly PlacedItem[];
  canUndo: boolean;
  turn: number;
  onChoose: (id: string) => void;
  onCancel: () => void;
  onRotate: () => void;
  onUndo: () => void;
  onRemove: (id: string) => void;
};

export function ItemCataloguePanel({
  active, items, canUndo, turn, onChoose, onCancel, onRotate, onUndo, onRemove,
}: Props) {
  const [group, setGroup] = useState<CatalogueGroup | "">("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const results = useRef<HTMLUListElement>(null);
  function changePage(index: number) {
    setPage(index);
    results.current?.scrollTo({ top: 0 });
  }
  const matches = useMemo(() => searchCatalogue(query, group || undefined), [query, group]);
  const pages = Math.max(1, Math.ceil(matches.length / PAGE_SIZE));
  const options = matches.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const rows = useMemo(() => itemSchedule(items), [items]);
  function downloadSchedule() {
    const file = new Blob(["\uFEFF", itemScheduleCsv(rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url;
    link.download = "planreader-draft-item-schedule.csv";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  return <div className="catalogue-panel" id="item-catalogue" aria-label="Materials and fixtures">
    <h2>Materials &amp; fixtures</h2>
    <div className="catalogue-fields">
      <label>Find an item
        <input type="search" value={query} placeholder="Try sliding door, slate or power point"
          onChange={event => { setQuery(event.currentTarget.value); changePage(0); }} />
      </label>
      <label>Category
        <select value={group} onChange={event => {
          setGroup(event.currentTarget.value as CatalogueGroup | "");
          changePage(0);
        }}>
          <option value="">All categories</option>
          {[...CATALOGUE_GROUPS].sort((a, b) => a[1].localeCompare(b[1])).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
      </label>
    </div>
    <p className="catalogue-count" role="status">{matches.length} matching {matches.length === 1 ? "item" : "items"}</p>
    {!matches.length && <p>Try another search or choose All categories.</p>}
    <ul className="catalogue-results" ref={results}>
      {options.map(item => <li key={item.id}>
        <button type="button" draggable aria-pressed={active?.id === item.id} onClick={() => onChoose(item.id)}
          onDragStart={event => {
            event.dataTransfer.setData(CATALOGUE_DRAG_TYPE, item.id);
            event.dataTransfer.effectAllowed = "copy";
            onChoose(item.id);
          }}>
          <span className="catalogue-swatch" style={{ backgroundColor: "#" +
            item.visual.color.toString(16).padStart(6, "0") }} aria-hidden="true" />
          <span><strong>{item.label}</strong><small>{catalogueGroupLabel(item.group)}</small></span>
        </button>
      </li>)}
    </ul>
    {pages > 1 && <div className="catalogue-actions catalogue-pagination" aria-label="Catalogue pages">
      <button type="button" disabled={page === 0} onClick={() => changePage(page - 1)}>Previous</button>
      <span>Page {page + 1} of {pages}</span>
      <button type="button" disabled={page >= pages - 1} onClick={() => changePage(page + 1)}>Next</button>
    </div>}
    {active && <section className="catalogue-instructions">
      <strong>{active.label}</strong>
      <p>{itemGuide(active)} Click to place or drag an item onto the scene.</p>
      <div className="catalogue-actions">
        {itemCanRotate(active) && <button type="button" onClick={onRotate}>
          Rotate · {turn * 90}°
        </button>}
        <button type="button" onClick={onCancel}>Done placing</button>
      </div>
    </section>}
    <details className="catalogue-schedule">
      <summary>Draft item schedule ({items.length})</summary>
      {rows.length ? <>
        <ul>{rows.map(row => <li key={row.itemId}>
          <span>{row.name}</span><strong>{row.placements}</strong>
        </li>)}</ul>
        <details>
          <summary>Individual placements</summary>
          <ul>{items.map((placement, index) => <li key={placement.id}>
            <span>{getCatalogueItem(placement.itemId)?.label} · {placement.target}</span>
            <button type="button" onClick={() => onRemove(placement.id)}
              aria-label={"Remove placement " + (index + 1)}>Remove</button>
          </li>)}</ul>
        </details>
        <button type="button" onClick={downloadSchedule}>Download schedule CSV</button>
        <p>Counts show selections and fittings placed in this draft.</p>
      </> : <p>Choose an item and place it in the scene to start the schedule.</p>}
    </details>
    <button type="button" disabled={!canUndo} onClick={onUndo}>Undo item placement</button>
  </div>;
}
