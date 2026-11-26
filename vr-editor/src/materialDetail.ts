import * as THREE from "three";
export type DetailPattern="plaster"|"plank"|"grain"|"tile"|"woven"|"fleck"|"stone"|"roof";
const SIZE=128;
const noise=(x:number,y:number)=>((Math.imul(x+197,374761393)^Math.imul(y+123,668265263))>>>0)%1021/1020;
const clamp=(v:number)=>Math.max(0,Math.min(255,Math.round(v)));
/** Deterministic neutral tintable albedo and relief, bounded 128² per map.
 * Physical dimensions are assigned by the renderer UV, not by evidence. */
export function detailPixels(pattern:DetailPattern,size=SIZE){
 const albedo=new Uint8Array(size*size*4),relief=new Uint8Array(size*size*4);
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){
  const u=x/size,v=y/size,n=noise(x,y),fine=noise(x*3,y*7);
  let shade=239+n*12,height=126+fine*18;
  if(pattern==="plank"||pattern==="grain"){
   const wave=Math.sin(u*75+Math.sin(v*10)*1.7+Math.sin(v*19)*.45);
   const grain=Math.sin(u*290+Math.sin(v*14)*2.2);
   shade=226+wave*12+grain*6+n*8;height=132+wave*12+grain*8;
   if(pattern==="plank"&&(u<.012||v<.004)){shade=100;height=65;}
  }else if(pattern==="tile"){
   const grout=u<.008||v<.008;shade=grout?152:238+n*10;height=grout?65:200;
  }else if(pattern==="woven"){
   shade=217+((x+y)%2)*15+n*12;height=105+(x%2)*42+(y%2)*29;
  }else if(pattern==="fleck"||pattern==="stone"){
   const vein=Math.sin(u*17+Math.sin(v*13)*2.7+v*11);
   shade=pattern==="stone"?234-Math.max(0,vein-.87)*150+n*9:221+n*28;
   height=pattern==="stone"?180:115+fine*50;
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
 const cache=new Map<DetailPattern,{map:THREE.DataTexture;bumpMap:THREE.DataTexture}>();
 function get(pattern:DetailPattern){
  let pair=cache.get(pattern);if(!pair){pair=materialDetailMaps(pattern);cache.set(pattern,pair);}return pair;
 }
 return {get,dispose(){for(const t of cache.values()){t.map.dispose();t.bumpMap.dispose();}cache.clear();}};
}
export type MaterialDetailLibrary=ReturnType<typeof createMaterialDetailLibrary>;
export function physicalUV(geometry:THREE.BufferGeometry,repeatX:number,repeatY:number,tangent?:readonly [number,number]){
 const p=geometry.getAttribute("position"),uv=new Float32Array(p.count*2);
 for(let i=0;i<p.count;i++){uv[i*2]=(tangent?p.getX(i)*tangent[0]+p.getZ(i)*tangent[1]:p.getX(i))/repeatX;uv[i*2+1]=(tangent?p.getY(i):p.getZ(i))/repeatY;}
 geometry.setAttribute("uv",new THREE.BufferAttribute(uv,2));
}
