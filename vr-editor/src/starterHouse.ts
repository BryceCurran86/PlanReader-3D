import type {SceneManifest} from "./types.ts";
import type {BuildState,PlacedWall,PlanPoint} from "./buildPlacement.ts";
import type {WallAdditionOpening} from "./wallAdditionProtocol.ts";
import {scopeKey} from "./reviewDraft.ts";
import {defaultWallAssembly,profileDetails} from "./wallProfiles.ts";
import {connectedDraftShell} from "./connectedDraftShell.ts";
import type {ShellSettings} from "./connectedDraftShell.ts";

export const STARTER_LEVEL="ground";
export const STARTER_SHELL:ShellSettings={roof:"gable",pitchDeg:22.5,slabMm:100};

/** A new local design, NOT an imported/source-verified plan. The level marker
 * provides a level only; all physical geometry is editable draft geometry. */
export function starterManifest():SceneManifest{
 return {schemaVersion:"1.0.0",scope:{workspaceId:"starter-house-local",projectId:"Starter house",
 documentId:"local-design",revisionId:"starter-r1",snapshotId:"draft-only",
 sourceSha256:"0".repeat(64),modelRevision:0},coordinateSystem:{unit:"metres",sourceToModelTransform:null,renderOrigin:[0,0,0]},
 readOnly:true,commercialQuantityPublicationAllowed:false,objects:[{objectId:"starter-level",canonicalObjectId:null,
 objectType:"design-level",levelId:STARTER_LEVEL,objectRevision:"local-draft",authority:"unverified",
 renderState:"review",geometry:null,dimensions:{},source:{sourceFileId:null,page:null,sheet:null,sourceRegion:null,
 originalGeometryRef:null,currentGeometryRef:null},quantityLinks:[],unresolvedIssues:["local_design_only"],canEdit:false}]};
}
export function starterBuild(scene:SceneManifest):BuildState{
 const key=scopeKey(scene);
 const door=(id:string,offsetM:number,widthM=.82):WallAdditionOpening=>({openingId:id,offsetM,widthM,heightM:2.04,sillHeightM:0,openingKind:"door"});
 const window=(id:string,offsetM:number,widthM=1.5):WallAdditionOpening=>({openingId:id,offsetM,widthM,heightM:1.2,sillHeightM:.9,openingKind:"window"});
 const wall=(id:string,start:PlanPoint,end:PlanPoint,external:boolean,openings:WallAdditionOpening[]=[]):PlacedWall=>({
 proposalId:id,scopeKey:key,levelId:STARTER_LEVEL,start,end,heightM:2.4,openings,
 assembly:{...defaultWallAssembly(external?"external-timber":"internal-timber"),exteriorSide:"right"}});
 const walls=[wall("front",[0,0],[10,0],true,[window("front-window",.7),door("entry",4.5,.92),window("front-bedroom-window",7.7)]),
 wall("right",[10,0],[10,8],true,[window("right-bedroom-window",1.2),window("right-bath-window",5.4,.9)]),
 wall("back",[10,8],[0,8],true,[window("back-bedroom-window",1.1),door("back-door",6,.92)]),
 wall("left",[0,8],[0,0],true,[window("living-window",2.2,1.8)]),
 wall("room-divider",[6,0],[6,8],false,[door("bedroom-one-door",1.5),door("bedroom-two-door",5.2)]),
 wall("bedroom-divider",[6,4],[10,4],false,[door("bath-access",1.4)]),
 wall("bath-divider",[8,4],[8,8],false,[door("bath-door",1.3)])];
 const ceiling=(id:string,start:PlanPoint,end:PlanPoint)=>({proposalId:id,scopeKey:key,levelId:STARTER_LEVEL,start,end,heightM:2.4});
 return {tool:null,start:null,walls,ceilings:[ceiling("living-ceiling",[0,0],[6,8]),ceiling("bedroom-one-ceiling",[6,0],[10,4]),ceiling("bedroom-two-ceiling",[6,4],[8,8]),ceiling("bath-ceiling",[8,4],[10,8])],history:[]};
}
export function starterBounds(walls:readonly PlacedWall[]){
 const external=walls.filter(w=>profileDetails(w.assembly).role==="external");
 const points=external.flatMap(w=>[w.start,w.end]);
 if(!points.length)return null;
 return {minX:Math.min(...points.map(p=>p[0])),maxX:Math.max(...points.map(p=>p[0])),minZ:Math.min(...points.map(p=>p[1])),maxZ:Math.max(...points.map(p=>p[1]))};
}
export function starterShell(walls:readonly PlacedWall[],settings:ShellSettings){
 const shell=connectedDraftShell(walls.filter(w=>profileDetails(w.assembly).role==="external"),settings);
 // Editable room ceilings are already present; never duplicate them.
 return shell?{...shell,surfaces:shell.surfaces.filter(s=>s.kind!=="ceiling")}:null;
}
