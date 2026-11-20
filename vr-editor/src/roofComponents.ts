import type { CatalogueItem, RoofComponentVisual } from "./itemCatalogue.ts";
import type { SourceSurface } from "./sourceSurfaces.ts";

type Vertex = SourceSurface["vertices"][number];
type EdgeKind = "eave" | "verge" | "ridge" | "valley" | "junction";
export type RoofEdge = { key: string; from: Vertex; to: Vertex; kind: EdgeKind; interior: Vertex };
type EdgeUse = { id: string; from: Vertex; to: Vertex; interior: Vertex };

// Match coincident triangle endpoints at the precision of the source surface geometry.
const keyFor = (point: Vertex) => point.map(value => Math.round(value * 100000)).join(",");
const tolerance = 0.001;

function acrossSlope({ from, to, interior }: EdgeUse) {
  const dx = to[0] - from[0], dz = to[2] - from[2];
  const span = dx * dx + dz * dz;
  if (span < tolerance * tolerance) return 0;
  const position = ((interior[0] - from[0]) * dx + (interior[2] - from[2]) * dz) / span;
  return interior[1] - (from[1] + position * (to[1] - from[1]));
}

export function roofEdges(surfaces: readonly SourceSurface[]) {
  const uses = new Map<string, EdgeUse[]>();
  for (const surface of surfaces) {
    if (surface.kind !== "roof") continue;
    const vertices = surface.vertices;
    for (let i = 0; i < vertices.length; i += 3) {
      for (let j = 0; j < 3; j++) {
        const a = vertices[i + j], b = vertices[i + (j + 1) % 3];
        const aKey = keyFor(a), bKey = keyFor(b);
        if (aKey === bKey || Math.hypot(a[0] - b[0], a[2] - b[2]) < 0.05) continue;
        const first = aKey < bKey;
        const key = first ? aKey + "/" + bKey : bKey + "/" + aKey;
        const entries = uses.get(key) ?? [];
        entries.push({ id: surface.surfaceId, from: first ? a : b, to: first ? b : a,
          interior: vertices[i + (j + 2) % 3] });
        uses.set(key, entries);
      }
    }
  }
  const bySurface = new Map<string, RoofEdge[]>();
  for (const [key, entries] of uses) {
    if (entries.length > 2) continue;
    const [first, second] = entries;
    const slope = acrossSlope(first);
    let kind: EdgeKind;
    if (!second) {
      kind = Math.abs(first.from[1] - first.to[1]) <= tolerance && slope >= -tolerance
        ? "eave" : "verge";
    } else {
      const otherSlope = acrossSlope(second);
      const delta = (entry: EdgeUse) => {
        const {from, to, interior} = entry;
        return (to[0] - from[0]) * (interior[2] - from[2]) - (to[2] - from[2]) * (interior[0] - from[0]);
      };
      const d1 = delta(first), d2 = delta(second);
      if (d1 * d2 >= 0) continue;
      // Coplanar triangulation seams are not construction edges.
      if (Math.abs(slope / d1 - otherSlope / d2) <= tolerance) continue;
      kind = slope > tolerance && otherSlope > tolerance ? "valley" :
        slope < -tolerance && otherSlope < -tolerance ? "ridge" : "junction";
    }
    for (const entry of second?.id === first.id ? [first] : entries) {
      const edges = bySurface.get(entry.id) ?? [];
      edges.push({ key, kind, from: entry.from, to: entry.to, interior: entry.interior });
      bySurface.set(entry.id, edges);
    }
  }
  return bySurface;
}

export function roofEdgeFits(visual: RoofComponentVisual, edge: RoofEdge) {
  if (visual.profile === "ridge") return edge.kind === "ridge";
  if (visual.profile === "valley") return edge.kind === "valley";
  if (visual.component === "gutter" || visual.profile === "eaves") return edge.kind === "eave";
  if (visual.profile === "barge") return edge.kind === "verge";
  return edge.kind === "eave" || edge.kind === "verge" || edge.kind === "junction";
}

export function nearestRoofEdge(edges: readonly RoofEdge[], visual: RoofComponentVisual, point: Vertex) {
  let nearest: RoofEdge | undefined, distance = 0.35;
  for (const edge of edges) {
    if (!roofEdgeFits(visual, edge)) continue;
    const dx = edge.to[0] - edge.from[0], dy = edge.to[1] - edge.from[1], dz = edge.to[2] - edge.from[2];
    const x = point[0] - edge.from[0], y = point[1] - edge.from[1], z = point[2] - edge.from[2];
    const t = Math.min(1, Math.max(0, (x * dx + y * dy + z * dz) / (dx * dx + dy * dy + dz * dz)));
    const gap = Math.hypot(x - dx * t, y - dy * t, z - dz * t);
    if (gap < distance) { nearest = edge; distance = gap; }
  }
  return nearest;
}

const finishes = [["Zinc", 0xabb5b8], ["Off white", 0xe4e2d9], ["Slate grey", 0x747a7e], ["Charcoal", 0x45494d]] as const;
const profiles: readonly [string, RoofComponentVisual["component"], RoofComponentVisual["profile"]][] = [
  ["Quad gutter", "gutter", "quad"], ["Half-round gutter", "gutter", "half-round"], ["Square gutter", "gutter", "square"],
  ["Eaves fascia", "fascia", "eaves"], ["Barge fascia", "fascia", "barge"],
  ["Apron flashing", "flashing", "apron"], ["Barge flashing", "flashing", "barge"],
  ["Ridge capping", "flashing", "ridge"], ["Valley flashing", "flashing", "valley"],
];
export const ROOF_COMPONENTS: CatalogueItem[] = profiles.flatMap(([name, component, profile]) =>
  finishes.map(([finish, color], index) => ({
    id: "roof-" + name.toLowerCase().replaceAll(" ", "-") + "-" + (index + 1),
    label: name + " · " + finish, group: "roof-components", targets: ["roof"],
    keywords: "roof roofline gutter fascia flashing ridge capping rainwater lock up",
    visual: { kind: "roof-component", component, profile, color },
  })),
);
