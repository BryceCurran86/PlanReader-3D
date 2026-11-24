import test from "node:test";
import assert from "node:assert/strict";
import {validOpeningReview,reviewOpeningCorners} from "../src/sourceOpeningReview.ts";
const g={kind:"wallFace",start:[1,2],end:[1,6],heightM:2.7};
const o={openingId:"d",kind:"door",offsetM:1,sillM:0,widthM:.9,heightM:2.1,sheet:"A101",page:3};
const review={status:"review_only",recordCount:1,positioned:[o]};
test("review opening has exact host-relative position and rejects impossible apertures",()=>{
 assert.equal(validOpeningReview(review,g),true);
 assert.deepEqual(reviewOpeningCorners(g,o),[[1,0,3],[1,2.1,3],[1,2.1,3.9],[1,0,3.9],[1,0,3]]);
 assert.equal(validOpeningReview({...review,status:"verified"},g),false);
 assert.equal(validOpeningReview({...review,positioned:[{...o,offsetM:3.5}]},g),false);
 assert.equal(validOpeningReview({...review,recordCount:2,positioned:[o,{...o,openingId:"d2"}]},g),false);
 assert.equal(validOpeningReview(review,{kind:"wallLine",start:g.start,end:g.end}),false);
});