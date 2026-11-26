import type {CatalogueItem} from "./itemCatalogue.ts";
export const MAX_PREVIEW_LIGHTS=4;
export function previewLightingRole(item:CatalogueItem):"light"|"switch"|null{
 const v=item.visual;
 if(v.kind!=="fixture")return null;
 if(item.group==="electrical"&&v.shape==="switch")return "switch";
 return item.group==="lights"&&["downlight","batten","pendant","sconce"].includes(v.shape)?"light":null;
}
export function nearestPreviewLights<T extends {id:string;position:readonly [number,number,number]}>(fixtures:readonly T[],eye:readonly [number,number,number]):T[]{
 const distance=(p:readonly number[])=>(p[0]-eye[0])**2+(p[1]-eye[1])**2+(p[2]-eye[2])**2;
 if(!eye.every(Number.isFinite))return [];
 return fixtures.filter(f=>f.position.every(Number.isFinite)).map(f=>({f,d:distance(f.position)})).filter(x=>x.d<=100).sort((a,b)=>a.d-b.d||a.f.id.localeCompare(b.f.id)).slice(0,MAX_PREVIEW_LIGHTS).map(x=>x.f);
}
