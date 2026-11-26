import * as THREE from "three";
export type ArchitecturalMap="wood-colour.jpg"|"wood-normal.jpg"|"wood-rough.jpg"|"plaster-normal.jpg"|"plaster-rough.jpg"|"grass-colour.jpg";
export const architecturalAssetUrl=(name:ArchitecturalMap|"outdoor.hdr")=>new URL("architectural-assets/"+name,document.baseURI).href;
const images=new Map<string,Promise<THREE.Source>>();
function sourceFor(name:ArchitecturalMap){
 let pending=images.get(name);
 if(!pending){
  pending=new Promise<THREE.Source>((resolve,reject)=>{
   const image=new Image();
   image.onload=()=>{
    if(name==="wood-colour.jpg"){
     // Keep catalogue paint/stain swatches authoritative: preserve photographed grain,
     // remove baked hue and normalize the diffuse map before tinting.
     const canvas=document.createElement("canvas");canvas.width=image.width;canvas.height=image.height;
     const ctx=canvas.getContext("2d");
     if(ctx){ctx.drawImage(image,0,0);const p=ctx.getImageData(0,0,canvas.width,canvas.height);
      let mean=0;for(let i=0;i<p.data.length;i+=4)mean+=.2126*p.data[i]+.7152*p.data[i+1]+.0722*p.data[i+2];
      mean=Math.max(1,mean/(p.data.length/4));
      for(let i=0;i<p.data.length;i+=4){const v=.2126*p.data[i]+.7152*p.data[i+1]+.0722*p.data[i+2];const shade=Math.max(0,Math.min(255,220+(v-mean)*.85));p.data[i]=p.data[i+1]=p.data[i+2]=shade;}
      ctx.putImageData(p,0,0);resolve(new THREE.Source(canvas));return;}
    }
    resolve(new THREE.Source(image));
   };
   image.onerror=()=>reject(Error("Missing local photographic asset: "+name));
   image.src=architecturalAssetUrl(name);
  });
  images.set(name,pending);
 }
 return pending;
}
/** Node geometry tests retain deterministic procedural material maps. In the browser
 * every photographic asset is served from the packaged local build, not a CDN. */
export function photoTexture(name:ArchitecturalMap):THREE.Texture|null{
 if(typeof Image==="undefined"||typeof document==="undefined")return null;
 const canvas=document.createElement("canvas");canvas.width=canvas.height=1;
 const ctx=canvas.getContext("2d");if(!ctx)return null;
 const normal=name.includes("normal"),colour=name.includes("colour");
 ctx.fillStyle=normal?"#8080ff":name==="grass-colour.jpg"?"#637d45":colour?"#eeeeee":"#ffffff";ctx.fillRect(0,0,1,1);
 const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=colour?THREE.SRGBColorSpace:THREE.NoColorSpace;
 texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.anisotropy=4;texture.magFilter=THREE.LinearFilter;texture.minFilter=THREE.LinearMipmapLinearFilter;
 let disposed=false;texture.addEventListener("dispose",()=>{disposed=true;});
 void sourceFor(name).then(source=>{if(!disposed){texture.source=source;texture.needsUpdate=true;}}).catch(error=>console.error(error));
 return texture;
}
