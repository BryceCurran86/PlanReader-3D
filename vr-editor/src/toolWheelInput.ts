import type {MenuLayout} from "./catalogueMenu.ts";
/** Hit the entire visible sector, not just its text rectangle. */
export function radialSector(x:number,y:number):number {
 if(!Number.isFinite(x)||!Number.isFinite(y))return -1;
 const radius=Math.hypot(x,y);
 if(radius<.29)return 8;
 if(radius>1.04)return -1;
 return ((Math.round((Math.atan2(y,x)+Math.PI/2)/(Math.PI/4))%8)+8)%8;
}
export function thumbstickSector(stick:readonly [number,number]):number {
 const n=Math.hypot(...stick);
 return n>=.45?radialSector(stick[0]/n,stick[1]/n):-1;
}
export function menuButtonAt(layout:MenuLayout,x:number,y:number):number {
 if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(layout.width)||!Number.isFinite(layout.height)||layout.width<=0||layout.height<=0||x<0||y<0||x>layout.width||y>layout.height)return -1;
 if(layout.radial){
  const i=radialSector((x-layout.width/2)/(layout.width/2),(y-layout.height/2)/(layout.height/2));
  return i>=0&&layout.buttons[i]&&!layout.buttons[i].disabled?i:-1;
 }
 // A little forgiveness around rectangular buttons; never select through a
 // disabled button or jump to a neighbouring active button on its behalf.
 const direct=layout.buttons.findIndex(b=>x>=b.x&&x<=b.x+b.w&&y>=b.y&&y<=b.y+b.h);
 if(direct>=0)return layout.buttons[direct].disabled?-1:direct;
 let best=-1,distance=Infinity;
 for(let i=0;i<layout.buttons.length;i++){
  const b=layout.buttons[i];
  const d=Math.hypot(Math.max(b.x-x,0,x-b.x-b.w),Math.max(b.y-y,0,y-b.y-b.h));
  if(d<distance-1e-6){best=i;distance=d;}
  else if(Math.abs(d-distance)<=1e-6)best=-1;
 }
 return distance<=12&&best>=0&&!layout.buttons[best].disabled?best:-1;
}

/** A button may dispatch only if the rendered and current targets still agree. */
export function displayedMenuAction(shown:MenuLayout|null,current:MenuLayout,index:number):MenuLayout["buttons"][number]["action"]|null {
 if(!shown||shown.width!==current.width||shown.height!==current.height||shown.radial!==current.radial||!Number.isInteger(index)||index<0)return null;
 const before=shown.buttons[index],after=current.buttons[index];
 if(!before||!after||before.disabled||after.disabled||before.x!==after.x||before.y!==after.y||before.w!==after.w||before.h!==after.h||JSON.stringify(before.action)!==JSON.stringify(after.action))return null;
 return before.action;
}

/** Move one enabled rectangular key in the requested direction; stay at an edge. */
export function adjacentMenuButton(layout:MenuLayout,index:number,dx:number,dy:number):number{
 const enabled=layout.buttons.map((b,i)=>({b,i})).filter(({b})=>!b.disabled);
 if(!enabled.length)return -1;
 const current=layout.buttons[index];if(!current||current.disabled)return enabled[0].i;
 if(Math.max(Math.abs(dx),Math.abs(dy))<.55)return index;
 const horizontal=Math.abs(dx)>=Math.abs(dy),direction=Math.sign(horizontal?dx:dy);
 let best=index,score=Infinity;
 for(const {b,i} of enabled){if(i===index)continue;const x=b.x+b.w/2-current.x-current.w/2,y=b.y+b.h/2-current.y-current.h/2;
 const forward=(horizontal?x:y)*direction;if(forward<1)continue;const cross=Math.abs(horizontal?y:x);const rank=forward+cross*3;
 if(rank<score){best=i;score=rank;}}
 return best;
}
