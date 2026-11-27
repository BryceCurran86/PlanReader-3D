import type {BuildState} from "./buildPlacement.ts";
import type {ItemDraft} from "./itemPlacement.ts";
import type {SceneManifest} from "./types.ts";
import type {FootprintProjection} from "./footprintResize.ts";
import {previewFootprint,projectWall,projectCeiling,projectPlacement,wallStretchRatio} from "./footprintResize.ts";
import {currentItemPlacements} from "./itemPlacement.ts";
import {scopeKey} from "./reviewDraft.ts";
/** Materialize a validated local-only resize as editable geometry. No source rows
 * are modified. Keep actual window/door dimensions and worktop-local anchors. */
export function commitLocalFootprint(scene:SceneManifest,build:BuildState,items:ItemDraft,projection:FootprintProjection){
 if(scene.scope.workspaceId!=="starter-house-local"||items.sourceKey!==scopeKey(scene))return null;
 if([...build.walls,...build.ceilings].some(w=>w.scopeKey!==items.sourceKey))return null;
 const check=previewFootprint(scene,projection.original,projection.draft,build.walls,build.ceilings);
 if(!check.projection||check.error)return null;
 const view=check.projection;
 const walls=build.walls.map(w=>projectWall(w,view)),ceilings=build.ceilings.map(c=>projectCeiling(c,view));
 const byHost=new Map(build.walls.map(w=>["draft-wall:"+w.proposalId,w]));
 const projected=items.items.map(p=>{
  const next=projectPlacement(p,view),host=byHost.get(p.hostId);
  if(host&&next.anchor?.kind==="wall")return {...next,anchor:{...next.anchor,offsetM:next.anchor.offsetM*wallStretchRatio(host,view)}};
  return next;
 });
 const old=currentItemPlacements(items.items,scene,build.walls,false,build.ceilings);
 const live=currentItemPlacements(projected,scene,walls,false,ceilings);
 const ids=new Set(live.map(p=>p.id));if(old.some(p=>!ids.has(p.id)))return null;
 // Coordinate-changing operations invalidate previous independent item snapshots;
 // the caller records a paired build/item undo transaction.
 const nextBuild:BuildState={...build,tool:null,start:null,walls,ceilings,history:[...build.history,{walls:build.walls,ceilings:build.ceilings}].slice(-50),future:[]};
 return {build:nextBuild,items:{...items,items:projected,history:[],future:[]}};
}
