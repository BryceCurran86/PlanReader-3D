const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

test('zoom observer settles after label updates and unrelated DOM changes', () => {
  let callback;
  let pending = false;
  let label = '75%';
  let writes = 0;
  const readout = {
    get textContent() { return label; },
    set textContent(value) {
      label = value;
      writes++;
      // DOM textContent replaces text children even for an identical value.
      pending = true;
    },
  };
  const context = {
    document: {
      documentElement: {},
      querySelector: () => ({}),
      getElementById: (id) => id === 'pbZoomReadout' ? readout
        : id === 'canvasWrap' ? null : {},
    },
    MutationObserver: class {
      constructor(fn) { callback = fn; }
      observe() {}
    },
    window: { addEventListener() {} },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,
    '../planreader_takeoff_studio/frontend/zoom_patch.js'), 'utf8'), context);
  function settle() {
    let deliveries = 0;
    while (pending && deliveries < 10) {
      pending = false;
      callback();
      deliveries++;
    }
    assert.equal(pending, false, 'observer must not perpetually enqueue itself');
  }
  settle();
  assert.equal(label, '100%');
  assert.equal(writes, 1);
  pending = true;
  settle();
  assert.equal(writes, 1, 'unrelated changes must not rewrite the zoom label');
  label = 'stale';
  pending = true;
  settle();
  assert.equal(label, '100%');
  assert.equal(writes, 2);
});
