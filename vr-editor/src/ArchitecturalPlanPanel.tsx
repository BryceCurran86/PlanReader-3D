import {useEffect,useMemo,useRef} from "react";
import {architecturalPlan,paintArchitecturalPlan} from "./architecturalPlan";
type Inputs=Parameters<typeof architecturalPlan>;
export function ArchitecturalPlan({scene,build,level,visible,projection,moves,extra}:{scene:Inputs[0];build:Inputs[1];level:Inputs[2];visible:Inputs[3];projection:Inputs[4];moves:Inputs[5];extra:Inputs[6]}){
 const canvas=useRef<HTMLCanvasElement>(null);
 const drawing=useMemo(()=>architecturalPlan(scene,build,level,visible,projection,moves,extra),[scene,build.walls,level,visible,projection,moves,extra]);
 useEffect(()=>{const ctx=canvas.current?.getContext("2d");if(ctx)paintArchitecturalPlan(ctx,drawing,1400,1000);},[drawing]);
 function download(){const node=canvas.current;if(!node)return;node.toBlob(blob=>{if(!blob)return;const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="planreader-plan-preview.png";a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);});}
 return <section aria-label="Architectural plan preview"><p>Orthographic plan preview · model metres · draft dimensions in millimetres. Original source faces are not inferred wall thicknesses. Return to 3D to edit.</p><button type="button" onClick={download}>Save plan preview PNG</button><canvas ref={canvas} width={1400} height={1000} style={{width:"100%",height:"auto",display:"block"}} aria-label="2D architectural plan drawing"/></section>;
}
