import * as THREE from "three";
/** Non-measurable presentation only: never registered as a pick or navigation host. */
export function createOutdoorEnvironment(scene:THREE.Scene){
 const size=256,bytes=new Uint8Array(size*size*4);
 let seed=1709;
 const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){
  const u=x/size*Math.PI*2,v=y/size*Math.PI*2;
  const patch=Math.sin(u*3+Math.cos(v*2))*.45+Math.sin(v*5+Math.sin(u*4))*.25+Math.cos(u*7-v*9)*.12;
  const blade=Math.sin(u*83+Math.sin(v*31)*1.3)*.5+.5,fleck=rand(),i=(y*size+x)*4;
  bytes[i]=Math.round(76+patch*16+blade*13+fleck*11);bytes[i+1]=Math.round(99+patch*19+blade*17+fleck*13);bytes[i+2]=Math.round(52+patch*13+blade*8+fleck*10);bytes[i+3]=255;
 }
 const texture=new THREE.DataTexture(bytes,size,size);
 texture.colorSpace=THREE.SRGBColorSpace;texture.wrapS=texture.wrapT=THREE.RepeatWrapping;
 texture.repeat.set(240,240);texture.anisotropy=4;texture.magFilter=THREE.LinearFilter;texture.minFilter=THREE.LinearMipmapLinearFilter;texture.generateMipmaps=true;texture.needsUpdate=true;
 const grass=new THREE.Mesh(new THREE.PlaneGeometry(240,240),new THREE.MeshStandardMaterial({map:texture,color:0xffffff,roughness:.98,metalness:0}));
 grass.rotation.x=-Math.PI/2;grass.position.y=-.04;grass.receiveShadow=true;grass.name="PresentationGrass";scene.add(grass);
 const sky=new THREE.Mesh(new THREE.SphereGeometry(110,24,12),new THREE.ShaderMaterial({
  side:THREE.BackSide,depthWrite:false,toneMapped:false,
  uniforms:{night:{value:0}},
  vertexShader:"varying vec3 vDirection; void main(){vDirection=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}",
  fragmentShader:"varying vec3 vDirection; uniform float night; void main(){float y=normalize(vDirection).y;float t=smoothstep(-0.06,0.75,y);vec3 day=mix(vec3(.84,.90,.94),vec3(.30,.59,.86),t);vec3 dark=mix(vec3(.12,.18,.24),vec3(.015,.035,.09),t);vec3 d=normalize(vDirection);float haze=smoothstep(.08,.45,y)*(1.0-smoothstep(.52,.9,y));float cloud=smoothstep(.48,.75,sin(d.x*19.0+d.z*8.0)*.30+sin(d.z*23.0-d.x*7.0)*.22+.45)*haze;day=mix(day,vec3(.94,.95,.96),cloud*.55);gl_FragColor=vec4(mix(day,dark,night),1.0);}"
 }));
 sky.name="PresentationSky";sky.renderOrder=-10;sky.frustumCulled=false;scene.add(sky);
 let previous:string|null=null;
 return {update(enabled:boolean,night:boolean,x:number,z:number){
  grass.visible=sky.visible=enabled;
  if(!enabled)return;
  grass.position.x=Math.round(x/20)*20;grass.position.z=Math.round(z/20)*20;
  sky.position.set(x,0,z);
  const key=String(night);
  if(previous!==key){sky.material.uniforms.night.value=night?1:0;grass.material.color.setHex(night?0x64727c:0xffffff);previous=key;}
 },dispose(){scene.remove(grass,sky);grass.geometry.dispose();grass.material.dispose();sky.geometry.dispose();sky.material.dispose();texture.dispose();}};
}
