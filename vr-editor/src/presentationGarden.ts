import * as THREE from "three";
type Bounds={minX:number;maxX:number;minZ:number;maxZ:number};
/** Decorative only. Never a source object, physical collision host, or quantity.
 * Bound to a small local starter footprint, not an imported customer's site. */
export function createPresentationGarden(scene:THREE.Scene){
 const group=new THREE.Group();group.name="IllustrativeGarden";scene.add(group);
 const geom=new THREE.BoxGeometry(1,1,1),leafGeometry=new THREE.IcosahedronGeometry(1,1);
 const timber=new THREE.MeshStandardMaterial({color:0xffffff,roughness:.93});
 const leaves=new THREE.MeshStandardMaterial({color:0xffffff,roughness:.96});
 const boxes=new THREE.InstancedMesh(geom,timber,192),crowns=new THREE.InstancedMesh(leafGeometry,leaves,80);
 group.add(boxes,crowns);boxes.count=crowns.count=0;
 const obj=new THREE.Object3D(),colour=new THREE.Color();let key="";
 function add(mesh:THREE.InstancedMesh,x:number,y:number,z:number,sx:number,sy:number,sz:number,hex:number){
  const i=mesh.count++;obj.position.set(x,y,z);obj.scale.set(sx,sy,sz);obj.updateMatrix();mesh.setMatrixAt(i,obj.matrix);mesh.setColorAt(i,colour.setHex(hex));
 }
 function update(bounds:Bounds|null,visible:boolean){
  group.visible=visible&&!!bounds;if(!group.visible||!bounds)return;
  const {minX,maxX,minZ,maxZ}=bounds;
  if(![minX,maxX,minZ,maxZ].every(Number.isFinite)||maxX-minX>35||maxZ-minZ>35){group.visible=false;return;}
  const next=JSON.stringify(bounds);if(next===key)return;key=next;boxes.count=crowns.count=0;
  const left=minX-3,right=maxX+3,back=maxZ+3;
  // Fence panels in a neutral charcoal, with regular posts and top rail.
  for(let i=0;i<Math.ceil((right-left)/.8);i++){const x=left+(i+.5)*.8;if(x>right)break;add(boxes,x,.85,back,.78,1.7,.06,0x626c68);}
  for(const x of [left,right])for(let i=0;i<Math.ceil((back-minZ)/.8);i++){const z=minZ+(i+.5)*.8;if(z>back)break;add(boxes,x,.85,z,.06,1.7,.78,0x626c68);}
  for(const x of [left+.9,right-.9])for(const z of [minZ+1.4,maxZ+1.7]){
   add(boxes,x,.95,z,.15,1.9,.15,0x756149);
   for(let i=0;i<5;i++){const a=i*Math.PI*2/5;add(crowns,x+Math.cos(a)*.47,2.25+(i%2)*.32,z+Math.sin(a)*.47,.82,.9,.76,[0x466542,0x607c47,0x769050][i%3]);}
  }
  for(let i=0;i<9;i++)add(crowns,left+1+(right-left-2)*i/8,.38,back-.55,.55,.48,.5,i%2?0x73945d:0x55794b);
  for(let i=0;i<5;i++)add(boxes,minX+5,.005,minZ-.55-i*.53,.92,.025,.45,0xb9b6a9);
  for(const mesh of [boxes,crowns]){mesh.instanceMatrix.needsUpdate=true;if(mesh.instanceColor)mesh.instanceColor.needsUpdate=true;mesh.computeBoundingSphere();mesh.receiveShadow=true;}
 }
 return {update,dispose(){geom.dispose();leafGeometry.dispose();timber.dispose();leaves.dispose();scene.remove(group);}};
}
