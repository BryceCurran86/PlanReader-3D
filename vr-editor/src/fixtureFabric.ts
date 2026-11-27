import * as THREE from "three";
const SIZE=64;
let cached:{colour:Uint8Array;relief:Uint8Array}|undefined;
/** Neutral fine weave, tileable, shared CPU pixels with separately owned GPU
 * texture wrappers. No external requests and no new fixture draw calls. */
export function fabricPixels(){
 if(cached)return cached;
 const colour=new Uint8Array(SIZE*SIZE*4),relief=new Uint8Array(colour.length);
 for(let y=0;y<SIZE;y++)for(let x=0;x<SIZE;x++){
  const u=x/8,v=y/8,warp=Math.pow(.5+.5*Math.cos(2*Math.PI*u),2),weft=Math.pow(.5+.5*Math.cos(2*Math.PI*v),2);
  const over=(Math.floor(u)+Math.floor(v))%2===0;
  const thread=over?warp:weft,under=over?weft:warp;
  const shade=Math.round(211+thread*25+under*6),height=Math.round(110+thread*57+under*9),i=(y*SIZE+x)*4;
  colour[i]=colour[i+1]=colour[i+2]=shade;colour[i+3]=255;relief[i]=relief[i+1]=relief[i+2]=height;relief[i+3]=255;
 }
 return cached={colour,relief};
}
function texture(bytes:Uint8Array,srgb:boolean){
 const t=new THREE.DataTexture(bytes,SIZE,SIZE,THREE.RGBAFormat);
 t.colorSpace=srgb?THREE.SRGBColorSpace:THREE.NoColorSpace;t.wrapS=t.wrapT=THREE.RepeatWrapping;
 t.magFilter=THREE.LinearFilter;t.minFilter=THREE.LinearMipmapLinearFilter;t.generateMipmaps=true;t.anisotropy=2;t.needsUpdate=true;
 return t;
}
/** Project fabric UVs in physical units using the dominant local face. Rounded
 * corners use a bounded projection rather than stretching one weave across a
 * whole cushion. Decorative finish only; placement envelope is unchanged. */
export function fabricUV(g:THREE.BufferGeometry,repeatM=.04){
 const p=g.getAttribute("position"),n=g.getAttribute("normal");if(!p||!n||!Number.isFinite(repeatM)||repeatM<=0)return;
 const uv=new Float32Array(p.count*2);
 for(let i=0;i<p.count;i++){
  const x=Math.abs(n.getX(i)),y=Math.abs(n.getY(i)),z=Math.abs(n.getZ(i));
  uv[i*2]=(x>y&&x>z?p.getZ(i):p.getX(i))/repeatM;
  uv[i*2+1]=(y>=x&&y>=z?p.getZ(i):p.getY(i))/repeatM;
 }
 g.setAttribute("uv",new THREE.BufferAttribute(uv,2));
}
export function applyFixtureFabric(group:THREE.Group,materials:readonly THREE.MeshStandardMaterial[]){
 const used=new Set<THREE.MeshStandardMaterial>();
 group.traverse(o=>{if(o instanceof THREE.Mesh&&o.material instanceof THREE.MeshStandardMaterial&&materials.includes(o.material)){fabricUV(o.geometry);used.add(o.material);}});
 if(!used.size)return;
 const p=fabricPixels(),map=texture(p.colour,true),bump=texture(p.relief,false);
 for(const m of used){m.map=map;m.bumpMap=bump;m.bumpScale=.00045;m.roughness=.94;m.metalness=0;m.needsUpdate=true;}
}
