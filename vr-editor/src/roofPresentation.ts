import type {DraftShell} from "./connectedDraftShell.ts";
type V=[number,number,number];
type Kind="skin"|"soffit"|"fascia"|"gutter";
type Part={kind:Kind;vertices:V[]};
const EPS=1e-6;
/** The canonical roof includes vertical gable closure triangles. Treat these
 * as wall infill rather than applying metal roofing to the entire facade. */
export function roofSkinAndGables(vertices:readonly V[]){
 const skin:V[]=[],gables:V[]=[];
 for(let i=0;i+2<vertices.length;i+=3){
  const [a,b,c]=vertices.slice(i,i+3);
  const area=Math.abs((b[0]-a[0])*(c[2]-a[2])-(b[2]-a[2])*(c[0]-a[0]));
  (area>EPS?skin:gables).push(a,b,c);
 }
 return {skin,gables};
}
/** Presentation-only eaves, continuous mitred corners and gutters for an
 * unambiguous rectangular, axis-aligned flat/gable roof. Never extrapolate
 * over concave plans or invent hips/valleys. Does not change shell quantities. */
export function roofPresentationParts(shell:DraftShell):Part[]{
 const roof=shell.surfaces.find(s=>s.kind==="roof");if(!roof)return [];
 const {skin}=roofSkinAndGables(roof.vertices);if(skin.length<6)return [];
 const minX=Math.min(...skin.map(p=>p[0])),maxX=Math.max(...skin.map(p=>p[0])),minZ=Math.min(...skin.map(p=>p[2])),maxZ=Math.max(...skin.map(p=>p[2]));
 const w=maxX-minX,d=maxZ-minZ;if(w<1||d<1||w>200||d>200)return [];
 const near=(a:number,b:number)=>Math.abs(a-b)<EPS;
 const key=(p:V)=>p.map(n=>Math.round(n*1e6)).join(",");
 const edges=new Map<string,{a:V;b:V;n:number}>();
 let area=0;
 for(let i=0;i<skin.length;i+=3){
  const [a,b,c]=skin.slice(i,i+3);area+=Math.abs((b[0]-a[0])*(c[2]-a[2])-(b[2]-a[2])*(c[0]-a[0]))/2;
  for(const [p,q] of [[a,b],[b,c],[c,a]]){const k=[key(p),key(q)].sort().join("|"),e=edges.get(k);if(e)e.n++;else edges.set(k,{a:p,b:q,n:1});}
 }
 if(Math.abs(area-w*d)>1e-5*Math.max(1,w*d))return [];
 const boundary=[...edges.values()].filter(e=>e.n===1);
 if(!boundary.length||boundary.some(({a,b})=>!((near(a[0],b[0])&&(near(a[0],minX)||near(a[0],maxX)))||(near(a[2],b[2])&&(near(a[2],minZ)||near(a[2],maxZ))))))return [];
 const low=Math.min(...skin.map(p=>p[1])),high=Math.max(...skin.map(p=>p[1])),rise=high-low;
 const flat=rise<EPS;
 const eaveX=boundary.filter(({a,b})=>near(a[0],b[0])&&near(a[1],low)&&near(b[1],low)).length;
 const eaveZ=boundary.filter(({a,b})=>near(a[2],b[2])&&near(a[1],low)&&near(b[1],low)).length;
 if(!flat&&((eaveX>0)===(eaveZ>0)))return [];
 const slope=flat?0:rise/((eaveX?w:d)/2);
 const overhang=.30;
 const outer=(p:V):V=>{
  const dx=near(p[0],minX)?-overhang:near(p[0],maxX)?overhang:0,dz=near(p[2],minZ)?-overhang:near(p[2],maxZ)?overhang:0;
  return [p[0]+dx,p[1]-slope*(eaveX?Math.abs(dx):Math.abs(dz)),p[2]+dz];
 };
 const result:Record<Kind,V[]>={skin:[],soffit:[],fascia:[],gutter:[]};
 const quad=(kind:Kind,a:V,b:V,c:V,d:V)=>result[kind].push(a,b,c,a,c,d);
 const down=(p:V,h:number):V=>[p[0],p[1]-h,p[2]];
 for(const {a,b} of boundary){
  const A=outer(a),B=outer(b);
  quad("skin",a,b,B,A);
  quad("soffit",down(a,.08),down(A,.14),down(B,.14),down(b,.08));
  quad("fascia",A,B,down(B,.17),down(A,.17));
  if(!flat&&(!near(a[1],low)||!near(b[1],low)))continue;
  const nx=near(a[0],b[0])?(near(a[0],minX)?-1:1):0,nz=near(a[2],b[2])?(near(a[2],minZ)?-1:1):0;
  const offset=(p:V,t:number,y:number):V=>[p[0]+nx*t,p[1]-y,p[2]+nz*t];
  // Recessed open gutter trough with a folded outer lip, not a solid box.
  const i=offset(A,.015,.14),j=offset(B,.015,.14),k=offset(B,.13,.14),l=offset(A,.13,.14);
  quad("gutter",i,j,k,l);
  quad("gutter",l,k,offset(B,.13,.055),offset(A,.13,.055));
  quad("gutter",offset(A,.13,.055),offset(B,.13,.055),offset(B,.115,.055),offset(A,.115,.055));
  quad("gutter",offset(A,.015,.045),offset(B,.015,.045),j,i);
 }
 return (Object.keys(result) as Kind[]).filter(kind=>result[kind].length).map(kind=>({kind,vertices:result[kind]}));
}
