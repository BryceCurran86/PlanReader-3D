import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {menuButtonAt} from "../src/toolWheelInput.ts";
import {createOutdoorEnvironment} from "../src/outdoorEnvironment.ts";
import {junctionBacking} from "../src/constructionJunctionVisual.ts";
import {defaultWallAssembly} from "../src/wallProfiles.ts";
test("toolbox rejects ambiguous gaps, invalid dimensions and outside clicks",()=>{
 const action={area:"done"};
 const layout={width:200,height:100,title:"Tools",note:"",buttons:[
 {label:"One",x:10,y:10,w:80,h:60,action},
 {label:"Two",x:110,y:10,w:80,h:60,action}]};
 assert.equal(menuButtonAt(layout,100,40),-1);
 assert.equal(menuButtonAt(layout,96,40),0);
 assert.equal(menuButtonAt(layout,104,40),1);
 assert.equal(menuButtonAt(layout,-1,40),-1);
 assert.equal(menuButtonAt({...layout,width:0},0,40),-1);
 assert.equal(menuButtonAt({...layout,buttons:[{...layout.buttons[0],disabled:true},layout.buttons[1]]},50,40),-1);
});
test("outdoor environment switches visibility and disposes its meshes",()=>{
 const scene=new THREE.Scene(),env=createOutdoorEnvironment(scene);
 env.update(true,false,0,0);assert.equal(scene.children.length,2);
 assert.ok(scene.children.every(o=>o.visible));
 assert.equal(scene.children.find(o=>o.name==="PresentationGrass").receiveShadow,true);
 env.update(false,false,0,0);assert.ok(scene.children.every(o=>!o.visible));
 env.dispose();assert.equal(scene.children.length,0);
});
test("nominal junction backing is deterministic and does not change draft geometry",()=>{
 const assembly=defaultWallAssembly("external-timber");
 const wall=(id,start,end)=>({proposalId:id,start,end,scopeKey:"s",levelId:"ground",heightM:2.4,openings:[],assembly});
 const walls=[wall("host",[0,0],[5,0]),wall("a",[2,0],[2,3]),wall("b",[4,0],[4,3])];
 const before=JSON.stringify(walls),first=junctionBacking(walls);
 assert.deepEqual(junctionBacking(walls),first);
 assert.equal(JSON.stringify(walls),before);
 assert.ok(first.every(e=>e.top>e.bottom));
});
