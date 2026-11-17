/** Source-gated WebXR teleport planning for PS VR2/SteamVR.
 *
 * A presentation-only shadow plane or a room without independently verified
 * source floor triangles may NEVER authorise a teleport. The planar floor
 * must be at the current local-floor stage (Y ~= 0); vertical transitions,
 * stair jumps and wall collision safety need additional source evidence.
 */
import type { SceneManifest } from "./types.ts";

export type TeleportReason =
  | "ok" | "no_verified_source_floor" | "stale_floor_source"
  | "invalid_target" | "outside_floor_triangle" | "unsafe_floor_edge"
  | "vertical_level_not_supported" | "too_far" | "too_close";
export type TeleportResult = {
  accepted: boolean;
  reason: TeleportReason;
  destination?: [number,number,number];
  distanceM?: number;
};

const MAX_STEP_M = 7;
const MIN_STEP_M = .20;
const FLOOR_LEVEL_TOLERANCE_M = .05;
const BOUNDARY_MARGIN_M = .12;
const EPS = 1e-9;
type Point3 = [number,number,number];
type Point2 = [number,number];

function vec3(p:unknown): p is Point3 {
  return Array.isArray(p) && p.length === 3 &&
    p.every(n=>typeof n==="number"&&Number.isFinite(n)&&Math.abs(n)<10000);
}
function cross(a:Point2,b:Point2,c:Point2):number {
  return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
}
function pointToEdgeDistance(p:Point2,a:Point2,b:Point2):number {
  const vx=b[0]-a[0],vz=b[1]-a[1];
  const length=Math.hypot(vx,vz);
  if(length<EPS) return 0;
  const t=Math.max(0,Math.min(1,
    ((p[0]-a[0])*vx+(p[1]-a[1])*vz)/(length*length)));
  return Math.hypot(p[0]-(a[0]+t*vx),p[1]-(a[1]+t*vz));
}
function floorPointIsInside(
  vertices:readonly Point3[],target:Point2,
):"inside"|"edge"|"outside" {
  // Triangle source sets may be triangulated: interior shared diagonals
  // are NOT construction boundaries. Use their union, then check only the
  // external perimeter edges across source triangles.
  let found=false;
  const candidateEdges:Array<[Point2,Point2]>=[];
  for(let i=0;i<vertices.length;i+=3) {
    const a:Point2=[vertices[i][0],vertices[i][2]],
      b:Point2=[vertices[i+1][0],vertices[i+1][2]],
      c:Point2=[vertices[i+2][0],vertices[i+2][2]];
    const triangle=cross(a,b,c);
    if(Math.abs(triangle)<=EPS)continue;
    const s1=cross(a,b,target),s2=cross(b,c,target),s3=cross(c,a,target);
    if((s1>=-EPS&&s2>=-EPS&&s3>=-EPS) ||
       (s1<=EPS&&s2<=EPS&&s3<=EPS))found=true;
    candidateEdges.push([a,b],[b,c],[c,a]);
  }
  if(!found)return "outside";
  // An interior seam appears twice regardless of winding, and must not
  // wrongly block a safe teleport. Small floor polygons still get a margin.
  const edgeKey=(a:Point2,b:Point2)=>{
    const pa=a.map(n=>n.toFixed(5)).join(","),
      pb=b.map(n=>n.toFixed(5)).join(",");
    return [pa,pb].sort().join("|");
  };
  const counts=new Map<string,number>();
  for(const [a,b] of candidateEdges){
    const k=edgeKey(a,b);counts.set(k,(counts.get(k)??0)+1);
  }
  for(const [a,b] of candidateEdges){
    if(counts.get(edgeKey(a,b))===1 &&
       pointToEdgeDistance(target,a,b)<BOUNDARY_MARGIN_M)
      return "edge";
  }
  return "inside";
}

/** Verify a raycast hit against the actual source-authorised floor triangles.
 * This is presentation locomotion only, not structural or collision approval.
 */
export function evaluateSourceFloorTeleport(
  manifest:SceneManifest,surfaceId:string,
  hit:unknown,viewer:unknown,
):TeleportResult {
  const fail=(reason:TeleportReason):TeleportResult=>({accepted:false,reason});
  if(!vec3(hit)||!vec3(viewer))return fail("invalid_target");
  const surface=manifest.sourceSurfaces?.find(row=>row.surfaceId===surfaceId);
  if(!surface||surface.kind!=="floor"||surface.renderState!=="verified"||
     surface.commercialAuthority!==false) return fail("no_verified_source_floor");
  const obj=manifest.objects.find(row=>row.objectId===surface.objectId);
  if(!obj || surface.objectRevision!==obj.objectRevision ||
     surface.sourceSha256!==manifest.scope.sourceSha256 ||
     surface.snapshotId!==manifest.scope.snapshotId ||
     surface.canonicalObjectId!==obj.canonicalObjectId ||
     surface.originalGeometryRef!==obj.source.originalGeometryRef)
    return fail("stale_floor_source");
  const floorY=surface.vertices[0]?.[1];
  if(floorY===undefined||!Number.isFinite(floorY)||
     Math.abs(floorY)>FLOOR_LEVEL_TOLERANCE_M ||
     Math.abs(hit[1]-floorY)>.02)
    return fail("vertical_level_not_supported");
  const point:[number,number]=[hit[0],hit[2]];
  const footprint=floorPointIsInside(surface.vertices,point);
  if(footprint==="outside")return fail("outside_floor_triangle");
  if(footprint==="edge")return fail("unsafe_floor_edge");
  const distanceM=Math.hypot(hit[0]-viewer[0],hit[2]-viewer[2]);
  if(distanceM>MAX_STEP_M)return fail("too_far");
  if(distanceM<MIN_STEP_M)return fail("too_close");
  return {accepted:true,reason:"ok",destination:[hit[0],0,hit[2]],distanceM};
}
export function describeTeleportReason(reason:TeleportReason):string {
  const explanations:Record<TeleportReason,string>={
    ok:"Verified floor destination ready",
    no_verified_source_floor:"No source-verified floor available for teleportation",
    stale_floor_source:"The floor does not match the active drawing revision",
    invalid_target:"Invalid controller ray target",
    outside_floor_triangle:"Target lies outside documented floor geometry",
    unsafe_floor_edge:"Move farther from the edge of the floor",
    vertical_level_not_supported:"Changing floor level requires an approved stair or lift route",
    too_far:"Teleport is limited to 7 metres per step",
    too_close:"Choose a destination at least 20 cm away",
  };
  return explanations[reason];
}
