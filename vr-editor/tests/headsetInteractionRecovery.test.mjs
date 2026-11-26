import test from "node:test";
import assert from "node:assert/strict";
import {displayedMenuAction,adjacentMenuButton} from "../src/toolWheelInput.ts";
const action={area:"quest",action:"quality"};
const layout={width:200,height:150,title:"Tools",note:"",buttons:[
 {label:"Balanced",x:0,y:0,w:90,h:60,action},
 {label:"Other",x:100,y:0,w:90,h:60,action:{area:"quest",action:"environment"}},
 {label:"Disabled",x:0,y:75,w:90,h:60,disabled:true,action:{area:"done"}},
 {label:"Close",x:100,y:75,w:90,h:60,action:{area:"done"}}]};
test("stable menu action survives changing feedback label or selected colour but not action or position",()=>{
 const changed={...layout,buttons:layout.buttons.map(b=>({...b,label:"Changed",active:true}))};
 assert.deepEqual(displayedMenuAction(layout,changed,0),action);
 assert.equal(displayedMenuAction(layout,{...changed,buttons:[{...changed.buttons[0],x:1},...changed.buttons.slice(1)]},0),null);
 assert.equal(displayedMenuAction(layout,{...changed,buttons:[{...changed.buttons[0],action:{area:"done"}},...changed.buttons.slice(1)]},0),null);
});
test("right stick steps through visible enabled keys without selecting disabled ones",()=>{
 assert.equal(adjacentMenuButton(layout,-1,1,0),0);
 assert.equal(adjacentMenuButton(layout,0,1,0),1);
 assert.equal(adjacentMenuButton(layout,1,0,1),3);
 assert.equal(adjacentMenuButton(layout,3,-1,0),3);
 assert.equal(adjacentMenuButton(layout,1,0,0),1);
});
