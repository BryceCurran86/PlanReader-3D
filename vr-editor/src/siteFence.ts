import * as THREE from "three";
export type FenceStyle="timber"|"colorbond"|"block"|"rendered";
export type FenceSettings={style:FenceStyle;heightM:number;color:string};
export type SiteBounds={minX:number;maxX:number;minZ:number;maxZ:number};
export const FENCE_STYLES:readonly FenceStyle[]=["timber","colorbond","block","rendered"];
export const DEFAULT_FENCE:FenceSettings={style:"colorbond",heightM:1.8,color:"#626c68"};
export function validSiteBounds(b:SiteBounds){return [b.minX,b.maxX,b.minZ,b.maxZ].every(n=>Number.isFinite(n)&&Math.abs(n)<=10000)&&b.maxX-b.minX>=.5&&b.maxZ-b.minZ>=.5&&b.maxX-b.minX<=200&&b.maxZ-b.minZ<=200;}
export function validFence(s:FenceSettings){return FENCE_STYLES.includes(s.style)&&Number.isFinite(s.heightM)&&s.heightM>=.6&&s.heightM<=3&&/^#[0-9a-f]{6}$/i.test(s.color);}
export function fenceTexture(style:FenceStyle){
 const size=64,data=new Uint8Array(size*size*4);
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){
  let v=255;
  if(style==="timber")v=x%16<2?105:220+Math.round(25*Math.sin(x*2+y*.13));
  if(style==="colorbond")v=205+Math.round(50*Math.sin(x*Math.PI/8)**2);
  if(style==="block")v=y%16<2||(x+(Math.floor(y/16)%2)*16)%32<2?145:239;
  const i=(y*size+x)*4;data[i]=data[i+1]=data[i+2]=v;data[i+3]=255;
 }
 const t=new THREE.DataTexture(data,size,size);t.colorSpace=THREE.SRGBColorSpace;t.wrapS=t.wrapT=THREE.RepeatWrapping;t.magFilter=THREE.LinearFilter;t.minFilter=THREE.LinearMipmapLinearFilter;t.generateMipmaps=true;t.needsUpdate=true;return t;
}
/** Presentation only, four surfaces, no collision or construction quantities. */
export function createSiteFence(scene:THREE.Scene){
 const group=new THREE.Group();group.name="Visual property fence";scene.add(group);let key="";
 const material=new THREE.MeshStandardMaterial({roughness:.92,side:THREE.DoubleSide});let texture:THREE.DataTexture|null=null;
 function clear(){for(const m of [...group.children]){group.remove(m);if(m instanceof THREE.Mesh)m.geometry.dispose();}}
 function update(bounds:SiteBounds|null,settings:FenceSettings,visible:boolean){
  group.visible=!!bounds&&visible&&validSiteBounds(bounds)&&validFence(settings);if(!group.visible||!bounds)return;
  const next=JSON.stringify([bounds,settings]);if(next===key)return;key=next;clear();texture?.dispose();texture=fenceTexture(settings.style);material.map=texture;material.color.set(settings.color);material.needsUpdate=true;
  const {minX,maxX,minZ,maxZ}=bounds,h=settings.heightM;
  const corners=[[minX,minZ],[maxX,minZ],[maxX,maxZ],[minX,maxZ]];
  for(let i=0;i<4;i++){const a=corners[i],b=corners[(i+1)%4],length=Math.hypot(b[0]-a[0],b[1]-a[1]);
   const g=new THREE.PlaneGeometry(length,h);const uv=g.getAttribute("uv");for(let j=0;j<uv.count;j++)uv.setXY(j,uv.getX(j)*length,uv.getY(j)*h);uv.needsUpdate=true;
   const m=new THREE.Mesh(g,material);m.position.set((a[0]+b[0])/2,h/2,(a[1]+b[1])/2);m.rotation.y=-Math.atan2(b[1]-a[1],b[0]-a[0]);group.add(m);
  }
 }
 return {update,dispose(){clear();texture?.dispose();material.dispose();scene.remove(group);}};
}
