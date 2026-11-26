import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {createDraftEditHandles,pickDraftEditHandle} from "../src/draftEditHandles.ts";
import {initialFinishGroup} from "../src/contextFinishes.ts";
import {openingFrameVisual} from "../src/openingFinishVisual.ts";
import {defaultWallAssembly} from "../src/wallProfiles.ts";
const wall={proposalId:"w",start:[0,0],end:[4,0],scopeKey:"s",levelId:"ground",heightM:2.4,openings:[],assembly:{...defaultWallAssembly("external-timber"),thicknessMm:253}};
test("collinear visible handles choose the frontmost intersection",()=>{
 const shape={kind:"wall",object:wall};
 const ray=new THREE.Ray(new THREE.Vector3(-1,2.56,0),new THREE.Vector3(1,0,0));
 const hit=pickDraftEditHandle(shape,ray);
 assert.equal(hit.mode,"stretch");assert.equal(hit.stretchStart,true);
 const handles=createDraftEditHandles();handles.update(shape);
 assert.equal(handles.group.children[0].geometry,handles.group.children[1].geometry);
 handles.dispose();assert.equal(handles.group.children.length,0);
});
test("context enters paint and floor choices directly but preserves opening hardware menu",()=>{
 assert.equal(initialFinishGroup({hit:{target:"wall"}}),"paint");
 assert.equal(initialFinishGroup({hit:{target:"floor"}}),"floors");
 assert.equal(initialFinishGroup({hit:{target:"opening",opening:{door:true}}}),null);
});
test("nominal jamb spans thick wall without editing aperture",()=>{
 const opening={openingId:"d",openingKind:"door",offsetM:1,widthM:.9,heightM:2.04,sillHeightM:0};
 const frame=openingFrameVisual(wall,opening);assert.ok(frame);
 const m=new THREE.Matrix4(),p=new THREE.Vector3(),q=new THREE.Quaternion(),s=new THREE.Vector3();
 frame.getMatrixAt(0,m);m.decompose(p,q,s);
 assert.ok(Math.abs(s.z-.253)<1e-6);assert.equal(opening.widthM,.9);
 frame.geometry.dispose();frame.material.dispose();frame.dispose();
});
