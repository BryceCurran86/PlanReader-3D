import * as THREE from "three";
import type {WallProfileId} from "./wallProfiles.ts";
type Pattern="brick"|"block"|"cladding"|"concrete";
export function exteriorPattern(profile:WallProfileId):Pattern|null{
 if(profile.startsWith("brick-veneer")||profile==="double-brick")return "brick";
 if(profile==="blockwork")return "block";
 if(profile.startsWith("external-"))return "cladding";
 if(profile==="concrete")return "concrete";
 return null;
}
export function patternRepeat(pattern:Pattern):[number,number]{
 return pattern==="brick"?[.46,.152]:pattern==="block"?[.8,.4]:pattern==="cladding"?[.5,.18]:[.5,.5];
}
/** Deterministic, low-resolution neutral detail. No external image downloads. */
export function patternPixels(pattern:Pattern,size=128){
 const pixels=new Uint8Array(size*size*4);
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){
  const u=x/size,v=y/size,row=Math.floor(v*2);
  const noise=((Math.imul(x+1,73856093)^Math.imul(y+1,19349663))>>>0)%19;
  let shade=230+noise;
  if(pattern==="brick"||pattern==="block"){
   const shifted=(u+(row%2)*.25)%1;
   const mortar=v%0.5<.055||shifted%0.5<.018;
   shade=mortar?160:215+noise+(Math.floor(shifted*2)===row?8:0);
  }else if(pattern==="cladding"){
   shade=v<.025?120:v<.08?185:225+noise-Math.round(v*20);
  }else shade=220+noise;
  const i=(y*size+x)*4;
  pixels[i]=pixels[i+1]=pixels[i+2]=shade;pixels[i+3]=255;
 }
 // A reserved neutral texel for faces that must remain untextured.
 pixels[0]=pixels[1]=pixels[2]=255;
 return pixels;
}
export function createWallTextureLibrary(){
 const cache=new Map<Pattern,THREE.DataTexture>();
 return {
  get(profile:WallProfileId){
   const pattern=exteriorPattern(profile);if(!pattern)return null;
   let texture=cache.get(pattern);
   if(!texture){
    texture=new THREE.DataTexture(patternPixels(pattern),128,128,THREE.RGBAFormat);
    texture.colorSpace=THREE.SRGBColorSpace;
    texture.wrapS=texture.wrapT=THREE.RepeatWrapping;
    texture.magFilter=THREE.NearestFilter;
    texture.minFilter=THREE.NearestMipmapLinearFilter;
    texture.generateMipmaps=true;texture.needsUpdate=true;cache.set(pattern,texture);
   }
   return {texture,repeat:patternRepeat(pattern)};
  },
  dispose(){for(const texture of cache.values())texture.dispose();cache.clear();}
 };
}
export type WallTextureLibrary=ReturnType<typeof createWallTextureLibrary>;
