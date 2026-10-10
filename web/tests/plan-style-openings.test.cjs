'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadPlanStyle } = require('./helpers/plan-style-loader.cjs');

function styledContext() {
  const calls = [];
  const target = { calls };
  return new Proxy(target, {
    get(object, name) {
      if (name in object) return object[name];
      return (...args) => calls.push({
        name, args, fillStyle: object.fillStyle, strokeStyle: object.strokeStyle,
        lineWidth: object.lineWidth, lineCap: object.lineCap,
      });
    },
  });
}

const toScreen = ({ x, y }) => ({ x: x * 20, y: y * 20 });
const wall = (id, ax, ay, bx, by) => ({
  id, a: { x: ax, y: ay }, b: { x: bx, y: by }, thickness_m: 0.2,
});

test('professional door has a bounded gap, jambs, threshold, leaf, hinge and swing arc', () => {
  const segment = wall('door-wall', 1, 1, 5, 1);
  const opening = { id: 'door', type: 'door', wall_id: segment.id,
    offset_m: 1, width_m: 0.9 };
  const before = structuredClone({ segment, opening });
  const ctx = styledContext();
  loadPlanStyle().drawOpenings(ctx, [opening], [segment], toScreen, 20);

  const strokes = ctx.calls.filter((call) => call.name === 'stroke');
  assert.ok(strokes.some((call) => call.strokeStyle === '#ffffff' && call.lineWidth === 5.5));
  assert.equal(strokes.filter((call) => call.strokeStyle === '#30383b' && call.lineWidth === 1.2).length, 2);
  assert.ok(strokes.some((call) => call.strokeStyle === '#a6adae' && call.lineWidth === 0.8));
  assert.ok(strokes.some((call) => call.strokeStyle === '#25343b' && call.lineWidth === 1.5));
  const arcs = ctx.calls.filter((call) => call.name === 'arc');
  assert.ok(arcs.some((call) => Math.abs(call.args[2] - 18) < 1e-9));
  assert.ok(arcs.some((call) => call.args[2] === 1.5));
  assert.ok(ctx.calls.every((call) => call.args.every((value) =>
    typeof value !== 'number' || Number.isFinite(value))));
  assert.equal(ctx.calls.filter((call) => call.name === 'save').length, 1);
  assert.equal(ctx.calls.filter((call) => call.name === 'restore').length, 1);
  assert.deepEqual({ segment, opening }, before);
});

test('wide window has reveal, glazing, two frame rails, jambs and one readable mullion', () => {
  const segment = wall('window-wall', 1, 1, 5, 1);
  const opening = { id: 'window', type: 'window', wall_id: segment.id,
    offset_m: 1, width_m: 1.8 };
  const ctx = styledContext();
  loadPlanStyle().drawOpenings(ctx, [opening], [segment], toScreen, 20);

  assert.ok(ctx.calls.some((call) => call.name === 'fill' && call.fillStyle === '#dcebf2'));
  const strokes = ctx.calls.filter((call) => call.name === 'stroke');
  assert.equal(strokes.filter((call) => call.strokeStyle === '#596466' && call.lineWidth === 1).length, 2);
  assert.equal(strokes.filter((call) => call.strokeStyle === '#30383b' && call.lineWidth === 1.2).length, 2);
  assert.equal(strokes.filter((call) => call.strokeStyle === '#739eb5' && call.lineWidth === 1.2).length, 1);
  assert.equal(strokes.filter((call) => call.strokeStyle === '#596466' && call.lineWidth === 0.8).length, 1);
});

test('compact window omits its mullion and invalid geometry paints nothing', () => {
  const style = loadPlanStyle();
  const segment = wall('short', 0, 0, 2, 0);
  const compact = styledContext();
  style.drawOpenings(compact, [{ id: 'small', type: 'window', wall_id: 'short',
    offset_m: 0.5, width_m: 0.5 }], [segment], toScreen, 20);
  assert.equal(compact.calls.filter((call) => call.name === 'stroke' &&
    call.strokeStyle === '#596466' && call.lineWidth === 0.8).length, 0);

  for (const opening of [
    { id: 'missing', type: 'door', wall_id: 'absent', offset_m: 0, width_m: 0.9 },
    { id: 'nan', type: 'window', wall_id: 'short', offset_m: Number.NaN, width_m: 1 },
    { id: 'zero', type: 'door', wall_id: 'short', offset_m: 0, width_m: 0 },
  ]) {
    const ctx = styledContext();
    style.drawOpenings(ctx, [opening], [segment], toScreen, 20);
    assert.deepEqual(ctx.calls, []);
  }
});

test('vertical, reversed and clipped openings stay on their visible wall segment', () => {
  const style = loadPlanStyle();
  for (const segment of [wall('vertical', 1, 1, 1, 5), wall('reversed', 5, 1, 1, 1)]) {
    const opening = { id: 'bounded', type: 'door', wall_id: segment.id,
      offset_m: 3.5, width_m: 1 };
    const ctx = styledContext();
    style.drawOpenings(ctx, [opening], [segment], toScreen, 20);
    const swing = ctx.calls.find((call) => call.name === 'arc' && call.args[2] > 2);
    assert.equal(swing.args[2], 10);
    assert.equal(ctx.calls.filter((call) => call.name === 'save').length, 1);
    assert.equal(ctx.calls.filter((call) => call.name === 'restore').length, 1);
    assert.ok(ctx.calls.every((call) => call.args.every((value) =>
      typeof value !== 'number' || Number.isFinite(value))));
  }
});

test('invalid wall thickness falls back to a finite architectural thickness', () => {
  const style = loadPlanStyle();
  for (const thickness of [Number.NaN, Number.POSITIVE_INFINITY, 'bad', -1]) {
    const segment = { ...wall('w', 0, 0, 4, 0), thickness_m: thickness };
    const ctx = styledContext();
    style.drawOpenings(ctx, [{ id: 'window', type: 'window', wall_id: 'w',
      offset_m: 1, width_m: 1 }], [segment], toScreen, 20);
    assert.ok(ctx.calls.length > 0);
    assert.ok(ctx.calls.every((call) => call.args.every((value) =>
      typeof value !== 'number' || Number.isFinite(value))), String(thickness));
  }
});

test('four explicit door semantics place hinges and leaves in four distinct quadrants', () => {
  const style = loadPlanStyle();
  const segment = wall('semantic', 0, 0, 4, 0);
  const expected = new Map([
    ['start/positive', [20, 20]], ['end/positive', [40, 20]],
    ['start/negative', [20, -20]], ['end/negative', [40, -20]],
  ]);
  const endpoints = new Set();
  for (const [key, target] of expected) {
    const [hinge, swing] = key.split('/');
    const opening = { id: key, type: 'door', wall_id: 'semantic',
      offset_m: 1, width_m: 1, hinge, swing };
    const before = structuredClone(opening);
    const ctx = styledContext();
    style.drawOpenings(ctx, [opening], [segment], toScreen, 20);
    const leafEnd = ctx.calls.find((call) => call.name === 'lineTo' &&
      call.strokeStyle === '#25343b' && call.lineWidth === 1.5);
    assert.deepEqual(leafEnd.args, target);
    endpoints.add(leafEnd.args.join(','));
    assert.equal(ctx.calls.filter((call) => call.name === 'save').length, 1);
    assert.equal(ctx.calls.filter((call) => call.name === 'restore').length, 1);
    assert.deepEqual(opening, before);
  }
  assert.equal(endpoints.size, 4);
});

test('explicit door semantics follow vertical and reversed wall orientation', () => {
  const style = loadPlanStyle();
  const cases = [
    {
      segment: wall('vertical-semantic', 0, 0, 0, 4),
      hinge: [0, 20],
      target: [-20, 20],
    },
    {
      segment: wall('reversed-semantic', 4, 0, 0, 0),
      hinge: [60, 0],
      target: [60, -20],
    },
  ];
  for (const { segment, hinge, target } of cases) {
    const ctx = styledContext();
    style.drawOpenings(ctx, [{ id: 'door', type: 'door', wall_id: segment.id,
      offset_m: 1, width_m: 1, hinge: 'start', swing: 'positive' }], [segment], toScreen, 20);
    const leafEndIndex = ctx.calls.findIndex((call) => call.name === 'lineTo' &&
      call.strokeStyle === '#25343b' && call.lineWidth === 1.5);
    assert.notEqual(leafEndIndex, -1);
    assert.deepEqual(ctx.calls[leafEndIndex - 1].args, hinge);
    assert.deepEqual(ctx.calls[leafEndIndex].args, target);
  }
});

test('a wide explicit garage opening has jambs and threshold but no hinged leaf', () => {
  const segment = wall('garage', 0, 0, 5, 0);
  const ctx = styledContext();
  loadPlanStyle().drawOpenings(ctx, [{ id: 'garage-door', type: 'door', wall_id: 'garage',
    offset_m: 1, width_m: 2.4, hinge: 'start', swing: 'positive' }], [segment], toScreen, 20);
  assert.equal(ctx.calls.filter((call) => call.name === 'arc').length, 0);
  assert.ok(ctx.calls.some((call) => call.name === 'stroke' &&
    call.strokeStyle === '#a6adae' && call.lineWidth === 0.8));
});

