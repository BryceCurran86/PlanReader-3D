// Browser DTO mirrors pb_vr_editor_scene_manifest.py, never the geometry source of truth.
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
  commercialQuantityPublicationAllowed: false;
}

// Treat local and remotely fetched manifest data as untrusted. Fail closed on
// unknown schemas / unexpected permission flags rather than drawing trusted UI.
export function isSceneManifest(value: unknown): value is SceneManifest {
  if (!value || typeof value !== "object") return false;
  const x = value as Partial<SceneManifest>;
  const s = x.scope;
  return x.schemaVersion === "1.0.0"
    && x.readOnly === true
    && x.commercialQuantityPublicationAllowed === false
    && !!s && typeof s.workspaceId === "string"
    && typeof s.documentId === "string"
    && typeof s.revisionId === "string"
    && typeof s.snapshotId === "string"
    && typeof s.sourceSha256 === "string"
    && /^[a-fA-F0-9]{64}$/.test(s.sourceSha256)
    && Number.isSafeInteger(s.modelRevision)
    && Array.isArray(x.objects)
    && x.objects.length <= 20000
    && x.objects.every((o) =>
      !!o && typeof o.objectId === "string"
      && o.canEdit === false
      && Array.isArray(o.unresolvedIssues)
    );
}
