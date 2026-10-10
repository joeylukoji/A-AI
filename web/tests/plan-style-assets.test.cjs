'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function loadAssets() {
  const images = [], timers = new Set();
  class FakeImage {
    constructor() { images.push(this); }
    succeed() { this.naturalWidth = 800; this.naturalHeight = 1200; this.onload(); }
    fail() { this.onerror(); }
  }
  const context = {
    window: { Image: FakeImage },
    setTimeout(fn) { timers.add(fn); return fn; },
    clearTimeout(fn) { timers.delete(fn); },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/plan-style-assets.js'), 'utf8'), context);
  return { assets: context.window.PlanStyleAssets, images, timers, context };
}
const item = id => ({ catalog_id: id });
const drawing = () => {
  const calls = [];
  return new Proxy({ calls }, { get: (target, key) => target[key] ?? ((...args) => calls.push([key, ...args])) });
};
const CATALOGUE_ASSETS = [
  { id: 'table.dining', file: 'table-dining-v2-opt1.png', width: 1.8, depth: 1 },
  { id: 'chair.dining', file: 'chair-dining-v2-opt1.png', width: 0.45, depth: 0.5 },
  { id: 'table.coffee', file: 'table-coffee-v2-opt1.png', width: 1.1, depth: 0.55 },
  { id: 'counter.kitchen', file: 'counter-kitchen-v2-opt1.png', width: 2.4, depth: 0.62 },
  { id: 'stove', file: 'stove-v2-opt1.png', width: 0.6, depth: 0.55 },
  { id: 'fridge', file: 'fridge-v2-opt1.png', width: 0.65, depth: 0.65 },
  { id: 'bathtub', file: 'bathtub-v2-opt1.png', width: 1.7, depth: 0.75 },
  { id: 'toilet', file: 'toilet-v3-opt1.png', width: 0.48, depth: 0.78 },
  { id: 'sink.basin', file: 'sink-basin-v2-opt1.png', width: 0.55, depth: 0.42 },
  { id: 'nightstand', file: 'nightstand-v1-opt1.png', width: 0.45, depth: 0.40 },
  { id: 'wardrobe', file: 'wardrobe-v1-opt1.png', width: 1.20, depth: 0.60 },
  { id: 'desk', file: 'desk-v1-opt1.png', width: 1.20, depth: 0.60 },
  { id: 'fireplace', file: 'fireplace-v2-opt1.png', width: 0.70, depth: 0.55 },
  { id: 'rug.rect', file: 'rug-v1-opt1.png', width: 2.20, depth: 1.60 },
  { id: 'tv.console', file: 'tv-console-v1-opt1.png', width: 1.60, depth: 0.40 },
];

test('assets load only requested known types once, including concurrent prepares', async () => {
  const { assets, images, timers } = loadAssets();
  const input = [item('bed.double'), item('bed.double'), item('unknown'), null];
  const before = JSON.stringify(input);
  const first = assets.prepare(input), second = assets.prepare(input);
  assert.equal(images.length, 1);
  assert.match(images[0].src, /^\/static\/assets\/furniture\/bed-double-v1-opt1\.png$/);
  assert.equal(assets.draw(drawing(), 'bed.double', 1.6, 2), false);
  images[0].succeed();
  assert.equal((await first)[0].status, 'loaded');
  await second;
  assert.equal(timers.size, 0);
  assert.equal(JSON.stringify(input), before);
});

test('loaded sprite uses the local metre footprint and balanced state', async () => {
  const { assets, images } = loadAssets();
  const ready = assets.prepare([item('bed.double')]); images[0].succeed(); await ready;
  const ctx = drawing();
  assert.equal(assets.draw(ctx, 'bed.double', 1.6, 2), true);
  assert.deepEqual(ctx.calls.map(c => c[0]), ['save', 'drawImage', 'restore']);
  assert.deepEqual(ctx.calls[1].slice(2), [-0.8, -1, 1.6, 2]);
  assert.equal(assets.draw(ctx, 'toString', 1, 1), false);
});

test('car source rotates to catalogue head-left horizontal convention', async () => {
  const { assets, images } = loadAssets();
  const ready = assets.prepare([item('car.sedan')]); images[0].succeed(); await ready;
  const ctx = drawing(); assets.draw(ctx, 'car.sedan', 4.2, 1.8);
  assert.deepEqual(ctx.calls[1], ['rotate', -Math.PI / 2]);
  assert.deepEqual(ctx.calls[2].slice(2), [-0.9, -2.1, 1.8, 4.2]);
  assert.equal(ctx.calls.at(-1)[0], 'restore');
});

test('failed and timed-out assets settle to fallback without rejecting or retry storms', async () => {
  const { assets, images, timers } = loadAssets();
  const ready = assets.prepare([item('bed.single'), item('plant.pot')]);
  images[0].fail();
  for (const timeout of [...timers]) timeout();
  const results = await ready;
  assert.deepEqual(Array.from(results, r => r.status), ['failed', 'failed']);
  assert.equal(assets.draw(drawing(), 'bed.single', 1, 2), false);
  await assets.prepare([item('bed.single')]);
  assert.equal(images.length, 2);
  assert.equal(timers.size, 0);
});

test('empty input performs no work', async () => {
  const { assets, images } = loadAssets();
  assert.equal((await assets.prepare()).length, 0);
  assert.equal(images.length, 0);
});

test('extended catalogue routes every sprite to its versioned local file', async () => {
  const { assets, images } = loadAssets();
  const furniture = CATALOGUE_ASSETS.map(({ id }) => item(id));
  const before = JSON.stringify(furniture);
  const ready = assets.prepare(furniture);
  assert.equal(images.length, CATALOGUE_ASSETS.length);
  assert.deepEqual(images.map(image => image.src), CATALOGUE_ASSETS.map(({ file }) =>
    '/static/assets/furniture/' + file));
  images.forEach(image => image.succeed());
  assert.ok((await ready).every(result => result.status === 'loaded'));
  assert.equal(JSON.stringify(furniture), before);
});

test('extended catalogue uses each declared footprint without an implicit quarter turn', async () => {
  const { assets, images } = loadAssets();
  const ready = assets.prepare(CATALOGUE_ASSETS.map(({ id }) => item(id)));
  images.forEach(image => image.succeed()); await ready;
  for (const { id, width, depth } of CATALOGUE_ASSETS) {
    const ctx = drawing();
    assert.equal(assets.draw(ctx, id, width, depth), true, id);
    assert.deepEqual(ctx.calls.find(call => call[0] === 'drawImage').slice(2),
      [-width / 2, -depth / 2, width, depth], id);
    assert.equal(ctx.calls.some(call => call[0] === 'rotate'), false, id);
  }
});

test('furniture renderer keeps world transform and clip around sprite without mutating input', async () => {
  const { assets, images, context } = loadAssets();
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/plan-style-furniture.js'), 'utf8'), context);
  const furniture = [{ catalog_id: 'car.sedan', position: { x: 3, y: 4 },
    rotation_deg: 90, size_m: { w: 4.2, d: 1.8 } }];
  const before = JSON.stringify(furniture);
  const ready = assets.prepare(furniture); images[0].succeed(); await ready;
  const ctx = drawing();
  context.window.PlanStyleFurniture({ m2px: () => 20 }).drawFurniture(ctx, furniture,
    p => ({ x: p.x * 20, y: p.y * 20 }));
  assert.deepEqual(ctx.calls.slice(0, 4), [['save'], ['translate', 60, 80], ['rotate', Math.PI / 2], ['scale', 20, 20]]);
  assert.deepEqual(ctx.calls.find(c => c[0] === 'rect'), ['rect', -2.1, -0.9, 4.2, 1.8]);
  assert.ok(ctx.calls.findIndex(c => c[0] === 'clip') < ctx.calls.findIndex(c => c[0] === 'drawImage'));
  assert.equal(ctx.calls.filter(c => c[0] === 'fill').length, 0);
  assert.equal(ctx.calls.filter(c => c[0] === 'save').length, ctx.calls.filter(c => c[0] === 'restore').length);
  assert.equal(JSON.stringify(furniture), before);
});
