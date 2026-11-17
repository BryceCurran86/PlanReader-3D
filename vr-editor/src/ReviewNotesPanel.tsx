import { useRef, useState } from "react";
import type { SceneManifest } from "./types";
import {
  activeReviewNotes, addReviewNote, deleteReviewNote, exportReviewNotes,
  importReviewNotes, reviewNotesSummary, setNoteStatus,
} from "./reviewNotes";
import type { NotePriority, ReviewNotesState } from "./reviewNotes";

type Props={
  scene:SceneManifest;
  selectedId:string|null;
  state:ReviewNotesState;
  onChange:(state:ReviewNotesState)=>void;
  onSelect:(id:string)=>void;
};
export function ReviewNotesPanel({scene,selectedId,state,onChange,onSelect}:Props){
  const [message,setMessage]=useState("");
  const [priority,setPriority]=useState<NotePriority>("normal");
  const [feedback,setFeedback]=useState<string|null>(null);
  const input=useRef<HTMLInputElement>(null);
  const notes=activeReviewNotes(state,scene);
  const summary=reviewNotesSummary(state,scene);
  const selected=scene.objects.some(o=>o.objectId===selectedId);

  function add(){
    if(!selectedId||!selected)return;
    const next=addReviewNote(state,scene,selectedId,message,priority,()=>crypto.randomUUID());
    if(next===state){setFeedback("Select a current source object and provide at least 8 characters (max 1,200).");return;}
    onChange(next);setMessage("");setFeedback("Local review finding added; not a saved source correction.");
  }
  function exportFile(){
    try{
      const payload=exportReviewNotes(state,scene);
      const blob=new Blob([payload],{type:"application/json"});
      const url=URL.createObjectURL(blob);
      const link=document.createElement("a");link.href=url;
      link.download="planreader-local-source-review-notes.json";
      link.click();URL.revokeObjectURL(url);
      setFeedback("Review-only handoff exported. No measurement or approval.");
    }catch(e){setFeedback(e instanceof Error?e.message:"Export failed");}
  }
  async function importFile(file:File|undefined){
    if(!file)return;
    try{
      if(file.size>256*1024)throw Error("Review file exceeds 256 KB");
      onChange(importReviewNotes(await file.text(),scene));
      setFeedback("Notes restored for exact source snapshot; no corrections applied.");
    }catch(e){setFeedback(e instanceof Error?e.message:"Import failed");}
  }
  return <div className="preview-section" aria-label="Source review findings">
    <span className="eyebrow">SOURCE REVIEW FINDINGS · LOCAL ONLY</span>
    <p className="muted">Pin drawing questions to canonical scene object identity and exact source revision. Reviewing a note does not authenticate construction evidence.</p>
    <p className="muted">Total {summary.total} · open {summary.open} · reviewed {summary.reviewed} · high-priority open {summary.high}</p>
    <label htmlFor="review-note-priority">Finding priority</label>
    <select id="review-note-priority" value={priority}
      onChange={e=>setPriority(e.target.value as NotePriority)}>
      <option value="low">Low</option><option value="normal">Normal</option>
      <option value="high">High</option>
    </select>
    <label htmlFor="review-note-message">Source question / evidence to check</label>
    <textarea id="review-note-message" rows={3} value={message} maxLength={1200}
      placeholder="Which source drawing detail remains unresolved?"
      onChange={e=>setMessage(e.target.value)} />
    <button type="button" disabled={!selected} onClick={add}>Pin to selected source object</button>
    <div className="review-note-list">
      {notes.slice(0,250).map(note=><div className="review-note" key={note.id}>
        <strong>{note.targetObjectId} · {note.priority} · {note.status}</strong>
        <p>{note.message}</p>
        <div className="review-control-grid">
          <button type="button" onClick={()=>onSelect(note.targetObjectId)}>Find in model</button>
          <button type="button" onClick={()=>onChange(setNoteStatus(state,scene,note.id,
            note.status==="open"?"reviewed":"open"))}>
            {note.status==="open"?"Mark reviewed":"Reopen"}
          </button>
          <button type="button" onClick={()=>onChange(deleteReviewNote(state,scene,note.id))}>
            Delete local note
          </button>
        </div>
      </div>)}
    </div>
    <div className="review-control-grid">
      <button type="button" onClick={exportFile}>Export review handoff</button>
      <button type="button" onClick={()=>input.current?.click()}>Import review handoff</button>
    </div>
    <input type="file" ref={input} accept=".json,application/json"
      aria-label="Import source-bound review handoff" style={{display:"none"}}
      onChange={e=>{void importFile(e.target.files?.[0]);e.currentTarget.value="";}}/>
    {feedback&&<p className="muted" role="status">{feedback}</p>}
  </div>;
}
