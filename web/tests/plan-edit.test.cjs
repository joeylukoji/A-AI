'use strict';
// node --test web/tests
const test = require('node:test');
const assert = require('node:assert');
const E = require('../static/js/plan-edit.js');

const rect = (x0, y0, x1, y1) => [{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }];
const wall = (id, ax, ay, bx, by) => ({ id, a: { x: ax, y: ay }, b: { x: bx, y: by }, thickness_m: 0.15 });
let n = 0;
const uid = (p) => `${p}new${++n}`;

// Maison 12 x 8 : quatre pièces à gauche (8 x 8), une bande libre à droite (x 8 -> 12).
function house() {
  return {
    floor: { bounds: { width: 12, depth: 8 } },
    rooms: [
      { id: 'a', type: 'bedroom', name: 'Chambre', polygon: rect(0, 0, 4, 4) },
      { id: 'b', type: 'kitchen', name: 'Cuisine', polygon: rect(4, 0, 8, 4) },
      { id: 'c', type: 'living', name: 'Séjour', polygon: rect(0, 4, 4, 8) },
      { id: 'd', type: 'bathroom', name: 'SDB', polygon: rect(4, 4, 8, 8) },
    ],
    walls: [
      wall('w_outer_1', 0, 0, 12, 0), wall('w_outer_2', 12, 0, 12, 8),
      wall('w_outer_3', 12, 8, 0, 8), wall('w_outer_4', 0, 8, 0, 0),
      wall('w1', 4, 0, 4, 4), wall('w2', 4, 4, 4, 8), wall('w3', 0, 4, 4, 4), wall('w4', 4, 4, 8, 4),
      wall('w5', 8, 0, 8, 4), wall('w6', 8, 4, 8, 8),
    ],
    openings: [
      { id: 'o1', wall_id: 'w6', type: 'door', offset_m: 1, width_m: 0.9 },
      { id: 'o2', wall_id: 'w2', type: 'door', offset_m: 1, width_m: 0.9 },
    ],
    furniture: [
      { id: 'f1', room_id: 'd', position: { x: 6, y: 6 }, catalog_id: 'bathtub' },
      { id: 'f2', room_id: 'a', position: { x: 1, y: 1 }, catalog_id: 'bed.double' },
      { id: 'f3', room_id: 'c', position: { x: 2, y: 7 }, catalog_id: 'sofa.2seat' },
    ],
  };
}
const findWall = (plan, id) => plan.walls.find((w) => w.id === id);
const hasWallFor = (plan, a, b) => plan.walls.some((w) => E.sameEdge(a, b, w.a, w.b));

test('overlap and bounds', () => {
  const p = house();
  assert.strictEqual(E.maxOverlap(p, 3, 0, 0).area, 0);           // voisines qui se touchent : pas de chevauchement
  assert.ok(E.maxOverlap(p, 3, -1, 0).area > 0);                  // D glissée sur C
  assert.ok(E.canMove(p, 3, 4, 0));                               // vers la bande libre
  assert.ok(!E.canMove(p, 3, 5, 0));                              // sort de la maison
  assert.ok(!E.canMove(p, 3, -1, 0));                             // chevauche
});

test('moving a room keeps the walls it shares with its neighbours in place', () => {
  const p = house();
  E.translateRoom(p, 3, 4, 0, uid);
  assert.deepStrictEqual(findWall(p, 'w2'), wall('w2', 4, 4, 4, 8));   // commun avec C
  assert.deepStrictEqual(findWall(p, 'w4'), wall('w4', 4, 4, 8, 4));   // commun avec B
  assert.deepStrictEqual(findWall(p, 'w_outer_3'), wall('w_outer_3', 12, 8, 0, 8));
});

test('the moved room gets a wall on every edge and its own wall travels with its door', () => {
  const p = house();
  E.translateRoom(p, 3, 4, 0, uid);
  const poly = p.rooms[3].polygon;
  poly.forEach((a, i) => assert.ok(hasWallFor(p, a, poly[(i + 1) % 4]), `arête ${i} sans mur`));
  assert.deepStrictEqual(findWall(p, 'w6').a, { x: 12, y: 4 });        // mur propre à D : il suit
  assert.strictEqual(p.openings[0].wall_id, 'w6');                      // sa porte aussi
  assert.deepStrictEqual(p.rooms[3].polygon[0], { x: 8, y: 4 });
});

test('furniture follows the moved room and only that room', () => {
  const p = house();
  E.translateRoom(p, 3, 4, 0, uid);
  assert.deepStrictEqual(p.furniture[0].position, { x: 10, y: 6 });
  assert.deepStrictEqual(p.furniture[1].position, { x: 1, y: 1 });
});

test('neighbouring rooms are untouched by a move', () => {
  const p = house();
  const before = JSON.stringify(p.rooms.slice(0, 3));
  E.translateRoom(p, 3, 4, 0, uid);
  assert.strictEqual(JSON.stringify(p.rooms.slice(0, 3)), before);
});

test('snap pulls the room onto a neighbour edge within tolerance, not beyond', () => {
  const p = house();
  const near = E.snapMove(p, 3, 3.85, 0);          // bord droit à 11,85 : à 0,15 du bord de la maison (12)
  assert.ok(Math.abs(near.dx - 4) < 1e-9);
  const far = E.snapMove(p, 3, 3.5, 0, 0.25);      // à 0,5 de tout bord
  assert.ok(Math.abs(far.dx - 3.5) < 1e-9);
});

test('snap also aligns on a neighbouring room edge', () => {
  const p = house();
  const s = E.snapMove(p, 3, 0.1, -3.9);           // D remonte contre B : son haut (0,1) vient à y = 0 ou 4
  assert.ok(Math.abs(s.dy - -4) < 1e-9);
});

test('swapping two rooms exchanges their cells and leaves walls and doors alone', () => {
  const p = house();
  const walls = JSON.stringify(p.walls);
  const openings = JSON.stringify(p.openings);
  const before = [p.rooms[0].polygon, p.rooms[2].polygon];
  E.swapRooms(p, 0, 2);
  assert.deepStrictEqual(p.rooms[0].polygon, before[1]);
  assert.deepStrictEqual(p.rooms[2].polygon, before[0]);
  assert.strictEqual(JSON.stringify(p.walls), walls);
  assert.strictEqual(JSON.stringify(p.openings), openings);
});

test('swap keeps the tiling: same total area, no overlap', () => {
  const p = house();
  const total = () => p.rooms.reduce((s, r) => s + E.polyArea(r.polygon), 0);
  const area = total();
  E.swapRooms(p, 1, 3);
  assert.ok(Math.abs(total() - area) < 1e-9);
  p.rooms.forEach((_, i) => assert.ok(E.maxOverlap(p, i, 0, 0).area <= E.MIN_OVERLAP));
});

test('furniture follows its room through a swap and lands inside the new cell', () => {
  const p = house();
  E.swapRooms(p, 0, 2); // chambre (0..4, 0..4) <-> séjour (0..4, 4..8)
  const bed = p.furniture.find((f) => f.id === 'f2');
  const sofa = p.furniture.find((f) => f.id === 'f3');
  assert.ok(bed.position.y >= 4 && bed.position.y <= 8);   // le lit est descendu dans la case du bas
  assert.ok(sofa.position.y >= 0 && sofa.position.y <= 4); // le canapé est monté
});

test('swap between cells of different sizes keeps furniture inside the destination', () => {
  const p = house();
  p.rooms[1].polygon = rect(4, 0, 8, 2);          // B plus petite
  p.furniture.push({ id: 'f9', room_id: 'a', position: { x: 3.9, y: 3.9 }, catalog_id: 'wardrobe' });
  p.furniture.push({ id: 'f10', room_id: 'a', position: { x: 0.1, y: 0.1 }, catalog_id: 'nightstand' });
  E.swapRooms(p, 0, 1);
  const low = p.furniture.find((f) => f.id === 'f10');
  assert.ok(Math.abs(low.position.x - 4.3) < 1e-9 && Math.abs(low.position.y - 0.3) < 1e-9, JSON.stringify(low)); // ramené à 30 cm des murs
  const it = p.furniture.find((f) => f.id === 'f9');
  assert.ok(it.position.x >= 4 && it.position.x <= 8 && it.position.y >= 0 && it.position.y <= 2, JSON.stringify(it));
  // à 30 cm au moins des murs de la case d'arrivée
  assert.ok(it.position.x <= 7.7 + 1e-9 && it.position.y <= 1.7 + 1e-9, JSON.stringify(it));
});

test('an exterior wall is never dragged along, even when it coincides exactly with a room edge', () => {
  const p = {
    floor: { bounds: { width: 8, depth: 4 } },
    rooms: [{ id: 'a', type: 'living', name: 'Séjour', polygon: rect(0, 0, 8, 4) }],
    walls: [wall('w_outer_1', 0, 0, 8, 0), wall('w_outer_2', 8, 0, 8, 4), wall('w_outer_3', 8, 4, 0, 4), wall('w_outer_4', 0, 4, 0, 0)],
    openings: [], furniture: [],
  };
  const outer = JSON.stringify(p.walls);
  E.translateRoom(p, 0, 0, 1, uid);
  assert.strictEqual(JSON.stringify(p.walls.slice(0, 4)), outer);
  assert.ok(p.walls.length > 4);            // la pièce reçoit ses propres murs à sa nouvelle place
});

test('resolveDrop: free space moves, overlap over a room swaps, nowhere valid cancels', () => {
  const p = house();
  assert.strictEqual(E.resolveDrop(p, 3, 4, 0, { x: 10, y: 6 }).action, 'move');
  const onto = E.resolveDrop(p, 3, -3, 0, { x: 1, y: 6 });        // déposée sur le séjour
  assert.deepStrictEqual([onto.action, onto.target], ['swap', 2]);
  assert.strictEqual(E.resolveDrop(p, 3, 0, 0, { x: 6, y: 6 }).action, 'cancel'); // pas bougé
  assert.strictEqual(E.resolveDrop(p, 3, 9, 0, { x: 14, y: 6 }).action, 'cancel'); // hors maison, pas sur une pièce
});

test('resolveDrop prefers a clean move over a swap', () => {
  const p = house();
  const r = E.resolveDrop(p, 3, 4, 0, { x: 10, y: 6 });
  assert.deepStrictEqual([r.action, r.target], ['move', -1]);
});

test('roomAt ignores the excluded room', () => {
  const p = house();
  assert.strictEqual(E.roomAt(p, { x: 6, y: 6 }, -1), 3);
  assert.strictEqual(E.roomAt(p, { x: 6, y: 6 }, 3), -1);
});

test('a wall between two hallway segments is reported as open, others are not', () => {
  const p = {
    floor: { bounds: { width: 8, depth: 8 } },
    rooms: [
      { id: 'h1', type: 'hallway', polygon: rect(0, 4, 4, 8) },
      { id: 'h2', type: 'hallway', polygon: rect(4, 4, 8, 8) },
      { id: 'b', type: 'bedroom', polygon: rect(0, 0, 8, 4) },
    ],
    walls: [
      wall('w_outer_1', 0, 0, 8, 0), wall('w_outer_2', 8, 0, 8, 8),
      wall('hh', 4, 4, 4, 8),        // entre deux segments de couloir
      wall('hb1', 0, 4, 4, 4),       // couloir / chambre
      wall('hb2', 4, 4, 8, 4),
    ],
  };
  const open = E.hallwayOnlyWalls(p);
  assert.deepStrictEqual([...open], ['hh']);
});

test('an exterior wall and a lone hallway edge are never reported as open', () => {
  const p = {
    floor: { bounds: { width: 8, depth: 8 } },
    rooms: [{ id: 'h1', type: 'hallway', polygon: rect(0, 0, 4, 4) }, { id: 'h2', type: 'hallway', polygon: rect(0, 0, 4, 4) }],
    walls: [wall('w_outer_1', 0, 0, 4, 0), wall('lone', 4, 0, 4, 4)],
  };
  // 'lone' est une arête commune aux deux polygones (identiques) : c'est bien un mur de couloir seul
  assert.ok(E.hallwayOnlyWalls(p).has('lone'));
  assert.ok(!E.hallwayOnlyWalls(p).has('w_outer_1'));
  const single = { rooms: [{ id: 'h', type: 'hallway', polygon: rect(0, 0, 4, 4) }], walls: [wall('e', 4, 0, 4, 4)] };
  assert.strictEqual(E.hallwayOnlyWalls(single).size, 0);
});

test('a hallway edge shared with a room of another type keeps its wall', () => {
  const p = {
    rooms: [
      { id: 'h1', type: 'hallway', polygon: rect(0, 0, 4, 4) },
      { id: 'h2', type: 'hallway', polygon: rect(0, 0, 4, 4) },
      { id: 'k', type: 'kitchen', polygon: rect(4, 0, 8, 4) },
    ],
    walls: [wall('hk', 4, 0, 4, 4)],
  };
  assert.strictEqual(E.hallwayOnlyWalls(p).size, 0);
});

test('door swing cycles through four explicit states without changing other fields', () => {
  const door = { id: 'o', type: 'door', wall_id: 'w', offset_m: 1, width_m: 0.9 };
  const expected = [
    ['end', 'positive'], ['end', 'negative'], ['start', 'negative'], ['start', 'positive'],
  ];
  for (const [hinge, swing] of expected) {
    assert.deepStrictEqual(E.cycleDoorSwing(door), { hinge, swing });
    assert.strictEqual(door.hinge, hinge);
    assert.strictEqual(door.swing, swing);
    assert.strictEqual(door.wall_id, 'w');
  }
  const window = { id: 'win', type: 'window' };
  assert.strictEqual(E.cycleDoorSwing(window), null);
  assert.deepStrictEqual(window, { id: 'win', type: 'window' });
});
