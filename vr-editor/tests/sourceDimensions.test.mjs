import test from "node:test";
import assert from "node:assert/strict";
import {sourceWallDimensions,sourceDimensionCount} from "../src/sourceDimensions.ts";
function wall(){
 return {
  objectId:"W1",canonicalObjectId:"canonical-w1",objectType:"wall",
  objectRevision:"hash",renderState:"verified",unresolvedIssues:[],
  source:{sourceFileId:"pdf",sheet:"A101",page:3,originalGeometryRef:"line-4"},
  geometry:{kind:"wallFace",start:[0,0],end:[4,0],heightM:2.7},
 };
}
test("source dimensions come from existing source-backed wall face only",()=>{
 const row=wall();const before=structuredClone(row);
 const dimension=sourceWallDimensions(row);
 assert.equal(dimension.lengthMetres,4);
 assert.equal(dimension.heightMetres,2.7);
 assert.match(dimension.label,/4.000 m × 2.700 m · SOURCE REVIEW/);
 assert.deepEqual(row,before);
 assert.equal(sourceDimensionCount([row]),1);
});
test("refuse inferred dimensions from review, missing sources or unbounded geometry",()=>{
 const row=wall();
 for(const key of ["canonicalObjectId","objectRevision"]) {
   const invalid={...row,[key]:null};assert.equal(sourceWallDimensions(invalid),null);
 }
 assert.equal(sourceWallDimensions({...row,renderState:"review"}),null);
 assert.equal(sourceWallDimensions({...row,unresolvedIssues:["missing-source"]}),null);
 assert.equal(sourceWallDimensions({...row,geometry:{kind:"wallLine",start:[0,0],end:[4,0]}}),null);
 assert.equal(sourceWallDimensions({...row,source:{...row.source,originalGeometryRef:null}}),null);
 assert.equal(sourceWallDimensions({...row,geometry:{...row.geometry,heightM:NaN}}),null);
 assert.equal(sourceWallDimensions({...row,geometry:{...row.geometry,end:[Infinity,0]}}),null);
});
