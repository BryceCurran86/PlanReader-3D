import { activeStart, BUILD_TOOLS } from "./buildPlacement.ts";
import {wallAngleDegrees} from "./buildPlacement.ts";
import type { BuildAction, BuildState, PlacedWall, WallAxis, WallRotationPivot } from "./buildPlacement.ts";
import { CATALOGUE_GROUPS, ITEM_CATALOGUE, itemCanRotate } from "./itemCatalogue.ts";
import type { CatalogueItem,CatalogueGroup } from "./itemCatalogue.ts";
import {contextGroups,contextChoices,contextTitle,finishGroupLabel,localContextTarget} from "./contextFinishes.ts";
import type {FinishContext} from "./contextFinishes.ts";
import {canEditFloorFixture} from "./itemPlacement.ts";
import type {ItemHit,FixtureEdit,Vector} from "./itemPlacement.ts";
import type {DoorHardwareFinish} from "./wallAdditionProtocol.ts";
import { CONSTRUCTION_STAGES, stageDetails } from "./constructionStages.ts";
import type { ConstructionStage } from "./constructionStages.ts";
import type { ControlMode, HistoryAction } from "./editorControls.ts";
import { budgetMoney,budgetHeadline } from "./vrAssemblyStudy.ts";
import type { ImmersiveBudget } from "./vrAssemblyStudy.ts";
import { WALL_PROFILES, wallAssembly, wallDimensionText } from "./wallProfiles.ts";
import type { WallAssembly, WallProfileId } from "./wallProfiles.ts";
import {CONSTRUCTION_LAYERS} from "./constructionLayers.ts";
import type {ConstructionLayer,LayerOverrides} from "./constructionLayers.ts";
import type {LiningBoard} from "./constructionLiningVisual.ts";

export type ItemAction =
  | { kind: "choose"; itemId: string }
  | { kind:"apply-finish";itemId:string;hit:ItemHit;replaceId?:string }
  | {kind:"edit-fixture";id:string;edit:FixtureEdit;move?:{from:Vector;to:[number,number]}}
  | {kind:"remove-context-item";id:string}
  | { kind: "undo" | "redo" | "done" | "rotate" };
type BrowseAction = { kind: "toggle" } | { kind: "groups" } | { kind: "category" | "page" | "group-page"; step: number }
  | { kind: "choose-group"; index: number };
export type MenuAction =
  | {area:"context-edit";action:"wall"|"opening"|"move"|"stretch"|"slab"|"remove"}
  | {area:"finish";action:"group"|"page"|"apply"|"back"|"close"|"hardware";group?:CatalogueGroup;step?:number;itemId?:string;hardware?:DoorHardwareFinish}
  | { area: "build"; action: BuildAction }
  | { area: "items"; action: ItemAction }
  | { area: "browse"; action: BrowseAction }
  | { area: "view"; stage?: ConstructionStage }
  | { area: "footprint"; reset?: boolean }
  | {area:"footprint-size";axis:"x"|"z";delta:number}
  | {area:"slab";mm?:number}
  | { area: "history"; action: HistoryAction }
  | { area: "level"; id: string }
  | { area: "done" }
  | { area: "quest"; action: "grid" | "axis" | "nudge-size" | "pin" | "recenter" | "help" | "back" |
      "drag-gain" | "compact" | "next-stage" | "next-floor" | "openings" | "next-opening" |
      "teleport" | "save" | "review" | "overview" | "elevated-view" | "walk-speed" | "multi-select" | "magnetic" | "clear-group" | "budget" | "budget-baseline" | "budget-clear" | "budget-page" | "wall-profiles" | "dimensions" | "layers" | "reset-layers" | "more-tools" | "hide-tools" | "ghost" | "lighting-night" | "lighting-on" | "all-dimensions" | "environment" | "home" | "quality" }
  | {area:"layer";layer:ConstructionLayer}
  | {area:"lining";action:"board"|"inspect"}
  | { area:"wall-profile"; profile:WallProfileId }
  | { area: "number"; action: "start" | "digit" | "erase" | "clear" | "apply" | "cancel";
      field?: NumericDraftField; digit?: string }
  | { area: "wall-angle"; action:"step"|"pivot"|"connected"|"panel"; degrees?:number }
  | { area: "opening"; action: "drag" | "shift" | "width" | "height" | "mechanism" | "toggle";
      deltaMm: number }
  | { area: "draft"; action: "move" | "stretch" | "nudge" | "rotate" | "duplicate" | "delete";
      direction?: "left" | "right" | "forward" | "back" };

export type MenuButton = {
  label: string; x: number; y: number; w: number; h: number;
  action: MenuAction; active?: boolean; disabled?: boolean; swatch?: number;
};
export type MenuLayout = { title: string; width: number; height: number;
  note: string; subtitle?: string; buttons: MenuButton[];
  sections?: { label: string; y: number }[]; helpLines?: string[]; radial?:boolean };
export type NumericDraftField = "angle" | "length" | "height" | "x" | "z" |
  "opening-offset" | "opening-width" | "opening-height" | "opening-sill";
export type QuestMenuState = {
  simpleHome?:boolean;outdoor?:boolean;quality?:"performance"|"balanced"|"high";finishContext?:FinishContext|null;finishGroup?:CatalogueGroup|null;finishPage?:number;activeFinishId?:string;hoverContext?:boolean;slabMm?:number;slabTools?:boolean;
  rotationPivot?:WallRotationPivot; connectedRotation?:boolean; angleTools?:boolean; feedback?:string;
  selectedWall: PlacedWall | null; gridM: 0.05 | 0.1 | 0.25;
  axis: WallAxis; nudgeM: 0.05 | 0.1 | 0.25;
  pinned: boolean; help: boolean; deleteArmed: boolean;
  compact?: boolean; openingTools?: boolean; openingIndex?: number;
  canTeleport?:boolean; teleport?:boolean; overview?:boolean;
  elevatedView?:boolean; walkSpeed?:number; dragGain?:number; ghost?:boolean; night?:boolean; previewLights?:boolean;
  multiSelect?:boolean; selectedCount?:number; magnetic?:boolean;
  wallProfilesOpen?:boolean; nextWallAssembly?:WallAssembly; dimensions?:boolean; allDimensions?:boolean;
  layers?:LayerOverrides; layersOpen?:boolean; radial?:boolean;
  liningBoard?:LiningBoard; liningHidden?:boolean;
  budget?:ImmersiveBudget; budgetOpen?:boolean; budgetPage?:number;
  numeric?: {field:NumericDraftField;digits:string}|null;
};
type BrowserState = { open: boolean; category: number; page: number; groups?: boolean; groupPage?: number };
export const EMPTY_ITEM_BROWSER: BrowserState = { open: false, category: 0, page: 0 };
const optionsByGroup = CATALOGUE_GROUPS.map(([key]) => ITEM_CATALOGUE.filter(entry => entry.group === key));
const PER_PAGE = 6;
const WIDTH = 980;
const GROUPS_PER_PAGE = 12;
const lastGroupPage = Math.ceil(CATALOGUE_GROUPS.length / GROUPS_PER_PAGE) - 1;
const maxPage = (category: number) => Math.max(0, Math.ceil(optionsByGroup[category].length / PER_PAGE) - 1);

export function updateItemBrowser(state: BrowserState, action: BrowseAction): BrowserState {
  if (action.kind === "toggle") return { ...state, open: !state.open, groups: false };
  if (action.kind === "groups") return { ...state, open: true, groups: true,
    groupPage: Math.floor(state.category / GROUPS_PER_PAGE) };
  if (action.kind === "choose-group") return { ...state, open: true, groups: false,
    category: action.index, page: 0 };
  if (action.kind === "group-page") return { ...state,
    groupPage: Math.max(0, Math.min(lastGroupPage, (state.groupPage ?? 0) + action.step)) };
  if (action.kind === "category") return { ...state, page: 0,
    category: (state.category + action.step + CATALOGUE_GROUPS.length) % CATALOGUE_GROUPS.length };
  return { ...state, page: Math.max(0, Math.min(maxPage(state.category), state.page + action.step)) };
}

export function buildMenuLayout(
  build: BuildState, levelId: string | null, browser: BrowserState,
  item: CatalogueItem | undefined, itemUndo: boolean, turn: number, hint: string,
  stage: ConstructionStage = "finished", viewsOpen = false,
  footprint = { available: false, enabled: false, changed: false },
  interaction?: { mode: ControlMode; canUndo: boolean; canRedo: boolean; levels?: readonly string[]; level?: string },
  quest?: QuestMenuState,
): MenuLayout {
  const buttons: MenuButton[] = [];
  function add(label: string, x: number, y: number, w: number, h: number, action: MenuAction,
    settings: { active?: boolean; disabled?: boolean; swatch?: number } = {}) {
    buttons.push({ label, x, y, w, h, action, ...settings });
  }
  const browse = (action: BrowseAction): MenuAction => ({ area: "browse", action });
  const items = (action: ItemAction): MenuAction => ({ area: "items", action });
  const questAction = (action: Extract<MenuAction, {area:"quest"}>["action"]): MenuAction =>
    ({ area: "quest", action });
  if(quest?.finishContext){
    const c=quest.finishContext,group=quest.finishGroup;
    const groups=contextGroups(c);
    const page=Math.max(0,quest.finishPage??0);
    const target=localContextTarget(c),localWall=target&&build.walls.find(w=>w.proposalId===target.id&&w.levelId===levelId),localCeiling=target&&build.ceilings.find(w=>w.proposalId===target.id&&w.levelId===levelId);
    const editRows:{label:string;action:MenuAction}[]=[];
    if(target?.kind==="wall"&&localWall)editRows.push({label:"Move / stretch / size",action:{area:"context-edit",action:"wall"}});
    if(target?.kind==="opening"&&localWall?.openings.some(o=>o.openingId===target.openingId))editRows.push({label:"Edit frame / opening",action:{area:"context-edit",action:"opening"}});
    if(target?.kind==="ceiling"&&localCeiling)editRows.push({label:"Move ceiling",action:{area:"context-edit",action:"move"}},{label:"Stretch ceiling",action:{area:"context-edit",action:"stretch"}});
    if(c.hit.hostId?.startsWith("draft-floor:"))editRows.push({label:"Concrete slab",action:{area:"context-edit",action:"slab"}});
    if(c.entry)editRows.push({label:"Remove selection…",action:{area:"context-edit",action:"remove"}});
    function contextRows(y:number){editRows.forEach((e,i)=>add(e.label,24+(i%2)*460,y+Math.floor(i/2)*78,440,68,e.action));return editRows.length?Math.ceil(editRows.length/2)*78:0;}
    if(group){
      const choices=contextChoices(c,group),max=Math.max(0,Math.ceil(choices.length/6)-1),p=Math.min(page,max);
      choices.slice(p*6,p*6+6).forEach((item,i)=>add(item.label,24+(i%2)*460,88+Math.floor(i/2)*84,440,74,{area:"finish",action:"apply",itemId:item.id},{active:(quest.activeFinishId??c.entry?.itemId)===item.id,swatch:item.visual.color}));
      add("Back",24,354,210,68,{area:"finish",action:"back"});
      add("Previous",250,354,210,68,{area:"finish",action:"page",step:-1},{disabled:p===0});
      add("Next",476,354,210,68,{area:"finish",action:"page",step:1},{disabled:p===max});
      add("Close",702,354,210,68,{area:"finish",action:"close"});
      const editing=!!c.entry&&canEditFloorFixture(c.entry);
      if(editing){const actions:[string,FixtureEdit][]=[["Rotate 90°","rotate"],["X −100","left"],["X +100","right"],["Z −100","forward"],["Z +100","back"],["Duplicate","duplicate"]];actions.forEach(([label,edit],i)=>add(label,24+i*150,438,142,64,items({kind:"edit-fixture",id:c.entry!.id,edit})));}
      const height=editing?560:476;const extra=contextRows(height-28);
      return {buttons,title:contextTitle(c)+" · "+finishGroupLabel(group)+" "+(p+1)+"/"+(max+1),width:936,height:height+extra,note:editing?"Change finish or edit this fitting · movement in mm, local design.":"Choose a finish to apply directly to the selected item or face."};
    }
    const max=Math.max(0,Math.ceil(groups.length/8)-1),p=Math.min(page,max);
    groups.slice(p*8,p*8+8).forEach((g,i)=>add(finishGroupLabel(g),24+(i%2)*460,86+Math.floor(i/2)*74,440,64,{area:"finish",action:"group",group:g}));
    if(c.hit.target==="opening"&&c.hit.opening?.door&&c.hit.hostId.startsWith("opening:")&&groups.length<=4){
      const finishes=[["Chrome",0xc4ced4,"chrome"],["Matte black",0x292c2e,"matte-black"],["Brushed brass",0xb99b63,"brushed-brass"],["Brushed nickel",0xaaa9a4,"brushed-nickel"]] as const;
      finishes.forEach(([label,swatch,hardware],index)=>{const i=groups.length+index;add("Handle · "+label,24+(i%2)*460,86+Math.floor(i/2)*74,440,64,{area:"finish",action:"hardware",hardware},{swatch});});
    }
    add("Tools",24,394,210,65,{area:"finish",action:"back"});
    add("Previous",250,394,210,65,{area:"finish",action:"page",step:-1},{disabled:p===0});
    add("Next",476,394,210,65,{area:"finish",action:"page",step:1},{disabled:p===max});
    add("Close",702,394,210,65,{area:"finish",action:"close"});
    const extra=contextRows(484);
    return {buttons,title:contextTitle(c),width:936,height:512+extra,note:quest.hoverContext?"Aim at this toolbox to choose; point back at the object to grab it.":"Choose a category. Existing fixtures retain their position."};
  }
  if(quest?.slabTools){
    const mm=quest.slabMm??0;
    add(mm?"Concrete slab · "+mm+" mm":"Add 100 mm concrete slab",24,88,900,74,{area:"slab",mm:mm||100},{active:!!mm});
    add("−25 mm",24,174,440,74,{area:"slab",mm:Math.max(50,mm-25)},{disabled:mm<=50});add("+25 mm",484,174,440,74,{area:"slab",mm:Math.min(600,mm+25)},{disabled:!mm||mm>=600});
    add("Remove slab",24,260,440,74,{area:"slab",mm:0},{disabled:!mm});add("Back",484,260,440,74,{area:"slab"});
    return {buttons,title:"CONCRETE SLAB",width:936,height:406,note:"Slab follows the closed local perimeter. Nominal thickness only; no engineering specification."};
  }
  if(footprint.enabled&&quest){
    add("Width −500 mm",24,88,440,74,{area:"footprint-size",axis:"x",delta:-.5});add("Width +500 mm",484,88,440,74,{area:"footprint-size",axis:"x",delta:.5});
    add("Depth −500 mm",24,174,440,74,{area:"footprint-size",axis:"z",delta:-.5});add("Depth +500 mm",484,174,440,74,{area:"footprint-size",axis:"z",delta:.5});
    add("Reset preview",24,260,440,74,{area:"footprint",reset:true});add("Apply / done",484,260,440,74,{area:"footprint"});
    return {buttons,title:"RESIZE BUILDING FOOTPRINT",width:936,height:406,note:"Drag green corners / gold edges or use 500 mm steps. Apply before further wall edits."};
  }
  if(quest?.simpleHome&&!quest.layersOpen&&!quest.wallProfilesOpen&&!quest.budgetOpen&&!quest.help&&!quest.numeric&&!quest.angleTools&&!quest.openingTools&&!quest.multiSelect&&!viewsOpen&&!browser.open&&!footprint.enabled){
    const selected=quest.selectedWall&&!build.tool&&!item;
    const entries:{label:string;action:MenuAction;disabled?:boolean}[]=selected?[
      {label:"Move wall",action:{area:"draft",action:"move"}},
      {label:"Stretch wall",action:{area:"draft",action:"stretch"}},
      {label:"Wall assembly",action:questAction("wall-profiles")},
      {label:"Doors / windows",action:questAction("openings"),disabled:!quest.selectedWall?.openings.length},
      {label:"Angle",action:{area:"wall-angle",action:"panel"}},
      {label:"More tools",action:questAction("more-tools")},
      {label:"Drag speed: "+(quest.dragGain??1)+"×",action:questAction("drag-gain")},
    ]:[
      {label:"Build / edit",action:questAction("more-tools")},
      {label:"Materials & fixtures",action:browse({kind:"groups"})},
      {label:"Plan / walkthrough",action:questAction("elevated-view")},
      {label:quest.outdoor?"Grass & sky: ON":"Grass & sky: OFF",action:questAction("environment")},
      {label:"Construction stages",action:{area:"view"}},
      {label:"Budget",action:questAction("budget")},
      {label:"Resize footprint",action:{area:"footprint"},disabled:!footprint.available},
      {label:quest.slabMm?"Concrete slab · "+quest.slabMm+" mm":"Concrete slabs",action:{area:"slab"}},
      {label:"Drag speed: "+(quest.dragGain??1)+"×",action:questAction("drag-gain")},
    ];
    entries.forEach((e,i)=>add(e.label,24+(i%2)*460,88+Math.floor(i/2)*86,440,76,e.action,{disabled:e.disabled}));
    const footer=98+Math.ceil(entries.length/2)*86;
    add("Undo",24,footer,210,70,{area:"history",action:"undo"},{disabled:!interaction?.canUndo});
    add("Redo",250,footer,210,70,{area:"history",action:"redo"},{disabled:!interaction?.canRedo});
    add(selected?"Home":quest.quality==="performance"?"Performance":quest.quality==="high"?"Ultra":"Realistic",476,footer,210,70,questAction(selected?"home":"quality"));
    add("Close",702,footer,210,70,questAction("hide-tools"));
    return {buttons,title:selected?"WALL WORKBENCH":"PLANREADER · TOOL TRAY",width:936,height:footer+122,note:"Left grip: tools · Right grip on an object: finishes · Trigger: choose"};
  }
  if(quest?.layersOpen){
    CONSTRUCTION_LAYERS.forEach(([id,label],i)=>add(label+" · "+(quest.layers?.[id]??"auto").toUpperCase(),20+(i%2)*475,85+Math.floor(i/2)*67,455,58,{area:"layer",layer:id},{active:quest.layers?.[id]==="show"}));
    const bottom=85+Math.ceil(CONSTRUCTION_LAYERS.length/2)*67+8;
    add("Reset to stage defaults",20,bottom,455,60,questAction("reset-layers"));
    add("Back",495,bottom,455,60,questAction("layers"));
    return {buttons,title:"CONSTRUCTION LAYERS",width:WIDTH,height:bottom+120,note:"Select a layer to cycle Auto → Show → Hide. Overrides do not change quantities."};
  }
  if(quest?.radial&&!quest.layersOpen&&!quest.wallProfilesOpen&&!quest.budgetOpen&&!quest.help&&!quest.numeric&&!quest.angleTools&&!quest.openingTools&&!quest.multiSelect&&!viewsOpen&&!browser.open&&!footprint.enabled){
    const canDraw=!!levelId&&!footprint.changed;
    const hasWall=build.walls.some(w=>w.levelId===levelId);
    const selected=quest.selectedWall&&!build.tool&&!item&&!footprint.changed?quest.selectedWall:null;
    const radialTools:{label:string;action:MenuAction;disabled?:boolean}[]=selected?[
      {label:"Angle",action:{area:"wall-angle",action:"panel"}},
      {label:"Move",action:{area:"draft",action:"move"}},
      {label:"Stretch",action:{area:"draft",action:"stretch"}},
      {label:"Openings",action:questAction("openings"),disabled:!selected.openings.length},
      {label:"Assembly",action:questAction("wall-profiles")},
      {label:"Undo",action:{area:"history",action:"undo"},disabled:!interaction?.canUndo},
      {label:"More edits",action:questAction("more-tools")},
      {label:"New tools",action:questAction("back")},
    ]:[
      {label:"Wall",action:{area:"build",action:{kind:"tool",tool:"wall"}},disabled:!canDraw},
      {label:"Door",action:{area:"build",action:{kind:"tool",tool:"door"}},disabled:!canDraw||!hasWall},
      {label:"Window",action:{area:"build",action:{kind:"tool",tool:"window"}},disabled:!canDraw||!hasWall},
      {label:"Ceiling",action:{area:"build",action:{kind:"tool",tool:"ceiling"}},disabled:!canDraw},
      {label:"Items",action:browse({kind:"groups"})},
      {label:"3D view",action:questAction("elevated-view")},
      {label:"Layers",action:questAction("layers")},
      {label:"More tools",action:questAction("more-tools")},
    ];
    radialTools.forEach((entry,i)=>{
      const angle=i*Math.PI/4-Math.PI/2;
      add(entry.label,330+Math.cos(angle)*218-76,330+Math.sin(angle)*218-34,152,68,entry.action,{disabled:entry.disabled});
    });
    add("Close",254,295,152,70,questAction("hide-tools"));
    return {buttons,title:selected?"EDIT SELECTED WALL":"QUICK TOOLS",width:660,height:660,note:"Aim or right stick · trigger",radial:true};
  }
  if(quest?.wallProfilesOpen){
    const a=wallAssembly(quest.selectedWall?.assembly??quest.nextWallAssembly);
    WALL_PROFILES.forEach((profile,i)=>add(profile.label+" · "+profile.thicknessMm+" mm",20+(i%2)*475,95+Math.floor(i/2)*76,455,66,{area:"wall-profile",profile:profile.id},{active:a.profile===profile.id}));
    add("Back",495,399,455,66,questAction("wall-profiles"));
    return {buttons,title:quest.selectedWall?"CHANGE WALL ASSEMBLY":"WALL CONSTRUCTION",width:WIDTH,height:530,note:"Nominal design profiles only · choose actual construction; imported wall types remain unverified."};
  }
  if(quest?.budgetOpen&&quest.budget){
    const b=quest.budget;
    const pages=Math.max(1,Math.ceil(b.trades.length/4)),page=Math.min(pages-1,Math.max(0,quest.budgetPage??0));
    const lines=[budgetHeadline(b),"Local draft only · excludes original source and unpriced work",
      b.walls+" walls · "+b.ceilings+" ceilings",
      "Materials: "+budgetMoney(b.material)+"   Labour: "+budgetMoney(b.labour),
      "Change vs baseline: "+(b.delta===null?"Not available":budgetMoney(b.delta)),
      ...b.trades.slice(page*4,page*4+4).map(t=>t.trade+": "+budgetMoney(t.cents)+(t.partial?" (partial)":""))];
    add("Back to tools",20,520,225,62,questAction("budget"));
    add("Capture baseline",256,520,225,62,questAction("budget-baseline"),{disabled:b.status==="disabled"||b.status==="invalid"});
    add("Clear baseline",492,520,225,62,questAction("budget-clear"),{disabled:!b.hasBaseline});
    add("Next trades "+(page+1)+"/"+pages,728,520,225,62,questAction("budget-page"),{disabled:pages===1});
    return {buttons,title:"LIVE CONSTRUCTION BUDGET",width:WIDTH,height:650,helpLines:lines,note:"Rates and assumptions are entered in desktop review. Not a customer quote."};
  }
  if (quest?.numeric && quest.selectedWall) {
    const { field, digits } = quest.numeric;
    const number = (action: Extract<MenuAction,{area:"number"}>["action"],digit?:string): MenuAction =>
      ({area:"number",action,digit});
    const keys = ["7","8","9","4","5","6","1","2","3","-","0","⌫"];
    for (const [i,key] of keys.entries()) add(key,
      20+(i%3)*315,118+Math.floor(i/3)*67,300,58,
      key==="⌫"?number("erase"):number("digit",key),
      {disabled:key==="-"&&!["x","z"].includes(field)});
    add(field==="angle"?"Apply angle °":"Apply exact mm",20,405,300,65,number("apply"),{disabled:!digits||digits==="-"});
    add("Clear",338,405,300,65,number("clear"));
    add("Cancel",655,405,300,65,number("cancel"));
    return {buttons,title:"EXACT "+field.toUpperCase()+" · "+(digits||"—")+(field==="angle"?"°":" mm"),
      width:WIDTH,height:530,note:field==="angle"?"Enter 0–360 degrees. Fixed pivot: "+(quest.rotationPivot??"start")+".":"Enter millimetres. Invalid sizes or openings cannot be applied.",
      sections:[{label:"DRAFT ONLY · TRIGGER A NUMBER",y:99}]};
  }
  if (quest?.help) {
    add("Back to tools", 20, 455, 260, 74, questAction("help"));
    return { buttons, title: "Quest 3 · quick controls", width: WIDTH, height: 570,
      note: "Everything here is local draft review until an authenticated save.",
      helpLines: [
        "Left grip: tool tray. Right grip on object: finishes.",
        "Left stick: walk/strafe. Right stick: snap turn.",
        "Trigger: point, select, confirm or place.",
        "Choose Wall, pick start and end; a corner glows when snapped.",
        "Select a purple draft wall to open precision controls.",
        "Select wall, choose Grab / Move, hold trigger and move your hand.",
        "Use Nudge for 50/100/250 mm adjustments.",
        "Grid and Axis change the next draft wall's alignment.",
      ] };
  }
  if (quest?.multiSelect && !viewsOpen && !browser.open && !footprint.enabled && !footprint.changed) {
    const count=quest.selectedCount??0;
    const edit=(action:Extract<MenuAction,{area:"draft"}>["action"],direction?:Extract<MenuAction,{area:"draft"}>["direction"]):MenuAction=>({area:"draft",action,direction});
    const controls:{label:string;action:MenuAction;disabled?:boolean}[]=[
      {label:"Single select",action:questAction("multi-select")},
      ...(quest.budget?[{label:"Live budget",action:questAction("budget")}]:[]),
      {label:"Clear selection",action:questAction("clear-group"),disabled:!count},
      {label:"Magnetic "+(quest.magnetic===false?"off":"on"),action:questAction("magnetic")},
      {label:"Step "+Math.round(quest.nudgeM*1000)+"mm",action:questAction("nudge-size")},
      ...(["left","right","forward","back"] as const).map(direction=>({label:"Nudge "+direction,action:edit("nudge",direction),disabled:!count})),
      {label:"Rotate group 90°",action:edit("rotate"),disabled:!count},
      {label:"Duplicate group",action:edit("duplicate"),disabled:!count},
      {label:quest.deleteArmed?"Confirm delete":"Delete group…",action:edit("delete"),disabled:!count},
      {label:"Undo",action:{area:"history",action:"undo"},disabled:!interaction?.canUndo},
      {label:"Redo",action:{area:"history",action:"redo"},disabled:!interaction?.canRedo},
    ];
    for(const [i,e] of controls.entries())add(e.label,20+(i%4)*235,105+Math.floor(i/4)*82,221,69,e.action,{disabled:e.disabled});
    return {buttons,title:"MULTI-SELECT · "+count+" WALLS",width:WIDTH,height:105+Math.ceil(controls.length/4)*82+68,note:"Point at a local draft wall and trigger to add or remove it. Green walls are selected."};
  }
  if(quest?.angleTools&&quest.selectedWall&&!viewsOpen&&!browser.open&&!footprint.enabled&&!footprint.changed){
    const wall=quest.selectedWall;
    const controls:{label:string;action:MenuAction;disabled?:boolean;active?:boolean}[]=[
      {label:"Exact angle",action:{area:"number",action:"start",field:"angle"}},
      {label:"Pivot: "+(quest.rotationPivot??"start"),action:{area:"wall-angle",action:"pivot"}},
      {label:quest.connectedRotation===false?"Junctions OFF":"Junctions ON",action:{area:"wall-angle",action:"connected"},active:quest.connectedRotation!==false},
      ...[-15,-5,-1,1,5,15].map(degrees=>({label:(degrees>0?"+":"")+degrees+"°",action:{area:"wall-angle",action:"step",degrees} as MenuAction})),
      {label:"Rotate 90°",action:{area:"wall-angle",action:"step",degrees:90}},
      {label:"Undo",action:{area:"history",action:"undo"},disabled:!interaction?.canUndo},
      {label:"Redo",action:{area:"history",action:"redo"},disabled:!interaction?.canRedo},
      {label:"Back to wall wheel",action:{area:"wall-angle",action:"panel"}},
      {label:"Close tools",action:questAction("hide-tools")},
    ];
    for(const [i,c] of controls.entries())add(c.label,20+(i%3)*315,118+Math.floor(i/3)*79,300,69,c.action,{active:c.active,disabled:c.disabled});
    return {buttons,title:"WALL ANGLE · "+wallAngleDegrees(wall).toFixed(1)+"°",subtitle:wallDimensionText(Math.hypot(wall.end[0]-wall.start[0],wall.end[1]-wall.start[1]),wall.heightM,wall.assembly),width:WIDTH,height:572,
      note:quest.feedback||"Rotate about the chosen pivot. Junctions ON also preserves adjoining endpoints during wall drags and stretches.",sections:[{label:"PRECISION ROTATION · LOCAL DRAFT",y:100}]};
  }
  // A selected local wall replaces the crowded toolbox with direct manipulation.
  if (quest?.selectedWall && !viewsOpen && !browser.open && !footprint.enabled && !footprint.changed) {
    if (quest.openingTools && quest.selectedWall.openings.length) {
      const list=quest.selectedWall.openings;
      const opening=list[(quest.openingIndex??0)%list.length];
      const field=(name:NumericDraftField):MenuAction=>({area:"number",action:"start",field:name});
      const adjust=(action:Extract<MenuAction,{area:"opening"}>["action"],deltaMm:number):MenuAction=>
        ({area:"opening",action,deltaMm});
      const controls: {label:string;action:MenuAction}[]=[
        {label:"Next opening",action:questAction("next-opening")},
        {label:"Slide by hand",action:adjust("drag",0)},
        {label:"Slide -50mm",action:adjust("shift",-50)},
        {label:"Slide +50mm",action:adjust("shift",50)},
        {label:"Width -50mm",action:adjust("width",-50)},
        {label:"Width +50mm",action:adjust("width",50)},
        {label:"Height -50mm",action:adjust("height",-50)},
        {label:"Height +50mm",action:adjust("height",50)},
        {label:"Exact offset",action:field("opening-offset")},
        {label:"Exact width",action:field("opening-width")},
        {label:"Exact height",action:field("opening-height")},
        {label:"Exact sill",action:field("opening-sill")},
        ...(opening.openingKind==="door"?[{label:"Type: "+(opening.doorMechanism??"swing"),action:adjust("mechanism",0)},{label:"Open / close",action:adjust("toggle",0)}]:[]),
        {label:"Back to wall",action:questAction("openings")},
      ];
      for(const [i,entry] of controls.entries()) add(entry.label,
        20+(i%3)*315,115+Math.floor(i/3)*79,300,66,entry.action);
      return {buttons,title:opening.openingKind.toUpperCase()+" · "+
        Math.round(opening.widthM*1000)+"×"+Math.round(opening.heightM*1000)+" mm",
        width:WIDTH,height:510,sections:[{label:"OPENING "+((quest.openingIndex??0)%list.length+1)+"/"+list.length,y:98}],
        note:"Draft wall opening only. Changes preserve host and reject overlap."};
    }
    const wall = quest.selectedWall;
    const length = Math.round(Math.hypot(wall.end[0]-wall.start[0],wall.end[1]-wall.start[1])*1000);
    const edit = (action: Extract<MenuAction,{area:"draft"}>["action"],
      direction?: Extract<MenuAction,{area:"draft"}>["direction"]): MenuAction =>
      ({area:"draft",action,direction});
    const controls: {label:string; action:MenuAction; disabled?:boolean}[] = [
      {label:"Grab / Move",action:edit("move")},
      {label:"Wall construction",action:questAction("wall-profiles")},
      {label:"Layers",action:questAction("layers")},
      {label:quest.dimensions===false?"Show dimensions":"Hide dimensions",action:questAction("dimensions")},
      {label:quest.allDimensions?"All dimensions ON":"All dimensions OFF",action:questAction("all-dimensions")},
      {label:"Multi-select",action:questAction("multi-select")},
      {label:"Exact length",action:{area:"number",action:"start",field:"length"}},
      {label:"Exact height",action:{area:"number",action:"start",field:"height"}},
      {label:"Set X (start)",action:{area:"number",action:"start",field:"x"}},
      {label:"Set Z (start)",action:{area:"number",action:"start",field:"z"}},
      {label:"Edit openings",action:questAction("openings"),disabled:!wall.openings.length},
      {label:"Review + cost",action:questAction("review")},
      ...(quest.budget?[{label:"Live budget",action:questAction("budget")}]:[]),
      {label:"Stretch end",action:edit("stretch")},
      {label:"Nudge left",action:edit("nudge","left")},
      {label:"Nudge right",action:edit("nudge","right")},
      {label:"Nudge forward",action:edit("nudge","forward")},
      {label:"Nudge back",action:edit("nudge","back")},
      {label:"Step " + Math.round(quest.nudgeM*1000) + "mm",action:questAction("nudge-size")},
      {label:"Angle "+wallAngleDegrees(wall).toFixed(1)+"°",action:{area:"number",action:"start",field:"angle"}},
      {label:"Pivot "+(quest.rotationPivot??"start"),action:{area:"wall-angle",action:"pivot"}},
      {label:quest.connectedRotation===false?"Junctions OFF":"Junctions ON",action:{area:"wall-angle",action:"connected"}},
      ...[-15,-5,-1,1,5,15].map(degrees=>({label:(degrees>0?"+":"")+degrees+"°",action:{area:"wall-angle",action:"step",degrees} as MenuAction})),
      {label:"Rotate 90°",action:{area:"wall-angle",action:"step",degrees:90}},
      {label:"Duplicate",action:edit("duplicate")},
      {label:"Undo",action:{area:"history",action:"undo"},disabled:!interaction?.canUndo},
      {label:"Redo",action:{area:"history",action:"redo"},disabled:!interaction?.canRedo},
      {label:quest.deleteArmed?"Confirm delete":"Delete…",action:edit("delete")},
      {label:"Back to tools",action:questAction("back")},
    ];
    const columns=4, stride=(WIDTH-40)/columns, height=110+Math.ceil(controls.length/columns)*84+56;
    for (const [i,c] of controls.entries()) add(c.label,
      20+(i%columns)*stride, 110+Math.floor(i/columns)*84, stride-13, 70, c.action,
      {disabled:c.disabled});
    return { buttons, title: "EDIT WALL · " + length + " mm", subtitle:wallDimensionText(length/1000,wall.heightM,wall.assembly),
      width: WIDTH, height,
      note: quest.deleteArmed?"Confirm delete or Back to cancel. Undo restores.":"Trigger & hold to move a draft wall; source stays unchanged.",
      sections: [{label:"SELECT · GRAB · MOVE · RELEASE",y:93}] };
  }
  if (viewsOpen) {
    for (const [index, option] of CONSTRUCTION_STAGES.entries()) {
      add(option.label, 20 + 235 * (index % 4), 69 + 78 * Math.floor(index / 4), 222, 65,
        { area: "view", stage: option.id }, { active: stage === option.id });
    }
    const extra:{label:string;action:MenuAction;disabled?:boolean}[]=[
      {label:"Board: "+(quest?.liningBoard??"standard"),action:{area:"lining",action:"board"}},
      {label:quest?.liningHidden?"Restore wall lining":"Inspect selected wall",action:{area:"lining",action:"inspect"},disabled:!quest?.selectedWall},
      {label:"Back",action:{area:"view"}},
    ];
    extra.forEach((entry,i)=>{const index=CONSTRUCTION_STAGES.length+i;add(entry.label,20+235*(index%4),69+78*Math.floor(index/4),222,65,entry.action,{disabled:entry.disabled});});
    return { buttons, title: "Construction view", width: WIDTH, height: 110 + 78 * Math.ceil((CONSTRUCTION_STAGES.length+extra.length)/4),
      note: stageDetails(stage).description };
  }
  if (browser.open && browser.groups) {
    const page = browser.groupPage ?? 0;
    const start = page * GROUPS_PER_PAGE;
    for (const [index, [, label]] of CATALOGUE_GROUPS.slice(start, start + GROUPS_PER_PAGE).entries()) {
      add(label, 20 + index % 3 * 318, 67 + Math.floor(index / 3) * 62, 304, 52,
        browse({ kind: "choose-group", index: start + index }));
    }
    add("Previous", 20, 322, 153, 54, browse({ kind: "group-page", step: -1 }), { disabled: !page });
    add("Next", 184, 322, 153, 54, browse({ kind: "group-page", step: 1 }), { disabled: page === lastGroupPage });
    add("Back to tools", 755, 322, 205, 54, browse({ kind: "toggle" }));
    return { buttons, title: "Item categories", width: WIDTH, height: 430,
      note: "Categories " + (page + 1) + " of " + (lastGroupPage + 1) };
  }
  if (browser.open) {
    const { category, page } = browser;
    const list = optionsByGroup[category];
    add("‹ Category", 20, 68, 165, 55, browse({ kind: "category", step: -1 }));
    add("Category ›", 795, 68, 165, 55, browse({ kind: "category", step: 1 }));
    for (const [index, entry] of list.slice(page * PER_PAGE, (page + 1) * PER_PAGE).entries()) {
      add(entry.label, index % 2 ? 500 : 20, 139 + Math.floor(index / 2) * 65, 460, 55,
        items({ kind: "choose", itemId: entry.id }), { swatch: entry.visual.color, active: item?.id === entry.id });
    }
    add("‹ Page", 20, 343, 138, 55, browse({ kind: "page", step: -1 }), { disabled: page === 0 });
    add("Page ›", 169, 343, 138, 55, browse({ kind: "page", step: 1 }), { disabled: page >= maxPage(category) });
    if (maxPage(category) > 9) {
      add("‹‹ 5 pages", 319, 343, 143, 55, browse({ kind: "page", step: -5 }), { disabled: page === 0 });
      add("5 pages ››", 474, 343, 143, 55, browse({ kind: "page", step: 5 }), { disabled: page >= maxPage(category) });
    }
    add("Undo item", 648, 343, 160, 55, items({ kind: "undo" }), { disabled: !itemUndo });
    add("Categories", 819, 343, 141, 55, browse({ kind: "groups" }));
    return { buttons, title: "Materials & fixtures", width: WIDTH, height: 457,
      subtitle: CATALOGUE_GROUPS[category][1] + " · " + list.length + " options",
      note: "Page " + (page + 1) + " of " + (maxPage(category) + 1) + " · Pick an item to place it." };
  }
  const hasWall = build.walls.some(wall => wall.levelId === levelId);
  const canMove = hasWall || build.ceilings.some(ceiling => ceiling.levelId === levelId);
  const actions: { label: string; target: MenuAction; active?: boolean; disabled?: boolean }[] =
    BUILD_TOOLS.map(({ id, label }) => ({ label: id === "frame" ? "Open frame" : label,
      target: { area: "build", action: { kind: "tool", tool: id } },
      active: build.tool === id, disabled: !levelId || footprint.enabled || footprint.changed ||
        ((id === "door" || id === "window" || id === "frame") && !hasWall) ||
        ((id === "stretch" || id === "move") && !canMove) ||
        (id==="opening-move" && !build.walls.some(wall=>wall.levelId===levelId&&wall.openings.length>0)) }));
  actions.push(
    { label: "Items", target: browse({ kind: "groups" }), active: !!item },
    { label: "View", target: { area: "view" } },
    { label: "Undo", target: interaction ? { area: "history", action: "undo" } :
      item ? items({ kind: "undo" }) : { area: "build", action: { kind: "undo" } },
      disabled: interaction ? !interaction.canUndo : item ? !itemUndo : !build.history.length && !activeStart(build, levelId) },
    { label: "Done", target: interaction ? { area: "done" } :
      item ? items({ kind: "done" }) : { area: "build", action: { kind: "done" } },
      disabled: interaction ? interaction.mode === "inspect" : !item && !build.tool },
  );
  if (interaction?.canRedo) actions.push({ label: "Redo", target: { area: "history", action: "redo" } });
  if (interaction?.levels && interaction.levels.length > 1) {
    const levels = ["all", ...interaction.levels];
    const id = levels[(levels.indexOf(interaction.level ?? "all") + 1) % levels.length];
    actions.push({ label: interaction.level === "all" ? "All levels ↻" : (interaction.level ?? "Level") + " ↻",
      target: { area: "level", id } });
  }
  if (footprint.available) actions.push({ label: footprint.enabled ? "Done resizing" : "Footprint",
    target: { area: "footprint" }, active: footprint.enabled });
  if (footprint.changed) actions.push({ label: "Reset size", target: { area: "footprint", reset: true } });
  if (item && itemCanRotate(item)) actions.push({ label: "Rotate " + turn * 90 + "°", target: items({ kind: "rotate" }) });
  if (quest?.compact) {
    const compact: {label:string;action:MenuAction;disabled?:boolean}[]=[
      {label:"Build tools",action:questAction("compact")},
      {label:"Wall construction",action:questAction("wall-profiles")},
      {label:quest.dimensions===false?"Show dimensions":"Hide dimensions",action:questAction("dimensions")},
      ...(quest.budget?[{label:"Live budget",action:questAction("budget")}]:[]),
      {label:"Multi-select",action:questAction("multi-select"),disabled:!hasWall||footprint.enabled||footprint.changed},
      {label:"Magnetic "+(quest.magnetic===false?"off":"on"),action:questAction("magnetic")},
      {label:"Items",action:browse({kind:"groups"})},
      {label:"Next stage",action:questAction("next-stage")},
      {label:"Next level",action:questAction("next-floor")},
      {label:quest.teleport?"Exit teleport":"Teleport",action:questAction("teleport"),
        disabled:!quest.canTeleport},
      {label:"Save draft",action:questAction("save")},
      {label:quest.overview?"Hide plan":"2D plan",action:questAction("overview")},
      {label:quest.elevatedView?"Walkthrough":"3D bird’s-eye",action:questAction("elevated-view")},
      {label:"Walk "+(quest.walkSpeed??1.2)+" m/s",action:questAction("walk-speed")},
      {label:quest.night?"Daylight":"Night view",action:questAction("lighting-night")},
      {label:quest.previewLights?"Lights ON":"Lights OFF",action:questAction("lighting-on")},
      {label:quest.ghost?"Ghost ON · walk through":"Ghost OFF · solid walls",action:questAction("ghost")},
      {label:"Undo",action:{area:"history",action:"undo"},disabled:!interaction?.canUndo},
      {label:"Redo",action:{area:"history",action:"redo"},disabled:!interaction?.canRedo},
      {label:"Done",action:{area:"done"}},
      {label:"Help",action:questAction("help")},
    ];
    for(const [i,entry] of compact.entries()) add(entry.label,
      20+(i%4)*235,105+Math.floor(i/4)*82,221,69,entry.action,{disabled:entry.disabled});
    return {buttons,title:"QUEST QUICK TOOLS",width:WIDTH,
      height:105+Math.ceil(compact.length/4)*82+68,
      note:"Compact palette · Build tools opens the full tool selection.",
      sections:[{label:"NAVIGATE · EDIT · UNDO",y:88}]};
  }
  if (quest) {
    actions.push(
      {label:"Compact",target:questAction("compact")},
      {label:"Wall construction",target:questAction("wall-profiles")},
      {label:"Layers",target:questAction("layers")},
      {label:quest.dimensions===false?"Show dimensions":"Hide dimensions",target:questAction("dimensions")},
      {label:quest.allDimensions?"All dimensions ON":"All dimensions OFF",target:questAction("all-dimensions"),active:quest.allDimensions},
      ...(quest.budget?[{label:"Live budget",target:questAction("budget")}]:[]),
      {label:"Multi-select",target:questAction("multi-select"),disabled:!hasWall||footprint.enabled||footprint.changed},
      {label:"Magnetic "+(quest.magnetic===false?"off":"on"),target:questAction("magnetic")},
      {label:quest.teleport?"Exit teleport":"Teleport",target:questAction("teleport"),
        disabled:!quest.canTeleport},
      {label:"Save draft",target:questAction("save")},
      {label:quest.overview?"Hide plan":"Architectural plan",target:questAction("overview")},
      {label:quest.elevatedView?"Walkthrough":"3D bird’s-eye",target:questAction("elevated-view")},
      {label:"Walk "+(quest.walkSpeed??1.2)+" m/s",target:questAction("walk-speed")},
      {label:quest.night?"Daylight":"Night view",target:questAction("lighting-night")},
      {label:quest.previewLights?"Lights ON":"Lights OFF",target:questAction("lighting-on"),active:quest.previewLights},
      {label:quest.ghost?"Ghost ON":"Ghost OFF",target:questAction("ghost"),active:quest.ghost},
      {label:"Grid " + Math.round(quest.gridM*1000) + "mm",target:questAction("grid")},
      {label:"Axis " + quest.axis,target:questAction("axis")},
      {label:quest.pinned?"Unpin panel":"Pin panel",target:questAction("pin")},
      {label:"Recenter",target:questAction("recenter")},
      {label:"Help",target:questAction("help")},
    );
  }
  const columns = 5, stride = (WIDTH - 40) / columns, rowHeight = 77;
  const toolCount = BUILD_TOOLS.length;
  const sections = [{label:"BUILD & EDIT",y:90}];
  function addGroup(entries: typeof actions, startY: number) {
    for (const [index, entry] of entries.entries()) add(entry.label,
      20+stride*(index%columns), startY+Math.floor(index/columns)*rowHeight,
      stride-12, 65, entry.target, {active:entry.active,disabled:entry.disabled});
    return startY + Math.ceil(entries.length / columns)*rowHeight;
  }
  const afterTools = addGroup(actions.slice(0,toolCount),108);
  const controlsY = afterTools + 54;
  sections.push({label:"MATERIALS, VIEWS & CONTROLS",y:controlsY-20});
  const afterControls = addGroup(actions.slice(toolCount),controlsY);
  return {buttons,sections,title:item?.label??"PLANREADER TOOLS",width:WIDTH,
    height:afterControls+58, note:hint||"Point and trigger to choose. All changes are drafts."};
}
