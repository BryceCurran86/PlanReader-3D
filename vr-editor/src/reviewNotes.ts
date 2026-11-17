/** Local reviewer findings pinned to exact source revision and object.
 * Not a construction change, source authentication or commercial approval.
 */
import type { SceneManifest } from "./types";
import { scopeKey } from "./reviewDraft.ts";

export type NotePriority = "low" | "normal" | "high";
export type NoteStatus = "open" | "reviewed";
export interface ReviewNote {
  id: string;
  targetObjectId: string;
  objectRevision: string;
  priority: NotePriority;
  status: NoteStatus;
  message: string;
}
export interface ReviewNotesState {
  scopeKey: string;
  notes: ReviewNote[];
}
const MAX_NOTES=250, MAX_BYTES=256*1024, MAX_TEXT=1200;
const ID=/^[A-Za-z0-9_.:-]{1,128}$/;
export function freshReviewNotes(scene: SceneManifest): ReviewNotesState {
  return { scopeKey: scopeKey(scene), notes: [] };
}
export function validReviewNote(note: ReviewNote, scene: SceneManifest): boolean {
  const row=scene.objects.find(o=>o.objectId===note.targetObjectId);
  return typeof note.id==="string" && ID.test(note.id) &&
    !!row && row.objectRevision===note.objectRevision &&
    ["low","normal","high"].includes(note.priority) &&
    ["open","reviewed"].includes(note.status) &&
    typeof note.message==="string" &&
    note.message.trim().length>=8 && note.message.length<=MAX_TEXT;
}
export function activeReviewNotes(state: ReviewNotesState, scene: SceneManifest): ReviewNote[] {
  if (state.scopeKey!==scopeKey(scene)) return [];
  return state.notes.filter(note=>validReviewNote(note,scene));
}
export function addReviewNote(
  state: ReviewNotesState, scene: SceneManifest, targetObjectId: string,
  message: string, priority: NotePriority, makeId:()=>string,
): ReviewNotesState {
  if (state.scopeKey!==scopeKey(scene)) return freshReviewNotes(scene);
  if (state.notes.length>=MAX_NOTES) return state;
  const row=scene.objects.find(o=>o.objectId===targetObjectId);
  if (!row) return state;
  const candidate: ReviewNote = {
    id:makeId(), targetObjectId, objectRevision:row.objectRevision,
    status:"open", priority, message:message.trim(),
  };
  if (!validReviewNote(candidate,scene) ||
      state.notes.some(note=>note.id===candidate.id)) return state;
  return {...state,notes:[...state.notes,candidate]};
}
export function setNoteStatus(
  state: ReviewNotesState, scene: SceneManifest, noteId: string, status: NoteStatus,
): ReviewNotesState {
  if (state.scopeKey!==scopeKey(scene) ||
      (status!=="open" && status!=="reviewed")) return freshReviewNotes(scene);
  if (!state.notes.some(n=>n.id===noteId && validReviewNote(n,scene))) return state;
  return {...state,notes:state.notes.map(note=>
    note.id===noteId?{...note,status}:note)};
}
export function deleteReviewNote(state:ReviewNotesState,scene:SceneManifest,id:string):ReviewNotesState {
  if(state.scopeKey!==scopeKey(scene))return freshReviewNotes(scene);
  return {...state,notes:state.notes.filter(note=>note.id!==id)};
}
export function reviewNotesSummary(state:ReviewNotesState,scene:SceneManifest) {
  const notes=activeReviewNotes(state,scene);
  return {total:notes.length,open:notes.filter(n=>n.status==="open").length,
    reviewed:notes.filter(n=>n.status==="reviewed").length,
    high:notes.filter(n=>n.priority==="high"&&n.status==="open").length};
}
export function exportReviewNotes(state:ReviewNotesState,scene:SceneManifest):string {
  if(state.scopeKey!==scopeKey(scene))throw Error("stale_review_scope");
  const payload={
    schemaVersion:"planreader-source-review-notes-1",
    scopeKey:scopeKey(scene), commercialAuthority:false, reviewOnly:true,
    notes:activeReviewNotes(state,scene),
  };
  const json=JSON.stringify(payload,null,2);
  if(new TextEncoder().encode(json).byteLength>MAX_BYTES)
    throw Error("review_handoff_too_large");
  return json;
}
export function importReviewNotes(raw:string,scene:SceneManifest):ReviewNotesState {
  if(new TextEncoder().encode(raw).byteLength>MAX_BYTES)
    throw Error("review_handoff_too_large");
  const o:unknown=JSON.parse(raw);
  if(!o||typeof o!=="object"||Array.isArray(o))throw Error("review_schema_invalid");
  const data=o as Record<string,unknown>;
  if(Object.keys(data).sort().join(",")!=="commercialAuthority,notes,reviewOnly,schemaVersion,scopeKey" ||
    data.schemaVersion!=="planreader-source-review-notes-1" ||
    data.scopeKey!==scopeKey(scene) || data.commercialAuthority!==false ||
    data.reviewOnly!==true || !Array.isArray(data.notes) ||
    data.notes.length>MAX_NOTES)throw Error("review_scope_or_schema_mismatch");
  const seen=new Set<string>(); const notes:ReviewNote[]=[];
  for(const item of data.notes) {
    if(!item||typeof item!=="object"||Array.isArray(item))throw Error("invalid_review_note");
    const rec=item as Record<string,unknown>;
    if(Object.keys(rec).sort().join(",")!=="id,message,objectRevision,priority,status,targetObjectId")
      throw Error("invalid_review_note");
    const note=rec as unknown as ReviewNote;
    if(!validReviewNote(note,scene)||seen.has(note.id))throw Error("invalid_review_note");
    notes.push(note);seen.add(note.id);
  }
  return {scopeKey:scopeKey(scene),notes};
}
