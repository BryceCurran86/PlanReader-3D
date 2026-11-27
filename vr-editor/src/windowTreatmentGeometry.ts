import * as THREE from "three";
import type {OpeningStyle} from "./itemCatalogue.ts";
import {applyFixtureFabric} from "./fixtureFabric.ts";
/** Continuous draped fabric, not intersecting rectangular boards. Bounds and
 * mesh density are derived from the existing opening. */
export function drapedCurtainGeometry(width:number,height:number,depth:number,folds:number){
 const columns=Math.max(24,Math.min(192,Math.round(folds)*8)),rows=8;
 const pos:number[]=[],uv:number[]=[],idx:number[]=[];
 for(let y=0;y<=rows;y++)for(let x=0;x<=columns;x++){
  const u=x/columns,v=y/rows,angle=u*folds*Math.PI*2;
  const wave=Math.cos(angle)*(.75+.25*v);
  const hem=(1-v)*.008*(1-Math.cos(angle));
  pos.push((u-.5)*width,v*height+hem,depth*wave+.006*Math.sin(v*Math.PI)*Math.sin(angle*.5));
  uv.push(u*width/.04,v*height/.04);
 }
 for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
  const a=y*(columns+1)+x,b=a+1,d=a+columns+1,c=d+1;
  idx.push(a,b,c,a,c,d);
 }
 const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.Float32BufferAttribute(pos,3));g.setAttribute("uv",new THREE.Float32BufferAttribute(uv,2));g.setIndex(idx);g.computeVertexNormals();return g;
}
export function createWindowTreatment(spec:OpeningStyle,width:number,height:number){
 const group=new THREE.Group();
 if(!Number.isFinite(width)||!Number.isFinite(height)||width<.15||height<.15||width>20||height>10)return group;
 const w=width+.14,h=height+.12,depth=.10;
 const finish=new THREE.MeshStandardMaterial({color:spec.color,roughness:.72});
 const rail=new THREE.MeshStandardMaterial({color:0xaaa9a3,roughness:.45,metalness:.35});
 function box(x:number,y:number,z:number,sx:number,sy:number,sz:number,material=finish,name="Window treatment detail"){
  const mesh=new THREE.Mesh(new THREE.BoxGeometry(sx,sy,sz),material);mesh.position.set(x,y,z);mesh.name=name;mesh.receiveShadow=true;group.add(mesh);return mesh;
 }
 box(0,h+.01,depth,w+.05,.025,.035,rail,"Head rail");
 if(spec.style==="curtain"||spec.style==="sheer"){
  finish.roughness=.96;finish.side=THREE.DoubleSide;
  finish.transparent=spec.style==="sheer";finish.opacity=finish.transparent?.40:1;
  finish.depthWrite=!finish.transparent;
  for(const sign of [-1,1]){
   const panelWidth=w*.495;
   const mesh=new THREE.Mesh(drapedCurtainGeometry(panelWidth,h,.036,Math.max(4,Math.round(panelWidth/.09))),finish);
   mesh.position.set(sign*w*.25,0,depth);mesh.name="Pleated fabric panel";mesh.receiveShadow=true;group.add(mesh);
  }
  // Same material ownership and adaptive bump relief as upholstery.
  applyFixtureFabric(group,[finish]);
 }else if(spec.style==="roller"){
  const cloth=box(0,h*.58,depth,w,h*.84,.012,finish,"Roller blind fabric");
  cloth.castShadow=false;
  const roll=new THREE.Mesh(new THREE.CylinderGeometry(.025,.025,w,16),rail);
  roll.rotation.z=Math.PI/2;roll.position.set(0,h,depth);roll.name="Roller tube";group.add(roll);
  box(0,h*.16,depth,w,.018,.018,rail,"Bottom weight");
 }else{
  const vertical=spec.style==="vertical";
  const count=vertical?Math.max(4,Math.min(80,Math.ceil(w/.095))):spec.style==="roman"?6:spec.style==="shutter"?10:Math.max(8,Math.min(80,Math.ceil(h/.055)));
  const geometry=new THREE.BoxGeometry(1,1,1),mesh=new THREE.InstancedMesh(geometry,finish,count),o=new THREE.Object3D();
  for(let i=0;i<count;i++){
   if(vertical){o.position.set(-w/2+(i+.5)*w/count,h/2,depth);o.scale.set(w/count*.86,h,.014);o.rotation.set(0,.19,0);}
   else{o.position.set(0,(i+.5)*h/count,depth);o.scale.set(w,h/count*(spec.style==="roman"?1.02:.94),.018);o.rotation.set(spec.style==="venetian"?-.42:spec.style==="shutter"?-.20:0,0,0);}
   o.updateMatrix();mesh.setMatrixAt(i,o.matrix);
  }
  mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingSphere();mesh.name=vertical?"Vertical blind vanes":"Horizontal blind slats";mesh.receiveShadow=true;group.add(mesh);
  if(!vertical)box(0,.01,depth,w,.02,.025,rail,"Bottom rail");
 }
 return group;
}
