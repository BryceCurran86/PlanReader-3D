/** Bounded metric construction visual layout, not structural design or verified quantities.
 * AS 1684 member/connection design requires loads, grade, span and wind inputs.
 * AS/NZS 2589 installation requirements depend on the selected lining system.
 * Defaults below are editable illustrative geometry, never certified minimums.
 */
export type Rect = { x0:number; x1:number; y0:number; y1:number };
export type FrameRole = "bottom-plate"|"top-plate"|"stud"|"king"|"trimmer"|"lintel"|"sill"|"cripple"|"nogging";
export type FrameMember = Rect & { role:FrameRole };
export type FramePreset = { memberWidth:number; studSpacing:number; noggingSpacing:number; lintelDepth:number; topPlates:1|2 };
export const NOMINAL_TIMBER:FramePreset={memberWidth:.045,studSpacing:.45,noggingSpacing:1.2,lintelDepth:.14,topPlates:2};
export type LiningPreset={sheetLength:number;sheetWidth:number;fixingSpacing:number;supportSpacing:number};
export const NOMINAL_LINING:LiningPreset={sheetLength:2.4,sheetWidth:1.2,fixingSpacing:.3,supportSpacing:.45};
export type LiningJoint={axis:"horizontal"|"vertical";at:number;from:number;to:number;kind:"recessed"|"butt"|"perimeter"};
export type LiningLayout={boards:Rect[];joints:LiningJoint[];fixings:{x:number;y:number}[]};
const EPS=1e-7;
const intersects=(a:Rect,b:Rect)=>Math.min(a.x1,b.x1)-Math.max(a.x0,b.x0)>EPS&&Math.min(a.y1,b.y1)-Math.max(a.y0,b.y0)>EPS;
const valid=(r:Rect)=>[r.x0,r.x1,r.y0,r.y1].every(Number.isFinite)&&r.x1-r.x0>EPS&&r.y1-r.y0>EPS;
function verify(width:number,height:number,holes:readonly Rect[]){
 if(!Number.isFinite(width)||!Number.isFinite(height)||width<.05||height<.05||width>200||height>20||holes.length>100)throw Error("Invalid visual surface dimensions");
 for(let i=0;i<holes.length;i++){
  const h=holes[i];
  if(!valid(h)||h.x0<0||h.y0<0||h.x1>width||h.y1>height||holes.slice(0,i).some(o=>intersects(o,h)))throw Error("Invalid or overlapping visual opening");
 }
}
function subtract(r:Rect,h:Rect):Rect[]{
 if(!intersects(r,h))return [r];
 const x0=Math.max(r.x0,h.x0),x1=Math.min(r.x1,h.x1),y0=Math.max(r.y0,h.y0),y1=Math.min(r.y1,h.y1);
 return [{...r,x1:x0},{...r,x0:x1},{x0,x1,y0:r.y0,y1:y0},{x0,x1,y0:y1,y1:r.y1}].filter(valid);
}
function clip(r:Rect,holes:readonly Rect[]):Rect[]{return holes.reduce<Rect[]>((pieces,h)=>pieces.flatMap(p=>subtract(p,h)),[r]);}
function unique(values:number[]){return [...new Set(values.map(v=>Math.round(v*1e7)/1e7))].sort((a,b)=>a-b);}
export function nominalFrameLayout(width:number,height:number,holes:readonly Rect[],p:FramePreset=NOMINAL_TIMBER):FrameMember[]{
 verify(width,height,holes);
 const t=p.memberWidth,space=p.studSpacing;
 if(![t,space,p.noggingSpacing,p.lintelDepth].every(Number.isFinite)||t<.025||t>.1||space<t*2||space>1||p.noggingSpacing<.25||p.noggingSpacing>2||p.lintelDepth<t||p.lintelDepth>.6||![1,2].includes(p.topPlates)||height<=t*(p.topPlates+1)||width<=t)throw Error("Invalid nominal frame preset");
 const top=height-p.topPlates*t, members:FrameMember[]=[];
 function put(role:FrameRole,r:Rect,obstacles:readonly Rect[]=holes){
  const bounded={x0:Math.max(0,r.x0),x1:Math.min(width,r.x1),y0:Math.max(0,r.y0),y1:Math.min(height,r.y1)};
  if(valid(bounded))for(const piece of clip(bounded,obstacles))members.push({...piece,role});
 }
 put("bottom-plate",{x0:0,x1:width,y0:0,y1:t});
 for(let i=0;i<p.topPlates;i++)put("top-plate",{x0:0,x1:width,y0:top+i*t,y1:top+(i+1)*t});
 const openingMembers:FrameMember[]=[];
 for(const h of holes){
  const headTop=Math.min(top,h.y1+p.lintelDepth),sillBottom=Math.max(t,h.y0-t);
  put("king",{x0:h.x0-2*t,x1:h.x0-t,y0:t,y1:top});
  put("king",{x0:h.x1+t,x1:h.x1+2*t,y0:t,y1:top});
  put("trimmer",{x0:h.x0-t,x1:h.x0,y0:t,y1:headTop});
  put("trimmer",{x0:h.x1,x1:h.x1+t,y0:t,y1:headTop});
  put("lintel",{x0:h.x0,x1:h.x1,y0:h.y1,y1:headTop});
  if(h.y0>t)put("sill",{x0:h.x0,x1:h.x1,y0:sillBottom,y1:h.y0});
 }
 openingMembers.push(...members.filter(m=>!m.role.endsWith("plate")));
 const xs=[t/2,width-t/2];for(let x=space;x<width-t/2;x+=space)xs.push(x);
 const obstacles=[...holes,...openingMembers];
 for(const x of unique(xs)){
  const r={x0:x-t/2,x1:x+t/2,y0:t,y1:top};
  for(const piece of clip(r,obstacles)){
   if(piece.x1-piece.x0<t-EPS)continue;
   put(piece.y0>t+EPS||piece.y1<top-EPS?"cripple":"stud",piece,[]);
  }
 }
 const verticals=members.filter(m=>["stud","king","trimmer","cripple"].includes(m.role));
 const blocked=[...holes,...verticals,...openingMembers];
 for(let y=t+p.noggingSpacing;y+t<top;y+=p.noggingSpacing)put("nogging",{x0:0,x1:width,y0:y,y1:y+t},blocked);
 return members;
}
export function nominalLiningLayout(width:number,height:number,holes:readonly Rect[],p:LiningPreset=NOMINAL_LINING):LiningLayout{
 verify(width,height,holes);
 if(![p.sheetLength,p.sheetWidth,p.fixingSpacing,p.supportSpacing].every(Number.isFinite)||p.sheetLength<.6||p.sheetLength>6||p.sheetWidth<.6||p.sheetWidth>1.5||p.fixingSpacing<.1||p.fixingSpacing>1||p.supportSpacing<.2||p.supportSpacing>1)throw Error("Invalid nominal sheet preset");
 const boards:Rect[]=[],joints:LiningJoint[]=[],fixings:LiningLayout["fixings"]=[];
 function line(axis:LiningJoint["axis"],at:number,from:number,to:number,kind:LiningJoint["kind"]){
  let spans:[[number,number]]|[number,number][]=[[from,to]];
  for(const h of holes){
   const a=axis==="horizontal"?h.y0:h.x0,b=axis==="horizontal"?h.y1:h.x1;
   if(at<a-EPS||at>b+EPS)continue;
   const lo=axis==="horizontal"?h.x0:h.y0,hi=axis==="horizontal"?h.x1:h.y1;
   spans=spans.flatMap(([s,e]):[number,number][]=>hi<=s||lo>=e?[[s,e]]:[[s,Math.min(e,lo)],[Math.max(s,hi),e]].filter(pair=>pair[1]-pair[0]>EPS) as [number,number][]);
  }
  for(const [s,e] of spans)if(e-s>EPS)joints.push({axis,at,from:s,to:e,kind});
 }
 for(let row=0,y=0;y<height-EPS;row++,y+=p.sheetWidth){
  const endY=Math.min(height,y+p.sheetWidth);
  const cuts=[0,width];for(let x=row%2?p.sheetLength/2:p.sheetLength;x<width-EPS;x+=p.sheetLength)cuts.push(x);
  const xs=unique(cuts);
  for(let i=0;i<xs.length-1;i++)boards.push(...clip({x0:xs[i],x1:xs[i+1],y0:y,y1:endY},holes));
  for(const x of xs.slice(1,-1))line("vertical",x,y,endY,"butt");
  if(y>EPS)line("horizontal",y,0,width,"recessed");
 }
 line("horizontal",0,0,width,"perimeter");line("horizontal",height,0,width,"perimeter");
 line("vertical",0,0,height,"perimeter");line("vertical",width,0,height,"perimeter");
 for(let x=.025;x<width-.01;x+=p.supportSpacing)for(let y=.025;y<height-.01;y+=p.fixingSpacing){
  if(!holes.some(h=>x>=h.x0-.01&&x<=h.x1+.01&&y>=h.y0-.01&&y<=h.y1+.01))fixings.push({x,y});
 }
 return {boards,joints,fixings};
}
