import type {PlacedWall,CeilingDraft,BuildAction} from "./buildPlacement.ts";
import {exactDraftWall} from "./vrDraftGeometry.ts";
export type PreciseCommand={kind:"wall"|"ceiling";field:"height"|"length"|"x"|"z";mm:number;relative:boolean};
export function parsePreciseCommand(input:string):PreciseCommand|null{
 const s=input.trim().toLowerCase().replace(/[.!?]$/,"").replace(/\s+/g," ").replace(/\b(\d)\s*,\s*(\d{3})\b/g,"$1$2");
 if(s.length>160)return null;
 const match=s.match(/^(?:set|make) (?:this |the )?(wall|ceiling) (height|length|x|z)(?: to)? (-?\d+(?:\.\d+)?) (mm|millimetres?|millimeters?|cm|centimetres?|centimeters?|m|metres?|meters?)$/)
  ??s.match(/^(?:set|make) (?:this |the )?(wall|ceiling) (-?\d+(?:\.\d+)?) (mm|millimetres?|millimeters?|cm|centimetres?|centimeters?|m|metres?|meters?) (high|long)$/)?.map((v,i,a)=>i===2?a[4]==="high"?"height":"length":i===3?a[2]:i===4?a[3]:v);
 if(match){
  const [,kind,field,num,unit]=match;
  if(kind==="ceiling"&&field!=="height")return null;
  const mm=Number(num)*(unit==="mm"||unit.startsWith("millim")?1:unit==="cm"||unit.startsWith("centim")?10:1000);
  if(!Number.isSafeInteger(mm))return null;
  return {kind:kind as PreciseCommand["kind"],field:field as PreciseCommand["field"],mm,relative:false};
 }
 const move=s.match(/^move (?:this |the )?wall ([xz])(?: by)? (-?\d+(?:\.\d+)?) (mm|millimetres?|millimeters?|cm|centimetres?|centimeters?|m|metres?|meters?)$/);
 if(!move)return null;
 const [,field,num,unit]=move;
 const mm=Number(num)*(unit==="mm"||unit.startsWith("millim")?1:unit==="cm"||unit.startsWith("centim")?10:1000);
 if(!Number.isSafeInteger(mm))return null;
 return {kind:"wall",field:field as "x"|"z",mm,relative:true};
}
export function previewPreciseCommand(command:PreciseCommand,wall:PlacedWall|null,ceiling:CeilingDraft|null):BuildAction|null{
 if(command.kind==="ceiling"){
  if(!ceiling||command.field!=="height"||command.relative||command.mm<50||command.mm>20000||!Number.isSafeInteger(command.mm)||ceiling.heightM===command.mm/1000)return null;
  return {kind:"adjust-ceiling",previous:ceiling,ceiling:{...ceiling,heightM:command.mm/1000}};
 }
 if(!wall)return null;
 const value=command.mm+(command.relative&&["x","z"].includes(command.field)?Math.round(wall.start[command.field==="x"?0:1]*1000):0);
 const updated=exactDraftWall(wall,command.field,value);
 return updated&&JSON.stringify(updated)!==JSON.stringify(wall)?{kind:"adjust",previous:wall,wall:updated}:null;
}
