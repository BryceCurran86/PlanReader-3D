/** Geometry-safe source mesh acceptance; never infer rooms from wall endpoints.
 * These triangles are supplied by an independently authenticated server
 * producer and NEVER used by the client to issue quantity or money.
 */
import type { EditorObject, WorkspaceScope } from "./types.ts";

export type SourceSurfaceKind = "floor" | "ceiling" | "roof";
export interface SourceSurface {
  surfaceId: string;
  objectId: string;
  objectRevision: string;
  canonicalObjectId: string;
  kind: SourceSurfaceKind;
  vertices: [number, number, number][];
  areaM2: number;
  geometryEvidenceId: string;
  triangulationEvidenceId: string;
  originalGeometryRef: string;
  sourceSha256: string;
  snapshotId: string;
  renderState: "verified";
  commercialAuthority: false;
}
function xyz(point: unknown): point is [number, number, number] {
  return Array.isArray(point) && point.length === 3 &&
    point.every(v => typeof v === "number" && Number.isFinite(v) &&
      Math.abs(v) <= 10000);
}
function area(a:number[], b:number[], c:number[]) {
  const u=[b[0]-a[0],b[1]-a[1],b[2]-a[2]],
    v=[c[0]-a[0],c[1]-a[1],c[2]-a[2]];
  return 0.5*Math.hypot(
    u[1]*v[2]-u[2]*v[1],
    u[2]*v[0]-u[0]*v[2],
    u[0]*v[1]-u[1]*v[0],
  );
}
export function validatedSourceSurfaces(
  rows: readonly EditorObject[], scope: WorkspaceScope, raw: unknown,
): SourceSurface[] {
  if (raw === undefined) return [];
  if (!Array.isArray(raw) || raw.length > 20000)
    throw new Error("Invalid source surfaces payload");
  const objects = new Map(rows.map(row => [row.objectId,row]));
  const result:SourceSurface[]=[];
  const seen = new Set<string>();
  let totalTriangles=0;
  for(const rawItem of raw) {
    if (!rawItem || typeof rawItem !== "object" || Array.isArray(rawItem))
      throw new Error("Malformed source surface");
    const s=rawItem as Record<string,unknown>;
    const row=objects.get(s.objectId as string);
    if (!row || typeof s.surfaceId !== "string" || !s.surfaceId ||
        seen.has(s.surfaceId) || !["floor","ceiling","roof"].includes(String(s.kind)) ||
        !Array.isArray(s.vertices) || s.vertices.length<3 ||
        s.vertices.length%3!==0 || s.vertices.length>6000 ||
        !s.vertices.every(xyz) || typeof s.areaM2!=="number" ||
        !Number.isFinite(s.areaM2) || s.areaM2<=0 || s.areaM2>100000 ||
        typeof s.canonicalObjectId!=="string" ||
        s.canonicalObjectId!==row.canonicalObjectId ||
        s.objectRevision!==row.objectRevision ||
        s.originalGeometryRef!==row.source.originalGeometryRef ||
        s.sourceSha256!==scope.sourceSha256 ||
        s.snapshotId!==scope.snapshotId ||
        typeof s.geometryEvidenceId!=="string" || !s.geometryEvidenceId ||
        typeof s.triangulationEvidenceId!=="string" ||
        !s.triangulationEvidenceId ||
        s.geometryEvidenceId===s.triangulationEvidenceId ||
        s.renderState!=="verified" || s.commercialAuthority!==false)
      throw new Error("Source surface authority, revision or geometry rejected");
    if ((s.kind==="floor"||s.kind==="ceiling") &&
        !["room","surface"].includes(row.objectType) ||
        s.kind==="roof" && !["roof","surface"].includes(row.objectType))
      throw new Error("Source surface object type mismatch");
    let computed=0;
    const v=s.vertices as [number,number,number][];
    for(let i=0;i<v.length;i+=3) {
      const a=area(v[i],v[i+1],v[i+2]);
      if(a<=0.000001)throw new Error("Degenerate source triangle");
      computed+=a;
    }
    if ((s.kind==="floor"||s.kind==="ceiling") &&
        Math.max(...v.map(p=>p[1]))-Math.min(...v.map(p=>p[1]))>0.001)
      throw new Error("Unverified sloped floor or ceiling");
    if (Math.abs(computed-s.areaM2 as number) > Math.max(0.005,0.001*(s.areaM2 as number)))
      throw new Error("Source triangulation and area mismatch");
    totalTriangles+=v.length/3;
    if(totalTriangles>20000)throw new Error("Source triangle scene cap exceeded");
    seen.add(s.surfaceId as string);
    result.push(s as unknown as SourceSurface);
  }
  return result;
}
