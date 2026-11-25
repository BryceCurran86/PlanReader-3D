import {ITEM_CATALOGUE} from "./itemCatalogue.ts";
import {emptyItemDraft,placeItem,localFloorHostId,ceilingDraftHostId,makeItemHostId,worktopId,currentItemPlacements} from "./itemPlacement.ts";
import type {ItemHit} from "./itemPlacement.ts";
import type {SceneManifest} from "./types.ts";
import {starterBuild} from "./starterHouse.ts";
import {scopeKey} from "./reviewDraft.ts";
/** Initial editable design choices for the local starter, not a source-plan
 * inference or hidden pricing allowance. All entries use the public catalogue. */
export function starterFurnishings(scene:SceneManifest){
 const key=scopeKey(scene),build=starterBuild(scene);let draft=emptyItemDraft(key);
 const put=(id:string,prefix:string,hit:ItemHit,turn=0)=>{
  const item=ITEM_CATALOGUE.find(i=>i.label===prefix)??ITEM_CATALOGUE.find(i=>i.label.startsWith(prefix));
  if(item)draft=placeItem(draft,key,id,item.id,hit,turn);
 };
 const floor=(x:number,z:number):ItemHit=>({target:"floor",hostId:localFloorHostId("ground"),point:[x,.002,z],normal:[0,1,0],side:1});
 const worktop=(id:string,x:number,y:number,z:number):ItemHit=>({target:"worktop",hostId:worktopId(id),point:[x,y,z],normal:[0,1,0],side:1});
 put("oak-floor","Engineered timber · Natural Oak",floor(3,3));
 for(let i=0;i<4;i++)put("kitchen-base-"+i,"Base cabinet 600 mm · Polar white",floor(1+i*.61,7.55),2);
 put("kitchen-island","Kitchen island 1600 mm · Pale oak",floor(2.5,5.85));
 put("kitchen-sink","Single bowl kitchen sink · White",worktop("kitchen-base-1",1.61,.902,7.55));
 put("kitchen-mixer","Gooseneck kitchen mixer · Brushed nickel",worktop("kitchen-base-1",1.61,.902,7.8),2);
 put("bath-vanity","Vanity 900 mm · Polar white",floor(9.35,4.45));
 put("bath-basin","Round countertop basin · White",worktop("bath-vanity",9.35,.842,4.45));
 put("bath-mixer","Basin mixer · Chrome",worktop("bath-vanity",9.35,.842,4.27));
 put("bath-toilet","Back-to-wall toilet · White",floor(9.5,6.9),2);
 put("bath-tub","Freestanding bath 1500 mm · White",floor(8.85,7.4));
 for(const c of build.ceilings){
  for(const [x,z] of (c.proposalId==="living-ceiling"?[[.25,.25],[.75,.25],[.25,.75],[.75,.75]]:[[.5,.5]])){
   const p:ItemHit={target:"ceiling",hostId:ceilingDraftHostId(c.proposalId),point:[c.start[0]+(c.end[0]-c.start[0])*x,c.heightM,c.start[1]+(c.end[1]-c.start[1])*z],normal:[0,-1,0],side:1,anchor:{kind:"ceiling",xFraction:x,zFraction:z}};
   put(c.proposalId+"-"+x+"-"+z,"Recessed downlight 90 mm",p);
  }
 }
 const wall=(id:string,offset:number,y:number,side:1|-1):ItemHit=>{
  const w=build.walls.find(w=>w.proposalId===id)!;const l=Math.hypot(w.end[0]-w.start[0],w.end[1]-w.start[1]),dx=(w.end[0]-w.start[0])/l,dz=(w.end[1]-w.start[1])/l;
  return {target:"wall",hostId:makeItemHostId("draft-wall",id),point:[w.start[0]+dx*offset,y,w.start[1]+dz*offset],normal:[dz*side,0,-dx*side],side,anchor:{kind:"wall",offsetM:offset}};
 };
 put("living-switch","Single light switch",wall("front",5.65,1.1,-1));
 put("living-socket","Double power point",wall("left",2,.3,-1));
 put("kitchen-socket","Double power point",wall("back",7.9,1.12,-1));
 // Drop any incompatible seed rather than invent a host. The starter has no
 // change history until the owner actually edits it.
 return {...draft,items:currentItemPlacements(draft.items,scene,build.walls,false,build.ceilings),history:[],future:[]};
}
