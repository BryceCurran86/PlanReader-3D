import * as THREE from "three";
export const SLAB_KINDS=["house","garage","driveway","alfresco"] as const;
export type SlabKind=typeof SLAB_KINDS[number];
export type IndependentSlab={id:string;kind:SlabKind;levelId:string;x:number;z:number;widthM:number;depthM:number;topM:number;thicknessMm:number};
export function validSlab(s:IndependentSlab):boolean{return !!s&&typeof s.id==="string"&&s.id.length>0&&s.id.length<200&&typeof s.levelId==="string"&&s.levelId.length>0&&SLAB_KINDS.includes(s.kind)&&[s.x,s.z,s.widthM,s.depthM,s.topM,s.thicknessMm].every(n=>Number.isFinite(n)&&Math.abs(n)<=10000)&&s.widthM>=.2&&s.widthM<=100&&s.depthM>=.2&&s.depthM<=100&&s.thicknessMm>=50&&s.thicknessMm<=600&&Math.abs(s.topM)<=30;}
export function slabArea(s:IndependentSlab){return s.widthM*s.depthM;}
export function slabVolume(s:IndependentSlab){return slabArea(s)*s.thicknessMm/1000;}
export function slabCorners(s:IndependentSlab):[number,number][]{return [[s.x,s.z],[s.x+s.widthM,s.z],[s.x+s.widthM,s.z+s.depthM],[s.x,s.z+s.depthM]];}
export function readSlabs(raw:unknown,levels?:ReadonlySet<string>):IndependentSlab[]{
 if(raw===undefined)return [];
 if(!Array.isArray(raw)||raw.length>100)throw Error("Invalid independent slabs");
 const ids=new Set<string>();
 return raw.map(v=>{if(!validSlab(v)||ids.has(v.id)||(levels&&!levels.has(v.levelId)))throw Error("Invalid independent slab geometry");ids.add(v.id);const {id,kind,levelId,x,z,widthM,depthM,topM,thicknessMm}=v;return {id,kind,levelId,x,z,widthM,depthM,topM,thicknessMm};});
}
export function createIndependentSlabs(scene:THREE.Scene){
 const group=new THREE.Group();group.name="Independent local slabs";scene.add(group);
 const material=new THREE.MeshStandardMaterial({color:0xbdbab1,roughness:.93});
 let previous:readonly IndependentSlab[]|null=null,priorLevel="";
 function clear(){for(const child of [...group.children]){group.remove(child);if(child instanceof THREE.Mesh)child.geometry.dispose();}}
 function update(slabs:readonly IndependentSlab[],level:string){if(previous===slabs&&priorLevel===level)return;previous=slabs;priorLevel=level;clear();
 for(const s of slabs){if(!validSlab(s)||(level!=="all"&&s.levelId!==level))continue;const t=s.thicknessMm/1000,m=new THREE.Mesh(new THREE.BoxGeometry(s.widthM,t,s.depthM),material);m.position.set(s.x+s.widthM/2,s.topM-t/2,s.z+s.depthM/2);m.name=s.kind+" slab";m.receiveShadow=true;group.add(m);}
 }
 return {update,dispose(){clear();material.dispose();scene.remove(group);}};
}
