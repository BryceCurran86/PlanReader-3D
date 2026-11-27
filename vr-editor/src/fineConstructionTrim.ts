import * as THREE from "three";
import {mergeGeometries} from "three/addons/utils/BufferGeometryUtils.js";
import {nominalTrimLayout} from "./constructionTrimVisual.ts";
import {trimRun} from "./catalogueGeometry.ts";
import {architraveMitres} from "./architraveMitres.ts";
import {skirtingEndCuts,applySkirtingCuts} from "./skirtingMitres.ts";
import {openingFits,planLength} from "./buildPlacement.ts";
import type {WallVisual,CeilingDraft} from "./buildPlacement.ts";
import {wallAssembly,profileDetails} from "./wallProfiles.ts";
import type {WallCornerJoins} from "./wallCornerJoin.ts";
const EPS=1e-6,ARCH=.067,DEPTH=.015;
function basis(wall:WallVisual){
 const l=planLength(wall.start,wall.end),a=wallAssembly(wall.assembly);
 if(!Number.isFinite(l)||l<.05)return null;
 const along=new THREE.Vector3((wall.end[0]-wall.start[0])/l,0,(wall.end[1]-wall.start[1])/l),up=new THREE.Vector3(0,1,0),left=new THREE.Vector3(-along.z,0,along.x);
 const sides=profileDetails(a).role==="internal"?[1,-1]:[a.exteriorSide==="left"?-1:1];
 const point=(x:number,y:number,side:number)=>new THREE.Vector3(wall.start[0],y,wall.start[1]).addScaledVector(along,x).addScaledVector(left,side*(a.thicknessMm/2000+.001));
 return {l,a,along,up,left,sides,point};
}
function collect(mesh:THREE.Mesh,parts:THREE.BufferGeometry[]){
 const g=mesh.geometry.index?mesh.geometry.toNonIndexed():mesh.geometry;
 if(g!==mesh.geometry)mesh.geometry.dispose();
 // Standardise attributes across the mouldings and cornices before merging.
 for(const key of Object.keys(g.attributes))if(!["position","normal","uv"].includes(key))g.deleteAttribute(key);
 parts.push(g);(Array.isArray(mesh.material)?mesh.material:[mesh.material]).forEach(m=>m.dispose());
}
function batch(parts:THREE.BufferGeometry[],name:string){
 if(!parts.length)return null;
 const g=mergeGeometries(parts,false);parts.forEach(p=>p.dispose());if(!g)return null;
 const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:0xf4f1e8,roughness:.61,side:THREE.DoubleSide}));m.name=name;m.receiveShadow=true;m.userData.illustrativeTrim=true;m.visible=false;return m;
}
/** Replace box trim with moulded profiles. Complete door architraves use
 * complementary mitres; clipped/near-corner openings retain safe fragments. */
export function fineTrimMesh(wall:WallVisual,joins?:WallCornerJoins){
 const b=basis(wall),layout=nominalTrimLayout(wall);if(!b||!layout.length)return null;
 const {l,a,along,up,left,sides,point}=b,parts:THREE.BufferGeometry[]=[];
 const arch={kind:"trim",profile:"pencil",widthM:ARCH,depthM:DEPTH,color:0xf4f1e8} as const;
 const openings=(wall.openings??[]).filter(o=>openingFits(wall,o));
 const full=openings.filter(o=>o.openingKind==="door"&&o.offsetM>=ARCH&&o.offsetM+o.widthM+ARCH<=l&&o.sillHeightM+o.heightM+ARCH<=wall.heightM&&o.heightM>ARCH*2&&openings.every(q=>q===o||q.offsetM>=o.offsetM+o.widthM+2*ARCH||q.offsetM+q.widthM+2*ARCH<=o.offsetM));
 for(const side of sides){
  const normal=left.clone().multiplyScalar(side),cuts=skirtingEndCuts(wall.start,wall.end,a.thicknessMm/2000,normal,joins);
  for(const o of full){
   const top=o.sillHeightM+o.heightM;
   const group=architraveMitres(point(o.offsetM,top,side),point(o.offsetM+o.widthM,top,side),o.sillHeightM,normal,arch);
   for(const child of group.children)if(child instanceof THREE.Mesh)collect(child,parts);
  }
  for(const p of layout){
   if(p.kind==="architrave"&&full.some(o=>p.x0>=o.offsetM-ARCH-EPS&&p.x1<=o.offsetM+o.widthM+ARCH+EPS&&p.y0>=o.sillHeightM-EPS&&p.y1<=o.sillHeightM+o.heightM+ARCH+EPS))continue;
   const start=point(p.x0,p.y0,side),end=point(p.x1,p.y0,side),width=p.y1-p.y0;
   const m=trimRun(start,end,up,normal,{kind:"trim",profile:p.kind==="skirting"?"pencil":"square",widthM:width,depthM:DEPTH,color:0xf4f1e8});
   if(!m)continue;
   if(p.kind==="skirting")applySkirtingCuts(m,start,end,normal,DEPTH,cuts,p.x0<EPS,p.x1>=l-EPS);
   collect(m,parts);
  }
 }
 const mesh=batch(parts,"Profiled skirting and architraves");if(mesh)mesh.userData.trimLayout=layout;return mesh;
}
export type CorniceRun={side:number;start:number;end:number};
/** Only a matching explicit room ceiling can supply a cornice contact. No
 * invented edge through a ceiling gap, higher ceiling or opening. */
export function corniceContactRuns(wall:WallVisual,ceilings:readonly CeilingDraft[]):CorniceRun[]{
 const b=basis(wall);if(!b)return [];
 const result:CorniceRun[]=[];
 for(const side of b.sides){
  const p=b.point(0,wall.heightM,side).addScaledVector(b.left,side*.025),dir=b.along;
  const intervals:{start:number;end:number}[]=[];
  for(const c of ceilings){
   if(c.scopeKey!==wall.scopeKey||c.levelId!==wall.levelId||Math.abs(c.heightM-wall.heightM)>.005)continue;
   let lo=0,hi=b.l;
   for(const [v,d,min,max] of [[p.x,dir.x,Math.min(c.start[0],c.end[0]),Math.max(c.start[0],c.end[0])],[p.z,dir.z,Math.min(c.start[1],c.end[1]),Math.max(c.start[1],c.end[1])]]){
    if(Math.abs(d)<EPS){if(v<min-EPS||v>max+EPS){hi=-1;break;}}
    else{const a=(min-v)/d,z=(max-v)/d;lo=Math.max(lo,Math.min(a,z));hi=Math.min(hi,Math.max(a,z));}
   }
   if(hi-lo>.025)intervals.push({start:lo,end:hi});
  }
  intervals.sort((a,b)=>a.start-b.start);const merged:{start:number;end:number}[]=[];
  for(const i of intervals){const last=merged.at(-1);if(last&&i.start<=last.end+EPS)last.end=Math.max(last.end,i.end);else merged.push({...i});}
  let clear=merged;
  for(const o of wall.openings??[])if(openingFits(wall,o)&&o.sillHeightM+o.heightM>wall.heightM-.055)clear=clear.flatMap(r=>[{start:r.start,end:Math.min(r.end,o.offsetM)},{start:Math.max(r.start,o.offsetM+o.widthM),end:r.end}].filter(i=>i.end-i.start>.025));
  for(const i of clear)result.push({side,...i});
 }
 return result;
}
export function corniceMesh(wall:WallVisual,runs:readonly CorniceRun[],joins?:WallCornerJoins){
 const b=basis(wall);if(!b||!runs.length)return null;
 const parts:THREE.BufferGeometry[]=[];
 for(const r of runs){
  const normal=b.left.clone().multiplyScalar(r.side),start=b.point(r.start,wall.heightM,r.side),end=b.point(r.end,wall.heightM,r.side),len=r.end-r.start;
  if(len<=.025)continue;
  // Concave cove profile with a small lip at the ceiling and wall edges.
  const s=new THREE.Shape();s.moveTo(0,0);s.lineTo(.055,0);s.lineTo(.055,.004);
  for(let j=1;j<=8;j++){const t=j*Math.PI/16;s.lineTo(.004+.051*Math.cos(t),.004+.051*Math.sin(t));}
  s.lineTo(0,.055);s.closePath();
  const g=new THREE.ExtrudeGeometry(s,{depth:len,bevelEnabled:false});
  g.applyMatrix4(new THREE.Matrix4().makeBasis(normal,b.up.clone().negate(),b.along).setPosition(start));
  const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial());
  const cuts=skirtingEndCuts(wall.start,wall.end,b.a.thicknessMm/2000,normal,joins);
  applySkirtingCuts(m,start,end,normal,.055,cuts,r.start<EPS,r.end>=b.l-EPS);
  collect(m,parts);
 }
 const m=batch(parts,"Coved wall-to-ceiling cornice");if(m)m.userData.nominalCornice=true;return m;
}
