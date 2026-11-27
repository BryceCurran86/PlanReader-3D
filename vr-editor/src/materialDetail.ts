import * as THREE from "three";
import {photoTexture} from "./architecturalAssets.ts";
export type DetailPattern="plaster"|"plank"|"grain"|"tile"|"woven"|"fleck"|"stone"|"roof"|"concrete";
const SIZE=256;
const noise=(x:number,y:number)=>((Math.imul(x+197,374761393)^Math.imul(y+123,668265263))>>>0)%1021/1020;
const clamp=(v:number)=>Math.max(0,Math.min(255,Math.round(v)));
/** Deterministic neutral tintable albedo and relief, bounded 256² per map.
 * Physical dimensions are assigned by the renderer UV, not by evidence. */
export function detailPixels(pattern:DetailPattern,size=SIZE){
 if(!Number.isInteger(size)||size<1||size>512)throw new RangeError("Detail texture size must be an integer from 1 to 512");
 const albedo=new Uint8Array(size*size*4),relief=new Uint8Array(size*size*4);
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){
  const u=x/size,v=y/size,n=noise(x,y),fine=noise(x*3,y*7);
  let shade=245+n*5,height=126+fine*12;
  if(pattern==="plank"||pattern==="grain"){
   const warp=.012*Math.sin(v*2*Math.PI)+.005*Math.sin(v*6*Math.PI);
   const ring=Math.sin((u+warp)*Math.PI*2*13+Math.sin(v*2*Math.PI)*.7);
   const grain=Math.sin((u+warp*.6)*Math.PI*2*49+Math.sin(v*4*Math.PI));
   const broad=Math.sin(u*Math.PI*2*3+Math.sin(v*Math.PI*2)*.7);
   const pore=Math.pow(Math.max(0,ring),12);
   shade=226+broad*9+ring*7+grain*3-pore*13+n*5;height=143+ring*9+grain*4-pore*10;
   if(pattern==="plank"&&(u<.008||v<.004)){shade=142;height=91;}
  }else if(pattern==="tile"){
   const grout=u<.008||v<.008;shade=grout?152:238+n*10;height=grout?65:200;
  }else if(pattern==="woven"){
   shade=217+((x+y)%2)*15+n*12;height=105+(x%2)*42+(y%2)*29;
  }else if(pattern==="fleck"||pattern==="stone"){
   const vein=Math.sin(u*17+Math.sin(v*13)*2.7+v*11);
   shade=pattern==="stone"?234-Math.max(0,vein-.87)*150+n*9:221+n*28;
   height=pattern==="stone"?180:115+fine*50;
  }else if(pattern==="concrete"){
   // Subtle trowelled mottling and fine aggregate; tileable at the edges.
   const tau=Math.PI*2,cloud=Math.sin(tau*u*3+Math.sin(tau*v*2))*Math.cos(tau*v*3)+.4*Math.cos(tau*(u*5+v*4));
   const pore=fine>.985?18:0;shade=224+cloud*7+n*8-pore;height=136+cloud*4+fine*18-pore;
  }else if(pattern==="roof"){
   const groove=u<.018||u>.98;shade=groove?120:220+25*Math.sin(u*Math.PI);height=groove?60:155+35*Math.sin(u*Math.PI);
  }
  const i=(y*size+x)*4;
  albedo[i]=albedo[i+1]=albedo[i+2]=clamp(shade);albedo[i+3]=255;
  relief[i]=relief[i+1]=relief[i+2]=clamp(height);relief[i+3]=255;
 }
 return {albedo,relief};
}
function texture(bytes:Uint8Array,colorSpace:THREE.ColorSpace){
 const t=new THREE.DataTexture(bytes,SIZE,SIZE);t.colorSpace=colorSpace;
 t.wrapS=t.wrapT=THREE.RepeatWrapping;t.magFilter=THREE.LinearFilter;
 t.minFilter=THREE.LinearMipmapLinearFilter;t.generateMipmaps=true;t.anisotropy=2;t.needsUpdate=true;return t;
}
export function materialDetailMaps(pattern:DetailPattern){const p=detailPixels(pattern);return {map:texture(p.albedo,THREE.SRGBColorSpace),bumpMap:texture(p.relief,THREE.NoColorSpace)};}
export function createMaterialDetailLibrary(){
 const cache=new Map<DetailPattern,ReturnType<typeof materialDetailMaps>&{normalMap?:THREE.Texture;roughnessMap?:THREE.Texture}>();
 function get(pattern:DetailPattern){
  let pair=cache.get(pattern);if(!pair){pair=materialDetailMaps(pattern);if(pattern==="plaster"){pair.normalMap=photoTexture("plaster-normal.jpg")??undefined;pair.roughnessMap=photoTexture("plaster-rough.jpg")??undefined;}cache.set(pattern,pair);}return pair;
 }
 return {get,dispose(){for(const t of cache.values()){t.map.dispose();t.bumpMap.dispose();t.normalMap?.dispose();t.roughnessMap?.dispose();}cache.clear();}};
}
export type MaterialDetailLibrary=ReturnType<typeof createMaterialDetailLibrary>;
export function physicalUV(geometry:THREE.BufferGeometry,repeatX:number,repeatY:number,tangent?:readonly [number,number]){
 const p=geometry.getAttribute("position"),uv=new Float32Array(p.count*2);
 for(let i=0;i<p.count;i++){uv[i*2]=(tangent?p.getX(i)*tangent[0]+p.getZ(i)*tangent[1]:p.getX(i))/repeatX;uv[i*2+1]=(tangent?p.getY(i):p.getZ(i))/repeatY;}
 geometry.setAttribute("uv",new THREE.BufferAttribute(uv,2));
}
