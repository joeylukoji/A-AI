'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadPlanStyle: loadStyle } = require('./helpers/plan-style-loader.cjs');

function recordingContext() {
  const calls = [];
  const ctx = { calls };
  for (const name of [
    'save', 'restore', 'beginPath', 'moveTo', 'lineTo', 'closePath',
    'clip', 'stroke',
  ]) {
    ctx[name] = (...args) => calls.push([name, ...args]);
  }
  ctx.fillRect = (...args) => calls.push(['fillRect', ctx.fillStyle, ...args]);
  return ctx;
}

const toScreen = (point) => ({ x: point.x * 20, y: point.y * 20 });
const concave = [
  { x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 1 },
  { x: 1, y: 1 }, { x: 1, y: 4 }, { x: 0, y: 4 },
];

function assertClippedOutline(ctx, polygon) {
  const clipIndex = ctx.calls.findIndex((call) => call[0] === 'clip');
  assert.ok(clipIndex >= 0);
  const expectedPath = [
    ['save'], ['beginPath'], ['moveTo', polygon[0].x * 20, polygon[0].y * 20],
    ...polygon.slice(1).map((point) => ['lineTo', point.x * 20, point.y * 20]),
    ['closePath'],
  ];
  assert.deepEqual(ctx.calls.slice(0, clipIndex), expectedPath);
  let depth = 0;
  for (const [name] of ctx.calls) {
    if (name === 'save') depth += 1;
    if (name === 'restore') depth -= 1;
    assert.ok(depth >= 0, 'restore without save');
  }
  assert.equal(depth, 0, 'unrestored canvas state');
}

for (const type of ['bedroom', 'office', 'living', 'hallway', 'kitchen', 'bathroom', 'garage', 'other']) {
  test(`${type} floor clips to a concave room without mutating it`, () => {
    const room = { type, polygon: structuredClone(concave) };
    const before = JSON.stringify(room);
    const ctx = recordingContext();
    loadStyle().drawFloor(ctx, room, toScreen);
    const names = ctx.calls.map((call) => call[0]);
    assertClippedOutline(ctx, room.polygon);
    assert.equal(names.filter((name) => name === 'clip').length, 1);
    assert.ok(names.includes('fillRect'));
    assert.equal(JSON.stringify(room), before);
  });
}

test('triangle uses its real outline, and a missing polygon draws nothing', () => {
  const style = loadStyle();
  const ctx = recordingContext();
  const triangle = concave.slice(0, 3);
  style.drawFloor(ctx, { type: 'living', polygon: triangle }, toScreen);
  assertClippedOutline(ctx, triangle);
  assert.equal(ctx.calls.filter((call) => call[0] === 'clip').length, 1);
  const empty = recordingContext();
  style.drawFloor(empty, { type: 'living', polygon: [] }, toScreen);
  assert.equal(empty.calls.length, 0);
});

test('drawFixtures retains the drawFloor contract used by thumbnails', () => {
  const style = loadStyle();
  const room = { type: 'kitchen', polygon: concave };
  const floor = recordingContext();
  const fixtures = recordingContext();
  style.drawFloor(floor, room, toScreen);
  style.drawFixtures(fixtures, room, toScreen);
  assert.deepEqual(fixtures.calls, floor.calls);
});

test('the legend color matches the base fill of each floor material', () => {
  const style = loadStyle();
  const normalize = (color) => color.replace(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i,
    (_, r, g, b) => `rgb(${parseInt(r, 16)}, ${parseInt(g, 16)}, ${parseInt(b, 16)})`);
  for (const type of [
    'bedroom', 'office', 'living', 'dining', 'hallway', 'kitchen',
    'bathroom', 'wc', 'laundry', 'garage', 'storage', 'other',
  ]) {
    const room = { type, polygon: concave };
    const ctx = recordingContext();
    style.drawFloor(ctx, room, toScreen);
    const firstFill = ctx.calls.find((call) => call[0] === 'fillRect');
    assert.equal(normalize(firstFill[1]), normalize(style.fill(room)), type);
  }
});
