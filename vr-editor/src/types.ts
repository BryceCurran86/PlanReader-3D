// Browser DTO mirrors pb_vr_editor_scene_manifest.py, never the geometry source of truth.
import { validatedSourceSurfaces } from "./sourceSurfaces.ts";
import type { SourceSurface } from "./sourceSurfaces";
export interface WorkspaceScope {
  workspaceId: string;
  projectId: string;
  documentId: string;
  revisionId: string;
  snapshotId: string;
  sourceSha256: string;
  modelRevision: number;
}

export type DisplayGeometry =
  | { kind: "wallFace"; start: [number, number]; end: [number, number]; heightM: number }
  | { kind: "wallLine"; start: [number, number]; end: [number, number] };

export interface EditorObject {
  objectId: string;
  canonicalObjectId: string | null;
  objectType: string;
  levelId: string | null;
  objectRevision: string;
  authority: string;
  renderState: "verified" | "review";
  geometry: DisplayGeometry | null;
  dimensions: Record<string, number>;
  source: {
    sourceFileId: string | null;
    page: number | string | null;
    sheet: string | null;
    sourceRegion: string | null;
    originalGeometryRef: string | null;
    currentGeometryRef: string | null;
  };
  quantityLinks: string[];
  unresolvedIssues: string[];
  canEdit: false;
}

export interface SceneManifest {
  schemaVersion: "1.0.0";
  scope: WorkspaceScope;
  coordinateSystem: {
    unit: "metres";
    sourceToModelTransform: null;
    renderOrigin: [number, number, number];
  };
  readOnly: true;
  objects: EditorObject[];
  sourceSurfaces?: SourceSurface[];
  commercialQuantityPublicationAllowed: false;
}

// Validate every browser-facing field. A remote HTTP response or manually
// imported JSON is not source authority just because TypeScript expects a type.
function finitePoint(v: unknown): v is [number, number] {
  return Array.isArray(v) && v.length === 2
    && v.every(n => typeof n === "number" && Number.isFinite(n));
}

function finiteWorldOrigin(v: unknown): v is [number, number, number] {
  return Array.isArray(v) && v.length === 3
    && v.every(n => typeof n === "number" && Number.isFinite(n));
}

function validObject(value: unknown): value is EditorObject {
  if (!value || typeof value !== "object") return false;
  const o = value as Record<string, unknown>;
  if (typeof o.objectId !== "string" || !o.objectId.trim()
    || typeof o.objectType !== "string"
    || typeof o.objectRevision !== "string"
    || typeof o.authority !== "string" || !o.authority
    || !["verified", "review"].includes(String(o.renderState))
    || o.canEdit !== false
    || !(o.canonicalObjectId === null || typeof o.canonicalObjectId === "string")
    || !(o.levelId === null || typeof o.levelId === "string")
    || !Array.isArray(o.quantityLinks)
    || !o.quantityLinks.every(q => typeof q === "string")
    || !Array.isArray(o.unresolvedIssues)
    || !o.unresolvedIssues.every(reason => typeof reason === "string")
    || (o.renderState === "verified" && o.unresolvedIssues.length > 0)) return false;
  const dims = o.dimensions;
  if (!dims || typeof dims !== "object" || Array.isArray(dims)
      || !Object.values(dims).every(v => typeof v === "number" && Number.isFinite(v))) return false;
  const source = o.source;
  if (!source || typeof source !== "object" || Array.isArray(source)) return false;
  const trace = source as Record<string, unknown>;
  if (!["sourceFileId", "sheet", "sourceRegion", "originalGeometryRef", "currentGeometryRef"]
    .every(k => trace[k] === null || typeof trace[k] === "string")) return false;
  if (!(trace.page === null || typeof trace.page === "string"
        || (typeof trace.page === "number" && Number.isSafeInteger(trace.page)
            && trace.page >= 0))) return false;
  const geom = o.geometry;
  if (geom === null) return true;
  if (o.objectType !== "wall") return false;
  if (!geom || typeof geom !== "object" || Array.isArray(geom)) return false;
  const g = geom as Record<string, unknown>;
  if (!finitePoint(g.start) || !finitePoint(g.end)) return false;
  if (g.kind === "wallLine") return true;
  return g.kind === "wallFace" && typeof g.heightM === "number"
    && Number.isFinite(g.heightM) && g.heightM > 0;
}

export function isSceneManifest(value: unknown): value is SceneManifest {
  if (!value || typeof value !== "object") return false;
  const x = value as Partial<SceneManifest>;
  const s = x.scope;
  const c = x.coordinateSystem;
  const baseline = x.schemaVersion === "1.0.0"
    && x.readOnly === true
    && x.commercialQuantityPublicationAllowed === false
    && !!s && typeof s.workspaceId === "string" && !!s.workspaceId
    && typeof s.projectId === "string" && !!s.projectId
    && typeof s.documentId === "string" && !!s.documentId
    && typeof s.revisionId === "string" && !!s.revisionId
    && typeof s.snapshotId === "string" && !!s.snapshotId
    && typeof s.sourceSha256 === "string"
    && /^[a-fA-F0-9]{64}$/.test(s.sourceSha256)
    && Number.isSafeInteger(s.modelRevision) && s.modelRevision >= 0
    && !!c && c.unit === "metres"
    && c.sourceToModelTransform === null
    && finiteWorldOrigin(c.renderOrigin)
    && Array.isArray(x.objects)
    && x.objects.length <= 20000
    && x.objects.every(validObject)
    && new Set(x.objects.map(o => o.objectId)).size === x.objects.length;
  if (!baseline) return false;
  try {
    validatedSourceSurfaces(x.objects as EditorObject[], s as WorkspaceScope,
      x.sourceSurfaces);
  } catch {
    return false;
  }
  return true;
}
