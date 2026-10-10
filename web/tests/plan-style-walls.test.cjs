'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadPlanStyle: loadStyle } = require('./helpers/plan-style-loader.cjs');

function recordingContext() {
  const calls = [];
  return new Proxy({ calls }, {
    get(target, name) {
      if (name in target) return target[name];
      return (...args) => calls.push([name, ...args]);
    },
  });
}

function styledContext() {
  const calls = [];
  return new Proxy({ calls }, {
    get(target, name) {
      if (name in target) return target[name];
      return (...args) => calls.push({ name, args, fillStyle: target.fillStyle,
        strokeStyle: target.strokeStyle, lineWidth: target.lineWidth });
    },
  });
}

const toScreen = ({ x, y }) => ({ x: x * 20, y: y * 20 });
const wall = (id, ax, ay, bx, by) => ({
  id, a: { x: ax, y: ay }, b: { x: bx, y: by }, thickness_m: 0.2,
});

test('walls close horizontal, vertical, reversed and T junctions without data mutation', () => {
  const walls = [
    wall('forward', 1, 1, 5, 1), wall('reverse', 5, 1, 1, 1),
    wall('vertical', 3, 1, 3, 4), wall('stem', 3, 3, 5, 3),
  ];
  const before = JSON.stringify(walls);
  const ctx = recordingContext();
  loadStyle().drawWalls(ctx, walls, toScreen, 20);
  assert.deepEqual(ctx.calls.slice(0, 8), [
    ['save'], ['beginPath'], ['moveTo', 18, 22], ['lineTo', 102, 22],
    ['lineTo', 102, 18], ['lineTo', 18, 18], ['closePath'], ['fill'],
  ]);
  assert.deepEqual(ctx.calls.slice(8, 15), [
    ['beginPath'], ['moveTo', 102, 18], ['lineTo', 18, 18],
    ['lineTo', 18, 22], ['lineTo', 102, 22], ['closePath'], ['fill'],
  ]);
  assert.deepEqual(ctx.calls.slice(15, 22), [
    ['beginPath'], ['moveTo', 58, 18], ['lineTo', 58, 82],
    ['lineTo', 62, 82], ['lineTo', 62, 18], ['closePath'], ['fill'],
  ]);
  assert.deepEqual(ctx.calls.slice(22, 29), [
    ['beginPath'], ['moveTo', 58, 62], ['lineTo', 102, 62],
    ['lineTo', 102, 58], ['lineTo', 58, 58], ['closePath'], ['fill'],
  ]);
  assert.equal(ctx.calls.filter(([name]) => name === 'fill').length, 4);
  assert.equal(ctx.calls.filter(([name]) => name === 'save').length, 1);
  assert.equal(ctx.calls.filter(([name]) => name === 'restore').length, 1);
  assert.equal(JSON.stringify(walls), before);
});

test('reversed wall still locates door and window on stored offsets', () => {
  const walls = [wall('reverse', 5, 1, 1, 1)];
  const door = { id: 'door', type: 'door', wall_id: 'reverse', offset_m: 1, width_m: 0.9 };
  const window = { id: 'window', type: 'window', wall_id: 'reverse', offset_m: 2, width_m: 1 };
  const before = JSON.stringify({ walls, door, window });
  const style = loadStyle();
  const doorCtx = recordingContext();
  style.drawOpenings(doorCtx, [door], walls, toScreen, 20);
  assert.deepEqual(doorCtx.calls.slice(0, 5), [
    ['save'], ['beginPath'], ['moveTo', 80, 20], ['lineTo', 62, 20], ['stroke'],
  ]);
  const arc = doorCtx.calls.find(([name]) => name === 'arc');
  assert.deepEqual(arc, ['arc', 80, 20, 18, Math.PI, Math.PI * 1.5]);
  assert.equal(doorCtx.calls.at(-1)[0], 'restore');
  const windowCtx = recordingContext();
  style.drawOpenings(windowCtx, [window], walls, toScreen, 20);
  assert.deepEqual(windowCtx.calls.slice(0, 5), [
    ['save'], ['beginPath'], ['moveTo', 60, 20], ['lineTo', 40, 20], ['stroke'],
  ]);
  assert.equal(windowCtx.calls.filter(([name]) => name === 'stroke').length, 7);
  assert.equal(windowCtx.calls.at(-1)[0], 'restore');
  const missing = recordingContext();
  style.drawOpenings(missing, [{ ...door, wall_id: 'absent' }], walls, toScreen, 20);
  assert.equal(missing.calls.length, 0);
  assert.equal(JSON.stringify({ walls, door, window }), before);
});

test('a south door does not fabricate an entrance step or arrow', () => {
  const style = loadStyle();
  const walls = [wall('w_outer_3', 8, 4, 0, 4)];
  const door = { id: 'o1', type: 'door', wall_id: 'w_outer_3', offset_m: 2, width_m: 0.9 };
  const before = JSON.stringify({ walls, door });
  const withSouthDoor = recordingContext();
  style.drawPorch(withSouthDoor, [door], walls, 4, toScreen);
  assert.equal(withSouthDoor.calls.length, 0);
  const opening = recordingContext();
  style.drawOpenings(opening, [door], walls, toScreen, 20);
  assert.deepEqual(opening.calls.slice(0, 5), [
    ['save'], ['beginPath'], ['moveTo', 120, 80], ['lineTo', 102, 80], ['stroke'],
  ]);
  assert.deepEqual(opening.calls.find(([name]) => name === 'arc'),
    ['arc', 120, 80, 18, Math.PI, Math.PI * 1.5]);
  assert.equal(opening.calls.filter(([name]) => name === 'stroke').length, 7);
  const noSouthDoor = recordingContext();
  style.drawPorch(noSouthDoor, [{ ...door, wall_id: 'other' }], walls, 4, toScreen);
  assert.equal(noSouthDoor.calls.length, 0);
  assert.equal(JSON.stringify({ walls, door }), before);
});

test('a clipped door arc matches its visible gap and never extends beyond the wall', () => {
  const style = loadStyle();
  for (const segment of [wall('forward', 1, 1, 5, 1), wall('reverse', 5, 1, 1, 1)]) {
    const opening = { id: 'clipped', type: 'door', wall_id: segment.id,
      offset_m: 3.5, width_m: 1 };
    const before = JSON.stringify({ segment, opening });
    const ctx = recordingContext();
    style.drawOpenings(ctx, [opening], [segment], toScreen, 20);
    const startX = segment.id === 'forward' ? 90 : 30;
    const endX = segment.id === 'forward' ? 100 : 20;
    assert.deepEqual(ctx.calls.slice(0, 5), [
      ['save'], ['beginPath'], ['moveTo', startX, 20], ['lineTo', endX, 20], ['stroke'],
    ]);
    assert.equal(ctx.calls.find(([name]) => name === 'arc')[3], 10);
    const battantEnd = ctx.calls.filter(([name]) => name === 'lineTo').at(-1);
    assert.ok(Math.abs(battantEnd[1] - startX) < 1e-9);
    assert.ok(Math.abs(battantEnd[2] - (segment.id === 'forward' ? 30 : 10)) < 1e-9);
    assert.equal(JSON.stringify({ segment, opening }), before);
  }
  const atStart = recordingContext();
  style.drawOpenings(atStart, [{ id: 'start', type: 'door', wall_id: 'forward',
    offset_m: -0.5, width_m: 1 }], [wall('forward', 1, 1, 5, 1)], toScreen, 20);
  assert.deepEqual(atStart.calls.slice(0, 5), [
    ['save'], ['beginPath'], ['moveTo', 20, 20], ['lineTo', 30, 20], ['stroke'],
  ]);
  assert.equal(atStart.calls.find(([name]) => name === 'arc')[3], 10);
});

test('invisible or invalid openings do not draw a phantom symbol', () => {
  const style = loadStyle();
  const segment = wall('w', 1, 1, 5, 1);
  for (const opening of [
    { type: 'door', offset_m: 4, width_m: 0.9 },
    { type: 'window', offset_m: 5, width_m: 1 },
    { type: 'door', offset_m: 1, width_m: 0 },
    { type: 'window', offset_m: 1, width_m: -1 },
    { type: 'door', offset_m: Number.NaN, width_m: 1 },
    { type: 'window', offset_m: 1, width_m: Number.POSITIVE_INFINITY },
    { type: 'window', offset_m: 'bad', width_m: 1 },
    { type: 'vent', offset_m: 1, width_m: 1 },
  ]) {
    const item = { id: 'candidate', wall_id: 'w', ...opening };
    const before = structuredClone({ segment, item });
    const ctx = recordingContext();
    style.drawOpenings(ctx, [item], [segment], toScreen, 20);
    assert.deepEqual(ctx.calls, [], JSON.stringify(opening));
    assert.deepEqual({ segment, item }, before);
  }
  const zeroLength = wall('zero', 1, 1, 1, 1);
  const zeroCtx = recordingContext();
  style.drawOpenings(zeroCtx, [{ id: 'z', type: 'door', wall_id: 'zero',
    offset_m: 0, width_m: 0.9 }], [zeroLength], toScreen, 20);
  assert.deepEqual(zeroCtx.calls, []);
});

test('window pane and end jambs follow horizontal, reversed and vertical walls', () => {
  const style = loadStyle();
  for (const segment of [wall('forward', 1, 1, 5, 1),
    wall('reverse', 5, 1, 1, 1), wall('vertical', 1, 1, 1, 5)]) {
    const opening = { id: 'pane', type: 'window', wall_id: segment.id,
      offset_m: 1, width_m: 1 };
    const before = structuredClone({ segment, opening });
    const ctx = styledContext();
    style.drawOpenings(ctx, [opening], [segment], toScreen, 20);
    const pane = ctx.calls.find((call) => call.name === 'fill' && call.fillStyle === '#dcebf2');
    assert.ok(pane, segment.id);
    const paneIndex = ctx.calls.indexOf(pane);
    const panePath = ctx.calls.slice(paneIndex - 6, paneIndex);
    assert.deepEqual(panePath.map((call) => call.name),
      ['beginPath', 'moveTo', 'lineTo', 'lineTo', 'lineTo', 'closePath']);
    assert.equal(ctx.calls.filter((call) => call.name === 'stroke').length, 7);
    const jambMoves = ctx.calls.filter((call) => call.name === 'moveTo' &&
      call.strokeStyle === '#30383b' && call.lineWidth === 1.2);
    const jambLines = ctx.calls.filter((call) => call.name === 'lineTo' &&
      call.strokeStyle === '#30383b' && call.lineWidth === 1.2);
    const endpoints = segment.id === 'forward' ? [[40, 20], [60, 20]]
      : segment.id === 'reverse' ? [[80, 20], [60, 20]] : [[20, 40], [20, 60]];
    const [normalX, normalY] = segment.id === 'forward' ? [0, 1]
      : segment.id === 'reverse' ? [0, -1] : [-1, 0];
    const [start, end] = endpoints;
    const glassHalf = 0.96;
    const paneCorners = [
      [start[0] + normalX * glassHalf, start[1] + normalY * glassHalf],
      [end[0] + normalX * glassHalf, end[1] + normalY * glassHalf],
      [end[0] - normalX * glassHalf, end[1] - normalY * glassHalf],
      [start[0] - normalX * glassHalf, start[1] - normalY * glassHalf],
    ];
    for (let i = 0; i < 4; i++) {
      panePath[i + 1].args.forEach((coordinate, axis) =>
        assert.ok(Math.abs(coordinate - paneCorners[i][axis]) < 1e-9));
    }
    const railMoves = ctx.calls.filter((call) => call.name === 'moveTo' &&
      call.strokeStyle === '#596466' && call.lineWidth === 1);
    const railLines = ctx.calls.filter((call) => call.name === 'lineTo' &&
      call.strokeStyle === '#596466' && call.lineWidth === 1);
    for (let i = 0; i < 2; i++) {
      const side = i === 0 ? -1.12 : 1.12;
      for (const [call, point] of [[railMoves[i], start], [railLines[i], end]]) {
        assert.ok(Math.abs(call.args[0] - (point[0] + normalX * side)) < 1e-9);
        assert.ok(Math.abs(call.args[1] - (point[1] + normalY * side)) < 1e-9);
      }
    }
    for (let i = 0; i < 2; i++) {
      const [x, y] = endpoints[i];
      if (segment.id === 'vertical') {
        assert.deepEqual(jambMoves[i].args, [x + 2, y]);
        assert.deepEqual(jambLines[i].args, [x - 2, y]);
      } else {
        assert.equal(jambMoves[i].args[0], x);
        assert.equal(jambLines[i].args[0], x);
        assert.deepEqual([jambMoves[i].args[1], jambLines[i].args[1]].sort(), [18, 22]);
      }
    }
    assert.deepEqual({ segment, opening }, before);
  }
});

test('a window clipped by the wall end keeps pane and jambs inside the visible span', () => {
  const segment = wall('clipped', 1, 1, 5, 1);
  const ctx = styledContext();
  loadStyle().drawOpenings(ctx, [{ id: 'pane', type: 'window', wall_id: 'clipped',
    offset_m: 3.5, width_m: 1 }], [segment], toScreen, 20);
  const paneIndex = ctx.calls.findIndex((call) => call.name === 'fill'
    && call.fillStyle === '#dcebf2');
  assert.notEqual(paneIndex, -1);
  for (const call of ctx.calls.slice(paneIndex - 5, paneIndex - 1)) {
    assert.ok(call.args[0] >= 90 && call.args[0] <= 100);
  }
  const jambs = ctx.calls.filter((call) => call.name === 'moveTo' &&
    call.strokeStyle === '#30383b' && call.lineWidth === 1.2);
  assert.deepEqual(jambs.map((call) => call.args[0]), [90, 100]);
});

test('a tiny window keeps glazing and jambs but omits its unreadable mullion', () => {
  const style = loadStyle();
  const segment = wall('short-pane', 1, 1, 5, 1);
  const ctx = styledContext();
  style.drawOpenings(ctx, [{ id: 'tiny', type: 'window', wall_id: 'short-pane',
    offset_m: 1, width_m: 0.2 }], [segment], toScreen, 20);
  assert.equal(ctx.calls.filter((call) => call.name === 'fill' && call.fillStyle === '#dcebf2').length, 1);
  assert.equal(ctx.calls.filter((call) => call.name === 'stroke').length, 7);
  assert.equal(ctx.calls.filter((call) => call.name === 'stroke' &&
    call.strokeStyle === '#596466' && call.lineWidth === 0.8).length, 0);
});
