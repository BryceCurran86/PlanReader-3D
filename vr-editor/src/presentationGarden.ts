import * as THREE from "three";
type Bounds={minX:number;maxX:number;minZ:number;maxZ:number};
/** Decorative only. Never a source object, physical collision host, or quantity.
 * Bound to a small local starter footprint, not an imported customer's site. */
export function createPresentationGarden(scene:THREE.Scene){
 const group=new THREE.Group();group.name="IllustrativeGarden";scene.add(group);
 const geom=new THREE.BoxGeometry(1,1,1),leafGeometry=new THREE.IcosahedronGeometry(1,2);
 const timber=new THREE.MeshStandardMaterial({color:0xffffff,roughness:.93});
 const leaves=new THREE.MeshStandardMaterial({color:0xffffff,roughness:.96});
 const boxes=new THREE.InstancedMesh(geom,timber,256),crowns=new THREE.InstancedMesh(leafGeometry,leaves,96);
 boxes.name="Garden fence, paving and edging";crowns.name="Garden foliage";
 group.add(boxes,crowns);boxes.count=crowns.count=0;
 const obj=new THREE.Object3D(),colour=new THREE.Color();let key="";
 function add(mesh:THREE.InstancedMesh,x:number,y:number,z:number,sx:number,sy:number,sz:number,hex:number,rotation=0){
  if(mesh.count>=mesh.instanceMatrix.count)return;
  const i=mesh.count++;obj.position.set(x,y,z);obj.scale.set(sx,sy,sz);obj.rotation.y=rotation;obj.updateMatrix();mesh.setMatrixAt(i,obj.matrix);mesh.setColorAt(i,colour.setHex(hex));
 }
 function update(bounds:Bounds|null,visible:boolean){
  group.visible=visible&&!!bounds;if(!group.visible||!bounds)return;
  const {minX,maxX,minZ,maxZ}=bounds;
  if(![minX,maxX,minZ,maxZ].every(Number.isFinite)||maxX<=minX||maxZ<=minZ||maxX-minX>35||maxZ-minZ>35){group.visible=false;return;}
  const next=[minX,maxX,minZ,maxZ].join(":");if(next===key)return;key=next;boxes.count=crowns.count=0;
  const left=minX-3,right=maxX+3,back=maxZ+3;
  // Fence panels in a neutral charcoal, with regular posts and top rail.
  for(let i=0;i<Math.ceil((right-left)/.8);i++){const x=left+(i+.5)*.8;if(x>right)break;add(boxes,x,.85,back,.78,1.7,.06,0x626c68);}
  for(const x of [left,right])for(let i=0;i<Math.ceil((back-minZ)/.8);i++){const z=minZ+(i+.5)*.8;if(z>back)break;add(boxes,x,.85,z,.06,1.7,.78,0x626c68);}
  for(const x of [left+.9,right-.9])for(const z of [minZ+1.4,maxZ+1.7]){
   add(boxes,x,.95,z,.15,1.9,.15,0x756149);
   for(let i=0;i<5;i++){const a=i*Math.PI*2/5;add(crowns,x+Math.cos(a)*.47,2.25+(i%2)*.32,z+Math.sin(a)*.47,.82,.9,.76,[0x466542,0x607c47,0x769050][i%3]);}
  }
  // Continuous low garden beds, separate edging and a varied planting layer.
  // Instancing preserves the same two landscape draw calls.
  const bedWidth=right-left-.45;
  add(boxes,(left+right)/2,.015,back-.58,bedWidth,.04,.94,0x796b55);
  add(boxes,(left+right)/2,.045,back-1.06,bedWidth,.09,.10,0xaaa69b);
  for(const x of [left+.53,right-.53]){
   const run=back-minZ-1.0;
   add(boxes,x,.015,minZ+.3+run/2,.83,.04,run,0x81715b);
   add(boxes,x+(x<minX?.47:-.47),.045,minZ+.3+run/2,.09,.09,run,0xaaa69b);
   for(let i=0;i<7;i++){const z=minZ+.65+(run-.7)*i/6,scale=.29+(i%3)*.07;add(crowns,x,.16+scale*.3,z,scale,.23+scale*.27,scale*.8,[0x466542,0x789056,0x627b48][i%3],i*.71);}
  }
  for(let i=0;i<11;i++){const x=left+1+(right-left-2)*i/10,scale=.35+(i%4)*.08;add(crowns,x,.28,back-.58,scale,.38+(i%3)*.08,scale*.88,i%2?0x73945d:0x55794b,i*.8);}
  const pathX=(minX+maxX)/2;
  // Thin paving slabs set into a contrasting compacted-gravel strip.
  add(boxes,pathX,-.006,minZ-1.6,1.12,.026,2.8,0x99958a);
  for(let i=0;i<5;i++)add(boxes,pathX,.012,minZ-.55-i*.53,.94,.026,.48,[0xb9b6a9,0xc0bdb0,0xb2afa3][i%3]);
  for(const mesh of [boxes,crowns]){mesh.instanceMatrix.needsUpdate=true;if(mesh.instanceColor)mesh.instanceColor.needsUpdate=true;mesh.computeBoundingSphere();mesh.receiveShadow=true;}
 }
 return {update,dispose(){boxes.dispose();crowns.dispose();geom.dispose();leafGeometry.dispose();timber.dispose();leaves.dispose();scene.remove(group);}};
}
