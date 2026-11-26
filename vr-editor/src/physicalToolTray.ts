import * as THREE from "three";
import type {MenuLayout} from "./catalogueMenu.ts";
const CAP=128;
const base=0x31434b,disabled=0x29343a,selected=0x287a71,hovered=0x409c8d;
/** One instanced draw for all physical keys and one for samples. Label texture
 * remains separate and static while pointing. No allocation/upload per hover. */
export function createPhysicalToolTray(parent:THREE.Object3D){
 const geometry=new THREE.BoxGeometry(1,1,1);
 const material=new THREE.MeshBasicMaterial({color:0xffffff,depthTest:false,depthWrite:false,toneMapped:false});
 const keys=new THREE.InstancedMesh(geometry,material,CAP);
 const samples=new THREE.InstancedMesh(geometry,material,CAP);
 keys.renderOrder=20;samples.renderOrder=21;
 keys.frustumCulled=false;samples.frustumCulled=false;
 keys.count=samples.count=0;parent.add(keys,samples);
 const transform=new THREE.Object3D(),colour=new THREE.Color();
 let layout:MenuLayout|null=null,lastHover=-1;
 const tint=(index:number,highlight:boolean)=>{
  if(!layout||index<0||index>=keys.count)return;
  const b=layout.buttons[index];
  keys.setColorAt(index,colour.setHex(b.disabled?disabled:highlight?hovered:b.active?selected:base));
 };
 function update(next:MenuLayout){
  if(!Number.isFinite(next.width)||!Number.isFinite(next.height)||next.width<=0||next.height<=0){layout=null;lastHover=-1;keys.count=samples.count=0;return;}
  layout=next;lastHover=-1;
  keys.visible=samples.visible=!next.radial;
  keys.count=next.radial?0:Math.min(CAP,next.buttons.length);samples.count=0;
  const w=next.width,h=next.height;
  for(let i=0;i<keys.count;i++){
   const b=next.buttons[i],x=(b.x+b.w/2)/w-.5,y=.5-(b.y+b.h/2)/h;
   transform.position.set(x,y,-.012);
   transform.scale.set(b.w/w*.975,b.h/h*.93,.022);
   transform.updateMatrix();keys.setMatrixAt(i,transform.matrix);tint(i,false);
   if(b.swatch!==undefined){
    const n=samples.count++;
    transform.position.set((b.x+24)/w-.5,y,.002);
    transform.scale.set(29/w,30/h,.012);transform.updateMatrix();
    samples.setMatrixAt(n,transform.matrix);samples.setColorAt(n,colour.setHex(b.swatch));
   }
  }
  keys.instanceMatrix.needsUpdate=true;if(keys.instanceColor)keys.instanceColor.needsUpdate=true;
  samples.instanceMatrix.needsUpdate=true;if(samples.instanceColor)samples.instanceColor.needsUpdate=true;
 }
 function highlight(index:number){
  if(index===lastHover)return;
  tint(lastHover,false);tint(index,true);lastHover=index;
  if(keys.instanceColor)keys.instanceColor.needsUpdate=true;
 }
 return {keys,samples,update,highlight,dispose(){parent.remove(keys,samples);keys.dispose();samples.dispose();geometry.dispose();material.dispose();}};
}
