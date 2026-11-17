import test from "node:test";
import assert from "node:assert/strict";
import {reviewStamp,safeCaptureSize} from "../src/reviewCapture.ts";
const scene={scope:{projectId:"Lot/16: Private",documentId:"sheet set",
  revisionId:"R01",snapshotId:"locked-snap",sourceSha256:"a".repeat(64)}};
test("captures are explicitly watermarked as review, never source authority",()=>{
  const stamp=reviewStamp(scene,12);
  assert.match(stamp.warning,/NOT A SOURCE MEASUREMENT/);
  assert.match(stamp.warning,/NOT.*APPROVED QUOTE/);
  assert.equal(stamp.title,"PLANREADER · VR VISUAL REVIEW");
  assert.match(stamp.subtitle,/Snapshot locked-snap/);
  assert.match(stamp.filename,/^planreader-review-Lot-16--Private-locked-snap\.png$/);
});
test("canvas dimensions are bounded and invalid sizes fail closed",()=>{
  assert.deepEqual(safeCaptureSize(1280,720),[1280,720]);
  assert.deepEqual(safeCaptureSize(8192,4096),[4096,2048]);
  assert.equal(safeCaptureSize(0,200),null);
  assert.equal(safeCaptureSize(NaN,200),null);
  assert.equal(safeCaptureSize(Infinity,200),null);
  assert.equal(safeCaptureSize(200,-1),null);
});
