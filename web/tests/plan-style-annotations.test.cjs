'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadPlanStyle: loadStyle } = require('./helpers/plan-style-loader.cjs');

function recordingContext() {
  const calls = [];
  const target = {
    calls,
    letterSpacing: '',
    measureText(text) {
      const fontSize = Number(/([\d.]+)px/.exec(this.font || '')?.[1] || 11);
      const spacing = this.letterSpacing === '0.06em' ? fontSize * 0.06 : 0;
      return { width: text.length * fontSize * 0.56 + Math.max(0, text.length - 1) * spacing };
    },
    fillText(text, x, y) {
      calls.push(['fillText', text, x, y, this.font, this.measureText(text).width]);
    },
  };
  return new Proxy(target, {
    get(object, name) {
      if (name in object) return object[name];
      return (...args) => calls.push([name, ...args]);
    },
  });
}

function rectangle(x0, y0, x1, y1) {
  return [{ x: x0, y: y0 }, { x: x1, y: y0 },
    { x: x1, y: y1 }, { x: x0, y: y1 }];
}

const toScreen = ({ x, y }) => ({ x: x * 20, y: y * 20 });

test('facade dimensions, scale bar and room area retain formatting and balanced state', () => {
  const style = loadStyle();
  const dimensions = recordingContext();
  style.drawDimensions(dimensions, 12, 9, toScreen);
  assert.deepEqual(dimensions.calls.filter(([name]) => name === 'fillText').map((call) => call[1]),
    ['12,0 m', '9,0 m', '0', '1', '2 m']);
  assert.equal(dimensions.calls.filter(([name]) => name === 'save').length, 3);
  assert.equal(dimensions.calls.filter(([name]) => name === 'restore').length, 3);

  const room = { id: 'r1', type: 'bedroom', name: 'Chambre 1', polygon: rectangle(0, 0, 4, 3) };
  const before = JSON.stringify(room);
  const ctx = recordingContext();
  style.drawRoomLabels(ctx, [room], toScreen);
  assert.deepEqual(ctx.calls.filter(([name]) => name === 'fillText').map((call) => call[1]),
    ['CHAMBRE 1', '12,0 m²']);
  assert.equal(ctx.calls.filter(([name]) => name === 'save').length, 1);
  assert.equal(ctx.calls.filter(([name]) => name === 'restore').length, 1);
  assert.equal(style.polyArea(room.polygon), 12);
  assert.equal(JSON.stringify(room), before);
});

test('editor adds exact interior dimensions only to an orthogonal rectangular room', () => {
  const style = loadStyle();
  const room = { id: 'r1', type: 'bedroom', name: 'Chambre 1',
    polygon: rectangle(0, 0, 4, 3) };
  const before = structuredClone(room);
  const ctx = recordingContext();
  style.drawRoomLabels(ctx, [room], ({ x, y }) => ({ x: x * 40, y: y * 40 }), {
    furniture: [], dimensions: true,
  });
  assert.deepEqual(ctx.calls.filter(([name]) => name === 'fillText').map((call) => call[1]),
    ['CHAMBRE 1', '12,0 m²', '4,0 × 3,0 m']);
  assert.equal(style.roomDimensions(room.polygon), '4,0 × 3,0 m');
  assert.deepEqual(room, before);

  const irregular = [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 2 },
    { x: 2, y: 3 }, { x: 0, y: 2 }];
  assert.equal(style.roomDimensions(irregular), null);
  const concaveOrthogonal = [{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 2 },
    { x: 2, y: 2 }, { x: 2, y: 4 }, { x: 0, y: 4 }];
  assert.equal(style.roomDimensions(concaveOrthogonal), null);

  const hallway = { id: 'h', type: 'hallway', polygon: rectangle(0, 0, 4, 2) };
  const hallwayCtx = recordingContext();
  style.drawRoomLabels(hallwayCtx, [hallway], toScreen, { furniture: [], dimensions: true });
  assert.deepEqual(hallwayCtx.calls.filter(([name]) => name === 'fillText')
    .map((call) => call[1]), ['COULOIR']);
});

test('interior dimensions degrade to area then name when available space shrinks', () => {
  const style = loadStyle();
  const compact = { id: 'compact', type: 'bedroom', name: 'Chambre',
    polygon: rectangle(0, 0, 5, 3) };
  const compactCtx = recordingContext();
  style.drawRoomLabels(compactCtx, [compact], ({ x, y }) => ({ x: x * 12, y: y * 12 }), {
    furniture: [], dimensions: true,
  });
  assert.deepEqual(compactCtx.calls.filter(([name]) => name === 'fillText').map((call) => call[1]),
    ['CHAMBRE', '15,0 m²']);

  const occupied = { id: 'occupied', type: 'garage', polygon: rectangle(0, 0, 8, 6) };
  const occupiedCtx = recordingContext();
  style.drawRoomLabels(occupiedCtx, [occupied], toScreen, { dimensions: true, furniture: [{
    catalog_id: 'car.sedan', position: { x: 4, y: 2.4 }, size_m: { w: 8, d: 4.8 },
  }] });
  assert.deepEqual(occupiedCtx.calls.filter(([name]) => name === 'fillText').map((call) => call[1]),
    ['GARAGE']);
});

test('three-line dimensions move away from volumetric furniture and restore after errors', () => {
  const style = loadStyle();
  const room = { id: 'large', type: 'living', polygon: rectangle(0, 0, 8, 6) };
  const furniture = [{ catalog_id: 'table.dining', position: { x: 4, y: 3 },
    size_m: { w: 2, d: 1 }, rotation_deg: 0 }];
  const ctx = recordingContext();
  style.drawRoomLabels(ctx, [room], toScreen, { furniture, dimensions: true });
  const labels = ctx.calls.filter(([name]) => name === 'fillText');
  assert.deepEqual(labels.map((call) => call[1]), ['SÉJOUR', '48,0 m²', '8,0 × 6,0 m']);
  assert.ok(labels.every((call) => call[2] < 60 || call[2] > 100 || call[3] < 50 || call[3] > 70));

  const calls = [];
  const throwing = new Proxy({ calls }, {
    get(target, name) {
      if (name === 'measureText') return () => { throw new Error('measure failure'); };
      if (name in target) return target[name];
      return (...args) => calls.push([name, ...args]);
    },
  });
  assert.throws(() => style.drawRoomLabels(throwing, [room], toScreen), /measure failure/);
  assert.deepEqual(calls.filter(([name]) => name === 'save' || name === 'restore')
    .map(([name]) => name), ['save', 'restore']);
});

test('noArea and adjacent hallway grouping keep one name per continuous corridor', () => {
  const style = loadStyle();
  const rooms = [
    { id: 'h1', type: 'hallway', polygon: rectangle(0, 0, 3, 2) },
    { id: 'h2', type: 'hallway', polygon: rectangle(3, 0, 6, 2) },
    { id: 'b', type: 'bedroom', polygon: rectangle(0, 2, 6, 5) },
    { id: 'bad', type: 'bedroom', polygon: [] },
  ];
  const before = JSON.stringify(rooms);
  assert.equal(style.hallGroups(rooms).length, 1);
  const ctx = recordingContext();
  style.drawRoomLabels(ctx, rooms, toScreen, { noArea: true });
  assert.deepEqual(ctx.calls.filter(([name]) => name === 'fillText').map((call) => call[1]),
    ['COULOIR', 'CHAMBRE']);
  assert.equal(JSON.stringify(rooms), before);
});

test('tiny rooms omit unreadable labels while larger rooms keep fitting detail', () => {
  const style = loadStyle();
  for (const scenario of [
    { width: 1.5, depth: 1.5, pxPerMetre: 10, expected: [] },
    { width: 5, depth: 2, pxPerMetre: 12, expected: ['CHAMBRE 1'] },
    { width: 4.5, depth: 4, pxPerMetre: 12, expected: ['CHAMBRE 1', '18,0 m²'], expectedNameSize: 8 },
    { width: 5, depth: 4, pxPerMetre: 20, expected: ['CHAMBRE 1', '20,0 m²'] },
    { width: 5, depth: 4, pxPerMetre: 20, expected: ['CHAMBRE 1'], options: { noArea: true } },
  ]) {
    const room = { id: 'r', type: 'bedroom', name: 'Chambre 1',
      polygon: rectangle(0, 0, scenario.width, scenario.depth) };
    const before = JSON.stringify(room);
    const ctx = recordingContext();
    const scaled = ({ x, y }) => ({ x: x * scenario.pxPerMetre, y: y * scenario.pxPerMetre });
    style.drawRoomLabels(ctx, [room], scaled, scenario.options);
    const labels = ctx.calls.filter(([name]) => name === 'fillText');
    assert.deepEqual(labels.map((call) => call[1]), scenario.expected);
    const usableWidth = scenario.width * scenario.pxPerMetre - 8;
    assert.ok(labels.every((call) => call[5] <= usableWidth + 1e-6));
    assert.ok(labels.every((call) => {
      const fontSize = Number(/([\d.]+)px/.exec(call[4])[1]);
      return call[3] - fontSize / 2 >= 4 &&
        call[3] + fontSize / 2 <= scenario.depth * scenario.pxPerMetre - 4;
    }));
    if (scenario.expectedNameSize) {
      assert.equal(Number(/([\d.]+)px/.exec(labels[0][4])[1]), scenario.expectedNameSize);
    }
    assert.equal(JSON.stringify(room), before);
  }
});

test('asymmetric polygon uses space around its label anchor, not full box width', () => {
  const style = loadStyle();
  const room = { id: 'triangle', type: 'bedroom', name: 'Chambre 1', polygon: [
    { x: 0, y: 0 }, { x: 3.5, y: 0 }, { x: 0, y: 4 },
  ] };
  const ctx = recordingContext();
  style.drawRoomLabels(ctx, [room], toScreen);
  assert.deepEqual(ctx.calls.filter(([name]) => name === 'fillText'), []);
});

test('a connected hallway uses a segment that can fit its sole label', () => {
  const style = loadStyle();
  const rooms = [
    { id: 'narrow', type: 'hallway', polygon: rectangle(0, 0, 1.5, 6) },
    { id: 'wide', type: 'hallway', polygon: rectangle(1.5, 0, 4, 2) },
  ];
  const ctx = recordingContext();
  style.drawRoomLabels(ctx, rooms, toScreen);
  assert.deepEqual(ctx.calls.filter(([name]) => name === 'fillText').map((call) => call[1]), ['COULOIR']);
});

test('hallway selection ignores a physically ineligible segment at high zoom', () => {
  const style = loadStyle();
  const rooms = [
    { id: 'too-narrow', type: 'hallway', polygon: rectangle(0, 0, 0.8, 8) },
    { id: 'valid', type: 'hallway', polygon: rectangle(0.8, 0, 3.3, 2) },
  ];
  const ctx = recordingContext();
  const enlarged = ({ x, y }) => ({ x: x * 200, y: y * 200 });
  style.drawRoomLabels(ctx, rooms, enlarged);
  assert.deepEqual(ctx.calls.filter(([name]) => name === 'fillText').map((call) => call[1]), ['COULOIR']);
});

test('editor labels avoid furniture including rotated footprints without moving data', () => {
  const style = loadStyle();
  for (const rotation of [0, 90, 35]) {
    const room = { id: 'garage', type: 'garage', polygon: rectangle(0, 0, 10, 8) };
    const furniture = [{ catalog_id: 'car.sedan', room_id: 'garage',
      position: { x: 5, y: 4 }, size_m: { w: 4.2, d: 1.8 }, rotation_deg: rotation }];
    const before = JSON.stringify({ room, furniture });
    const ctx = recordingContext();
    style.drawRoomLabels(ctx, [room], toScreen, { furniture });
    const labels = ctx.calls.filter(([name]) => name === 'fillText');
    assert.equal(labels.length, 2, 'name and area fit in the remaining space');
    const angle = rotation * Math.PI / 180;
    const halfW = (Math.abs(Math.cos(angle)) * 4.2 + Math.abs(Math.sin(angle)) * 1.8) * 10;
    const halfH = (Math.abs(Math.sin(angle)) * 4.2 + Math.abs(Math.cos(angle)) * 1.8) * 10;
    for (const [, , x, y, font, width] of labels) {
      const height = Number(/([\d.]+)px/.exec(font)[1]);
      assert.ok(x + width / 2 < 100 - halfW || x - width / 2 > 100 + halfW ||
        y + height / 2 < 80 - halfH || y - height / 2 > 80 + halfH);
    }
    assert.equal(JSON.stringify({ room, furniture }), before);
  }
});

test('editor labels remain within a concave room and ignore rugs as obstacles', () => {
  const room = { id: 'l', type: 'bathroom', polygon: [
    { x: 0, y: 0 }, { x: 6, y: 0 }, { x: 6, y: 2 },
    { x: 2, y: 2 }, { x: 2, y: 6 }, { x: 0, y: 6 },
  ] };
  const ctx = recordingContext();
  loadStyle().drawRoomLabels(ctx, [room], toScreen, { furniture: [
    { catalog_id: 'rug.rect', position: { x: 3, y: 3 }, size_m: { w: 6, d: 6 } },
  ] });
  const labels = ctx.calls.filter(([name]) => name === 'fillText');
  assert.ok(labels.length >= 1);
  for (const [, , x, y, font, width] of labels) {
    const height = Number(/([\d.]+)px/.exec(font)[1]);
    assert.ok(x - width / 2 >= 0 && y - height / 2 >= 0);
    assert.ok(x + width / 2 <= 120 && y + height / 2 <= 120);
    assert.ok(x + width / 2 <= 40 || y + height / 2 <= 40,
      'the text rectangle must not cross the concave notch');
  }
});

test('a fully occupied room does not paint a label over furniture', () => {
  const room = { id: 'r', type: 'bedroom', polygon: rectangle(0, 0, 4, 4) };
  const ctx = recordingContext();
  loadStyle().drawRoomLabels(ctx, [room], toScreen, { furniture: [
    { catalog_id: 'bed.double', position: { x: 2, y: 2 }, size_m: { w: 4, d: 4 } },
  ] });
  assert.deepEqual(ctx.calls.filter(([name]) => name === 'fillText'), []);
});

test('editor keeps the name alone when only a narrow free strip remains', () => {
  const room = { id: 'r', type: 'garage', polygon: rectangle(0, 0, 8, 6) };
  const options = { furniture: [{ catalog_id: 'car.sedan',
    position: { x: 4, y: 2.4 }, size_m: { w: 8, d: 4.8 } }] };
  const first = recordingContext();
  const second = recordingContext();
  const style = loadStyle();
  style.drawRoomLabels(first, [room], toScreen, options);
  style.drawRoomLabels(second, [room], toScreen, options);
  const labels = first.calls.filter(([name]) => name === 'fillText');
  assert.deepEqual(labels.map((call) => call[1]), ['GARAGE']);
  assert.ok(labels[0][3] > 96);
  assert.deepEqual(second.calls.filter(([name]) => name === 'fillText'), labels);
});

test('editor retries another connected hallway segment when the largest is occupied', () => {
  const rooms = [
    { id: 'h1', type: 'hallway', polygon: rectangle(0, 0, 6, 2) },
    { id: 'h2', type: 'hallway', polygon: rectangle(6, 0, 10, 2) },
  ];
  const ctx = recordingContext();
  loadStyle().drawRoomLabels(ctx, rooms, toScreen, { furniture: [
    { catalog_id: 'wardrobe', position: { x: 3, y: 1 }, size_m: { w: 6, d: 2 } },
  ] });
  const labels = ctx.calls.filter(([name]) => name === 'fillText');
  assert.deepEqual(labels.map((call) => call[1]), ['COULOIR']);
  assert.ok(labels[0][2] > 120);
});

test('editor searches away from the initial anchor in an asymmetric room', () => {
  const room = { id: 'triangle', type: 'bedroom', name: 'Chambre 1', polygon: [
    { x: 0, y: 0 }, { x: 3.5, y: 0 }, { x: 0, y: 4 },
  ] };
  const ctx = recordingContext();
  loadStyle().drawRoomLabels(ctx, [room], toScreen, { furniture: [] });
  const labels = ctx.calls.filter(([name]) => name === 'fillText');
  assert.ok(labels.length > 0);
  for (const [, , x, y, font, width] of labels) {
    const height = Number(/([\d.]+)px/.exec(font)[1]);
    assert.ok((x + width / 2) / 70 + (y + height / 2) / 80 <= 1);
  }
});
