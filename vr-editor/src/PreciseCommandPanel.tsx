import {useEffect,useRef,useState} from "react";
import type {BuildAction,BuildState} from "./buildPlacement";
import {parsePreciseCommand,previewPreciseCommand} from "./preciseCommands";
type Recognition={lang:string;continuous:boolean;interimResults:boolean;onresult:((e:{results:ArrayLike<ArrayLike<{transcript:string}>>})=>void)|null;onerror:(()=>void)|null;onend:(()=>void)|null;start:()=>void;abort:()=>void};
type SpeechWindow=Window & {SpeechRecognition?:new()=>Recognition;webkitSpeechRecognition?:new()=>Recognition};
export function PreciseCommandPanel({state,level,blocked,onAction}:{state:BuildState;level:string|null;blocked:boolean;onAction:(a:BuildAction)=>void}){
 const [input,setInput]=useState("");const [target,setTarget]=useState("");const [status,setStatus]=useState("");const [listening,setListening]=useState(false);
 const recognition=useRef<Recognition|null>(null);
 useEffect(()=>()=>{recognition.current?.abort();recognition.current=null;},[]);
 const walls=state.walls.filter(w=>w.levelId===level),ceilings=state.ceilings.filter(c=>c.levelId===level);
 const wall=walls.find(w=>"wall:"+w.proposalId===target)??null,ceiling=ceilings.find(c=>"ceiling:"+c.proposalId===target)??null;
 const command=parsePreciseCommand(input),preview=command?previewPreciseCommand(command,wall,ceiling):null;
 const speech=typeof window!=="undefined"?(window as SpeechWindow).SpeechRecognition??(window as SpeechWindow).webkitSpeechRecognition:undefined;
 function listen(){
  if(!speech||blocked||listening)return;
  if(!window.confirm("Use your browser's speech recognition? Audio may be processed by its speech service. Only recognised text will fill the command; no edit is applied automatically."))return;
  try{
   const rec=new speech();recognition.current=rec;rec.lang="en-AU";rec.continuous=false;rec.interimResults=false;
   rec.onresult=e=>{setInput(e.results[0]?.[0]?.transcript??"");setStatus("Check the recognised command and preview before applying.");};
   rec.onerror=()=>{setStatus("Speech unavailable. Type your command instead.");setListening(false);};
   rec.onend=()=>{setListening(false);recognition.current=null;};
   rec.start();setListening(true);
  }catch{setStatus("Speech unavailable. Type your command instead.");setListening(false);}
 }
 return <details className="footprint-tools"><summary>Precise voice or text editing</summary>
 <p>Choose a local draft object. Say or type an exact command, then confirm its preview. Original drawing geometry is never changed. Voice is browser-dependent and may not work in immersive Quest mode.</p>
 <label>Draft object<select value={target} disabled={blocked} onChange={e=>{setTarget(e.currentTarget.value);setStatus("");}}><option value="">Select object</option>
 {walls.map((w,i)=><option key={w.proposalId} value={"wall:"+w.proposalId}>Wall {i+1} · {Math.round(Math.hypot(w.end[0]-w.start[0],w.end[1]-w.start[1])*1000)} mm</option>)}
 {ceilings.map((c,i)=><option key={c.proposalId} value={"ceiling:"+c.proposalId}>Ceiling {i+1} · {Math.round(c.heightM*1000)} mm high</option>)}</select></label>
 <label>Command<input value={input} maxLength={160} disabled={blocked} onChange={e=>{setInput(e.currentTarget.value);setStatus("");}} placeholder="Make this wall 2700 mm high"/></label>
 <button type="button" disabled={!speech||blocked||listening} onClick={listen}>{listening?"Listening…":"Dictate command"}</button>
 {listening&&<button type="button" onClick={()=>recognition.current?.abort()}>Stop listening</button>}
 <p>Examples: set wall length to 4.2 metres; move wall x by 300 mm; make this ceiling 2700 mm high.</p>
 {preview&&command?<p>Preview: {command.relative?"Shift":"Set"} {command.kind} {command.field} {command.relative?"by":"to"} {command.mm} mm. Undo restores the previous draft.</p>:input&&<p>No valid edit: select the correct object and use an explicit metric command that retains its openings.</p>}
 <button type="button" disabled={blocked||!preview||listening} onClick={()=>{if(preview){onAction(preview);setStatus("Draft edit submitted.");setInput("");}}}>Apply preview</button>
 {status&&<p role="status">{status}</p>}
 </details>;
}
