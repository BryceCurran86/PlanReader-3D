import * as THREE from "three";
/** Render-only neutral studio reflection fallback. Small HDR latitude/longitude
 * map with broad softboxes, used until the local photographic sky is ready.
 * No additional scene geometry or synchronously rendered PMREM setup. */
export function neutralStudioTexture(){
 const width=256,height=128,data=new Float32Array(width*height*4);
 const lights=[{az:.8,el:.65,power:3.8},{az:3.6,el:.4,power:2.3},{az:5.1,el:.9,power:1.7}];
 for(let y=0;y<height;y++){
  const elevation=Math.PI*(.5-(y+.5)/height),vertical=Math.sin(elevation),c=Math.cos(elevation);
  for(let x=0;x<width;x++){
   const azimuth=(x+.5)/width*Math.PI*2;
   let value=.13+.30*Math.max(0,vertical)+.12*Math.max(0,1-Math.abs(vertical)*2);
   for(const light of lights){
    const cosine=vertical*Math.sin(light.el)+c*Math.cos(light.el)*Math.cos(azimuth-light.az);
    value+=light.power*Math.pow(Math.max(0,cosine),48);
   }
   const i=(y*width+x)*4;
   data[i]=value*1.01;data[i+1]=value;data[i+2]=value*.98;data[i+3]=1;
  }
 }
 const tex=new THREE.DataTexture(data,width,height,THREE.RGBAFormat,THREE.FloatType);
 tex.mapping=THREE.EquirectangularReflectionMapping;tex.colorSpace=THREE.LinearSRGBColorSpace;
 tex.minFilter=THREE.LinearFilter;tex.magFilter=THREE.LinearFilter;tex.needsUpdate=true;return tex;
}
