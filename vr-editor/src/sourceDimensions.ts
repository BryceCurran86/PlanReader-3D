/** Read-only source witness labels for existing planar wall faces.
 * Never derive commercial quantity/area or fill missing heights.
 */
import type { EditorObject } from "./types";

export interface SourceWallDimensions {
  objectId: string; lengthMetres: number; heightMetres: number;
  label: string; source: string;
}
export function sourceWallDimensions(row:EditorObject):SourceWallDimensions|null {
  const g=row.geometry;
  if(row.objectType!=="wall" || row.renderState!=="verified" ||
      row.unresolvedIssues.length || !row.canonicalObjectId ||
      !row.objectRevision || !row.source.sourceFileId ||
      !row.source.originalGeometryRef || !g || g.kind!=="wallFace")
    return null;
  const [x1,y1]=g.start,[x2,y2]=g.end;
  const length=Math.hypot(x2-x1,y2-y1);
  if(!Number.isFinite(length)||length<=0||length>10000||
      !Number.isFinite(g.heightM)||g.heightM<=0||g.heightM>1000)
    return null;
  const source=`${row.source.sheet??"drawing"} p.${row.source.page??"?"}`;
  return {
    objectId:row.objectId,lengthMetres:length,heightMetres:g.heightM,
    label:`${length.toFixed(3)} m × ${g.heightM.toFixed(3)} m · SOURCE REVIEW`,
    source,
  };
}
export function sourceDimensionCount(rows:readonly EditorObject[]):number {
  return rows.filter(row=>sourceWallDimensions(row)!==null).length;
}
