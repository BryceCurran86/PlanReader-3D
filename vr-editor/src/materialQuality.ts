import * as THREE from "three";
type DetailMaps={bumpMap:THREE.Texture|null;normalMap:THREE.Texture|null;roughnessMap:THREE.Texture|null};
const detail=new WeakMap<THREE.MeshStandardMaterial,DetailMaps>();
/** Switch only decorative micro-surface maps, retaining diffuse colour and geometry. */
export function applyMaterialDetailBudget(root:THREE.Object3D,enabled:boolean){
 root.traverse(node=>{
  if(!(node instanceof THREE.Mesh))return;
  for(const material of Array.isArray(node.material)?node.material:[node.material]){
   if(!(material instanceof THREE.MeshStandardMaterial))continue;
   let original=detail.get(material);
   if(!original){original={bumpMap:material.bumpMap,normalMap:material.normalMap,roughnessMap:material.roughnessMap};detail.set(material,original);}
   for(const key of ["bumpMap","normalMap","roughnessMap"] as const){
    const next=enabled?original[key]:null;
    if(material[key]!==next){material[key]=next;material.needsUpdate=true;}
   }
  }
 });
}
/** Owned material textures include temporarily detached maps, preventing leaks. */
export function ownedDetailTextures(material:THREE.MeshStandardMaterial){
 const saved=detail.get(material);
 return new Set([material.map,material.bumpMap,material.normalMap,material.roughnessMap,saved?.bumpMap,saved?.normalMap,saved?.roughnessMap].filter((map):map is THREE.Texture=>!!map));
}
