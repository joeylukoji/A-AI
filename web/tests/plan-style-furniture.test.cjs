'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { loadPlanStyle: loadStyle } = require('./helpers/plan-style-loader.cjs');

function recordingContext() {
  const calls = [];
  const ctx = { calls };
  ctx.createLinearGradient = (...args) => {
    calls.push(['createLinearGradient', ...args]);
    return { addColorStop: (offset, color) => calls.push(['addColorStop', offset, color]) };
  };
  return new Proxy(ctx, {
    get(target, name) {
      if (name in target) return target[name];
      return (...args) => calls.push([name, ...args]);
    },
  });
}

const toScreen = ({ x, y }) => ({ x: x * 20, y: y * 20 });
const item = (catalog_id, x = 3, rotation_deg = 0) => ({
  id: catalog_id,
  catalog_id,
  position: { x, y: 4 },
  rotation_deg,
  size_m: { w: 2.4, d: 1.6, h: 0.8 },
});

// Catalogue routing is checked without freezing the old visual design.
const CATALOG_IDS = [
  'bed.double', 'bed.single', 'sofa.lshape', 'sofa.2seat', 'armchair',
  'table.dining', 'chair.dining', 'table.coffee', 'counter.kitchen', 'stove',
  'nightstand', 'wardrobe', 'desk', 'fireplace', 'bathtub', 'toilet',
  'sink.basin', 'sink', 'car.sedan', 'rug.rect', 'plant.pot', 'fridge',
  'tv.console', 'unknown.catalog',
];

test('each current furniture glyph balances canvas state without mutating input', () => {
  const style = loadStyle();
  const signatures = new Map();
  for (const catalogId of CATALOG_IDS) {
    const furniture = [item(catalogId, 3, 90)];
    const before = JSON.stringify(furniture);
    const ctx = recordingContext();
    style.drawFurniture(ctx, furniture, toScreen);
    const names = ctx.calls.map(([name]) => name);
    assert.equal(names.filter((name) => name === 'save').length, 1, catalogId);
    assert.equal(names.filter((name) => name === 'restore').length, 1, catalogId);
    assert.ok(names.includes('fill'), catalogId);
    assert.ok(names.includes('rotate'), catalogId);
    assert.deepEqual(ctx.calls.find(([name]) => name === 'translate'), ['translate', 60, 80]);
    assert.deepEqual(ctx.calls.find(([name]) => name === 'scale'), ['scale', 20, 20]);
    assert.deepEqual(ctx.calls.find(([name]) => name === 'rotate'), ['rotate', Math.PI / 2]);
    const signature = crypto.createHash('sha256').update(JSON.stringify(ctx.calls)).digest('hex').slice(0, 12);
    if (catalogId === 'sink') assert.equal(signature, signatures.get('sink.basin'));
    else assert.ok(![...signatures.values()].includes(signature), `${catalogId}: unexpected duplicate glyph`);
    signatures.set(catalogId, signature);
    assert.equal(JSON.stringify(furniture), before, catalogId);
  }
});

test('all glyphs clip their ink and retain finite geometry at compact dimensions', () => {
  const style = loadStyle();
  for (const catalogId of CATALOG_IDS) {
    const furniture = item(catalogId);
    furniture.size_m = { w: 0.2, d: 0.1 };
    const ctx = recordingContext();
    style.drawFurniture(ctx, [furniture], toScreen);
    const clip = ctx.calls.findIndex(([name]) => name === 'clip');
    assert.ok(clip > 0 && clip < ctx.calls.findIndex(([name]) => name === 'fill'), catalogId);
    for (const transform of ['translate', 'rotate', 'scale']) {
      const index = ctx.calls.findIndex(([name]) => name === transform);
      assert.ok(index >= 0 && index < clip, `${catalogId}: ${transform} before clipping`);
    }
    assert.deepEqual(ctx.calls[clip - 1], ['rect', -0.1, -0.05, 0.2, 0.1]);
    for (const [name, ...args] of ctx.calls) {
      assert.ok(args.filter((v) => typeof v === 'number').every(Number.isFinite), catalogId);
      if (name === 'roundRect') assert.ok(args[2] > 0 && args[3] > 0, catalogId);
      if (name === 'ellipse') assert.ok(args[2] > 0 && args[3] > 0, catalogId);
    }
  }
});

test('invalid furniture never opens canvas state', () => {
  const style = loadStyle();
  for (const value of [
    null, { ...item('stove'), position: { x: NaN, y: 2 } },
    { ...item('stove'), rotation_deg: Infinity },
    { ...item('stove'), size_m: { w: -1, d: 1 } },
    { ...item('stove'), size_m: { w: 0, d: 1 } },
  ]) {
    const ctx = recordingContext();
    style.drawFurniture(ctx, [value], toScreen);
    assert.deepEqual(ctx.calls, []);
  }
});

test('rugs draw first and invalid positions do not open canvas state', () => {
  const ctx = recordingContext();
  const furniture = [item('bed.double', 2), item('rug.rect', 7), {
    catalog_id: 'fridge', size_m: { w: 0.6, d: 0.6 }, position: { x: null, y: 4 },
  }];
  loadStyle().drawFurniture(ctx, furniture, toScreen);
  const translates = ctx.calls.filter(([name]) => name === 'translate');
  assert.deepEqual(translates, [['translate', 140, 80], ['translate', 40, 80]]);
  assert.equal(ctx.calls.filter(([name]) => name === 'save').length, 2);
  assert.equal(ctx.calls.filter(([name]) => name === 'restore').length, 2);
});

test('an L-shaped sofa stays within its declared footprint at 0, 90 and 270 degrees', () => {
  const style = loadStyle();
  for (const catalogId of ['sofa.lshape', 'sofa.2seat']) {
    const sizes = catalogId === 'sofa.lshape'
      ? [{ w: 2.4, d: 1.6 }, { w: 1, d: 0.16 }, { w: 0.5, d: 0.5 }, { w: 0.2, d: 0.1 }]
      : [{ w: 2.4, d: 1.6 }];
    for (const dimensions of sizes) {
      for (const rotation of [0, 90, 270]) {
        const sofa = item(catalogId, 5.53, rotation);
        sofa.position.y = 6.92;
        Object.assign(sofa.size_m, dimensions);
        const ctx = recordingContext();
        style.drawFurniture(ctx, [sofa], toScreen);
        const { w, d } = sofa.size_m;
        const bounds = rotation === 0 ? { w, d } : { w: d, d: w };
        const angle = rotation * Math.PI / 180;
        assert.deepEqual(ctx.calls.find(([name]) => name === 'rotate'), ['rotate', angle]);
        assert.deepEqual(ctx.calls.find(([name]) => name === 'scale'), ['scale', 20, 20]);
        const rectangles = ctx.calls.filter(([name]) => name === 'roundRect');
        assert.ok(rectangles.length >= 5, `${catalogId} ${rotation} ${w}×${d}: no sofa geometry`);
        for (const [, x, y, width, depth] of rectangles) {
          assert.ok(width > 0 && depth > 0,
            `${catalogId} ${rotation} ${w}×${d}: invalid rectangle ${width}×${depth}`);
          for (const [cx, cy] of [[x, y], [x + width, y], [x + width, y + depth], [x, y + depth]]) {
            const worldX = cx * Math.cos(angle) - cy * Math.sin(angle);
            const worldY = cx * Math.sin(angle) + cy * Math.cos(angle);
            assert.ok(worldX >= -bounds.w / 2 - 1e-9 && worldX <= bounds.w / 2 + 1e-9,
              `${catalogId} ${rotation} ${w}×${d}: x=${worldX} exceeds ${bounds.w}`);
            assert.ok(worldY >= -bounds.d / 2 - 1e-9 && worldY <= bounds.d / 2 + 1e-9,
              `${catalogId} ${rotation} ${w}×${d}: y=${worldY} exceeds ${bounds.d}`);
          }
        }
      }
    }
  }
});

test('car geometry stays inside its footprint at catalog and compact sizes', () => {
  const style = loadStyle();
  for (const [w, d] of [[4.2, 1.8], [2.1, 0.9]]) {
    for (const rotation of [0, 90, 270]) {
      const car = item('car.sedan', 5.53, rotation);
      car.size_m = { w, d, h: 1.45 };
      const before = JSON.stringify(car);
      const ctx = recordingContext();
      style.drawFurniture(ctx, [car], toScreen);
      const limits = { minX: -w / 2, maxX: w / 2, minY: -d / 2, maxY: d / 2 };
      const check = (x, y, name) => {
        assert.ok(x >= limits.minX - 1e-9 && x <= limits.maxX + 1e-9,
          `${w}×${d} ${rotation}° ${name}: x=${x} outside`);
        assert.ok(y >= limits.minY - 1e-9 && y <= limits.maxY + 1e-9,
          `${w}×${d} ${rotation}° ${name}: y=${y} outside`);
      };
      for (const [name, ...args] of ctx.calls) {
        if (name === 'roundRect') {
          const [x, y, width, depth] = args;
          assert.ok(width > 0 && depth > 0);
          check(x, y, name);
          check(x + width, y + depth, name);
        } else if (name === 'ellipse') {
          const [x, y, rx, ry] = args;
          check(x - rx, y - ry, name);
          check(x + rx, y + ry, name);
        } else if (name === 'moveTo' || name === 'lineTo') {
          check(args[0], args[1], name);
        } else if (name === 'quadraticCurveTo') {
          check(args[0], args[1], name);
          check(args[2], args[3], name);
        }
      }
      assert.ok(ctx.calls.filter(([name]) => name === 'roundRect').length >= 6,
        'cab glazing and four wheels');
      assert.equal(ctx.calls.filter(([name]) => name === 'quadraticCurveTo').length, 4,
        'closed vehicle silhouette');
      assert.equal(ctx.calls.filter(([name]) => name === 'ellipse').length, 4,
        'two headlights and two taillights');
      assert.equal(ctx.calls.filter(([name]) => name === 'save').length, 1);
      assert.equal(ctx.calls.filter(([name]) => name === 'restore').length, 1);
      const clipIndex = ctx.calls.findIndex(([name]) => name === 'clip');
      const firstFill = ctx.calls.findIndex(([name]) => name === 'fill');
      assert.ok(clipIndex > 0 && clipIndex < firstFill, 'ink clipped before drawing');
      assert.deepEqual(ctx.calls.slice(clipIndex - 2, clipIndex + 1), [
        ['beginPath'], ['rect', -w / 2, -d / 2, w, d], ['clip'],
      ]);
      assert.deepEqual(ctx.calls.find(([name]) => name === 'rotate'),
        ['rotate', rotation * Math.PI / 180]);
      assert.equal(JSON.stringify(car), before);
    }
  }
});

test('car cabin has separate front and rear glazing inside its roof', () => {
  const ctx = recordingContext();
  const car = item('car.sedan');
  car.size_m = { w: 4.2, d: 1.8, h: 1.45 };
  loadStyle().drawFurniture(ctx, [car], toScreen);
  const rectangles = ctx.calls.filter(([name]) => name === 'roundRect');
  assert.equal(rectangles.length, 7, 'roof, two glazing panes and four wheels');
  const [, roofX, roofY, roofW, roofD] = rectangles[0];
  const [, frontX, frontY, frontW, frontD] = rectangles[1];
  const [, rearX, rearY, rearW, rearD] = rectangles[2];
  assert.ok(frontW > 0 && rearW > 0 && frontD > 0 && rearD > 0);
  assert.ok(frontX >= roofX && frontX + frontW <= roofX + roofW);
  assert.ok(rearX >= roofX && rearX + rearW <= roofX + roofW);
  assert.ok(frontY >= roofY && frontY + frontD <= roofY + roofD);
  assert.ok(rearY >= roofY && rearY + rearD <= roofY + roofD);
  assert.ok(frontX + frontW < rearX, 'a roof pillar separates the two panes');
  assert.equal(frontY, rearY);
  assert.equal(frontD, rearD);
});
