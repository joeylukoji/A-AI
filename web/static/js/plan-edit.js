// Édition d'un PlanDocument : déplacer ou échanger des pièces sans casser le plan.
//
// Module pur (aucun accès au DOM), donc testable avec `node --test web/tests`.
//
// Pourquoi ce n'est pas un simple « translater les sommets » : un mur commun à deux pièces
// est UN mur. Le tirer avec la pièce déplacée déformait sa voisine (son polygone ne suivait
// plus le mur). Ici, les murs partagés restent en place et la pièce déplacée reçoit ses
// propres murs à sa nouvelle position ; seuls les murs qui n'appartenaient qu'à elle voyagent
// (avec leurs portes et fenêtres).
(function (root) {
  'use strict';

  const EPS = 0.06;      // coïncidence de sommets (m) : les plans sont sur une grille de 10 cm
  const MIN_OVERLAP = 0.05; // m² : en dessous, deux pièces qui se touchent ne se chevauchent pas

  const samePt = (a, b, eps) => Math.abs(a.x - b.x) < (eps || EPS) && Math.abs(a.y - b.y) < (eps || EPS);
  const sameEdge = (a, b, c, d) => (samePt(a, c) && samePt(b, d)) || (samePt(a, d) && samePt(b, c));

  function bboxOf(poly) {
    const xs = poly.map((p) => p.x);
    const ys = poly.map((p) => p.y);
    return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
  }

  function overlapArea(a, b) {
    const w = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0);
    const h = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
    return w > 0 && h > 0 ? w * h : 0;
  }

  function edgesOf(poly) {
    return poly.map((p, i) => [p, poly[(i + 1) % poly.length]]);
  }

  function bounds(plan) {
    const b = (plan.floor && plan.floor.bounds) || {};
    return { w: b.width || 12, d: b.depth || 10 };
  }

  function shifted(box, dx, dy) {
    return { x0: box.x0 + dx, y0: box.y0 + dy, x1: box.x1 + dx, y1: box.y1 + dy };
  }

  // Plus grand chevauchement de la pièce `ri` déplacée de (dx, dy) avec une autre pièce.
  function maxOverlap(plan, ri, dx, dy) {
    const mine = shifted(bboxOf(plan.rooms[ri].polygon), dx, dy);
    let best = { area: 0, index: -1 };
    plan.rooms.forEach((room, j) => {
      if (j === ri || (room.polygon || []).length < 3) return;
      const area = overlapArea(mine, bboxOf(room.polygon));
      if (area > best.area) best = { area, index: j };
    });
    return best;
  }

  // La pièce déplacée reste-t-elle dans l'emprise de la maison ?
  function insideHouse(plan, ri, dx, dy) {
    const { w, d } = bounds(plan);
    const b = shifted(bboxOf(plan.rooms[ri].polygon), dx, dy);
    return b.x0 >= -EPS && b.y0 >= -EPS && b.x1 <= w + EPS && b.y1 <= d + EPS;
  }

  // Murs qui ne séparent que des segments d'un même couloir : un couloir est ouvert. Les plans
  // enregistrés avant que le générateur ne les supprime en ont encore ; on ne les dessine pas.
  function hallwayOnlyWalls(plan) {
    const hall = [];
    const other = [];
    (plan.rooms || []).forEach((room) => {
      const bucket = room.type === 'hallway' ? hall : other;
      edgesOf(room.polygon || []).forEach((e) => bucket.push(e));
    });
    const out = new Set();
    (plan.walls || []).forEach((wall) => {
      if (String(wall.id || '').startsWith('w_outer')) return;
      const onHall = hall.filter(([a, b]) => sameEdge(a, b, wall.a, wall.b)).length;
      const onOther = other.some(([a, b]) => sameEdge(a, b, wall.a, wall.b));
      if (onHall >= 2 && !onOther) out.add(wall.id);
    });
    return out;
  }

  // Un déplacement est valide s'il ne chevauche aucune pièce et reste dans la maison.
  function canMove(plan, ri, dx, dy) {
    return insideHouse(plan, ri, dx, dy) && maxOverlap(plan, ri, dx, dy).area <= MIN_OVERLAP;
  }

  // Aimante la pièce sur les bords voisins (autres pièces, limites de la maison) à `tol` m près.
  function snapMove(plan, ri, dx, dy, tol) {
    const t = tol === undefined ? 0.25 : tol;
    const { w, d } = bounds(plan);
    const mine = shifted(bboxOf(plan.rooms[ri].polygon), dx, dy);
    const xs = [0, w];
    const ys = [0, d];
    plan.rooms.forEach((room, j) => {
      if (j === ri || (room.polygon || []).length < 3) return;
      const b = bboxOf(room.polygon);
      xs.push(b.x0, b.x1);
      ys.push(b.y0, b.y1);
    });
    const pull = (edges, targets) => {
      let best = null;
      edges.forEach((e) => targets.forEach((g) => {
        const diff = g - e;
        if (Math.abs(diff) <= t && (best === null || Math.abs(diff) < Math.abs(best))) best = diff;
      }));
      return best === null ? 0 : best;
    };
    return { dx: dx + pull([mine.x0, mine.x1], xs), dy: dy + pull([mine.y0, mine.y1], ys) };
  }

  // Déplace la pièce `ri` de (dx, dy). `uid(prefix)` fabrique les identifiants des nouveaux murs.
  function translateRoom(plan, ri, dx, dy, uid) {
    const room = plan.rooms[ri];
    const oldEdges = edgesOf(room.polygon).map(([a, b]) => [{ x: a.x, y: a.y }, { x: b.x, y: b.y }]);
    const others = plan.rooms.filter((_, j) => j !== ri).flatMap((r) => edgesOf(r.polygon || []));
    const moving = new Set();
    oldEdges.forEach(([a, b]) => {
      const shared = others.some(([c, e]) => sameEdge(a, b, c, e));
      plan.walls.forEach((wall) => {
        if (!sameEdge(a, b, wall.a, wall.b)) return;
        // Un mur commun à une voisine, ou un mur extérieur, reste où il est.
        if (!shared && !String(wall.id || '').startsWith('w_outer')) moving.add(wall);
      });
    });
    moving.forEach((wall) => {
      wall.a = { x: round(wall.a.x + dx), y: round(wall.a.y + dy) };
      wall.b = { x: round(wall.b.x + dx), y: round(wall.b.y + dy) };
    });
    room.polygon = room.polygon.map((p) => ({ x: round(p.x + dx), y: round(p.y + dy) }));
    // Les arêtes de la pièce qui n'ont pas de mur à leur nouvelle place en reçoivent un.
    edgesOf(room.polygon).forEach(([a, b]) => {
      if (!plan.walls.some((wall) => sameEdge(a, b, wall.a, wall.b))) {
        plan.walls.push({ id: uid('w'), a: { x: a.x, y: a.y }, b: { x: b.x, y: b.y }, thickness_m: 0.15 });
      }
    });
    (plan.furniture || []).forEach((it) => {
      if (it.room_id === room.id && it.position) {
        it.position.x = round(it.position.x + dx);
        it.position.y = round(it.position.y + dy);
      }
    });
  }

  function round(v) {
    return Math.round(v * 100) / 100;
  }

  function clamp(v, lo, hi) {
    return hi < lo ? (lo + hi) / 2 : Math.min(hi, Math.max(lo, v));
  }

  // Échange deux pièces : chacune prend la place (le polygone) de l'autre. Les murs et les
  // ouvertures ne bougent pas, donc le pavage de la maison reste intact ; le mobilier suit sa
  // pièce, remis à l'échelle de la nouvelle case.
  function swapRooms(plan, i, j) {
    const a = plan.rooms[i];
    const b = plan.rooms[j];
    const boxA = bboxOf(a.polygon);
    const boxB = bboxOf(b.polygon);
    const remap = (it, from, to) => {
      const fw = from.x1 - from.x0 || 1;
      const fh = from.y1 - from.y0 || 1;
      const rx = clamp((it.position.x - from.x0) / fw, 0, 1);
      const ry = clamp((it.position.y - from.y0) / fh, 0, 1);
      const m = 0.3;
      it.position.x = round(clamp(to.x0 + rx * (to.x1 - to.x0), to.x0 + m, to.x1 - m));
      it.position.y = round(clamp(to.y0 + ry * (to.y1 - to.y0), to.y0 + m, to.y1 - m));
    };
    (plan.furniture || []).forEach((it) => {
      if (!it.position) return;
      if (it.room_id === a.id) remap(it, boxA, boxB);
      else if (it.room_id === b.id) remap(it, boxB, boxA);
    });
    const tmp = a.polygon;
    a.polygon = b.polygon;
    b.polygon = tmp;
    return { a: polyArea(a.polygon), b: polyArea(b.polygon) };
  }

  function polyArea(poly) {
    let s = 0;
    poly.forEach((p, k) => {
      const q = poly[(k + 1) % poly.length];
      s += p.x * q.y - q.x * p.y;
    });
    return Math.abs(s) / 2;
  }

  // Pièce sous un point (hors `exclude`), ou -1.
  function roomAt(plan, p, exclude) {
    for (let i = plan.rooms.length - 1; i >= 0; i--) {
      if (i === exclude) continue;
      const poly = plan.rooms[i].polygon || [];
      if (poly.length < 3) continue;
      let inside = false;
      for (let j = 0, k = poly.length - 1; j < poly.length; k = j++) {
        const xi = poly[j].x, yi = poly[j].y, xk = poly[k].x, yk = poly[k].y;
        if ((yi > p.y) !== (yk > p.y) && p.x < ((xk - xi) * (p.y - yi)) / ((yk - yi) || 1e-9) + xi) inside = !inside;
      }
      if (inside) return i;
    }
    return -1;
  }

  // Que fait un dépôt ? { action: 'move' | 'swap' | 'cancel', dx, dy, target }.
  function resolveDrop(plan, ri, dx, dy, pointer) {
    const snapped = snapMove(plan, ri, dx, dy);
    if (canMove(plan, ri, snapped.dx, snapped.dy)) {
      if (Math.abs(snapped.dx) < 1e-9 && Math.abs(snapped.dy) < 1e-9) return { action: 'cancel', dx: 0, dy: 0, target: -1 };
      return { action: 'move', dx: snapped.dx, dy: snapped.dy, target: -1 };
    }
    const target = roomAt(plan, pointer, ri);
    if (target >= 0) return { action: 'swap', dx: 0, dy: 0, target };
    return { action: 'cancel', dx: 0, dy: 0, target: -1 };
  }

  function cycleDoorSwing(opening) {
    if (!opening || opening.type !== 'door') return null;
    const states = [
      ['start', 'positive'], ['end', 'positive'],
      ['end', 'negative'], ['start', 'negative'],
    ];
    const hinge = opening.hinge === 'end' ? 'end' : 'start';
    const swing = opening.swing === 'negative' ? 'negative' : 'positive';
    const current = states.findIndex((state) => state[0] === hinge && state[1] === swing);
    const next = states[(current + 1) % states.length];
    opening.hinge = next[0];
    opening.swing = next[1];
    return { hinge: next[0], swing: next[1] };
  }

  const api = {
    EPS, MIN_OVERLAP, samePt, sameEdge, bboxOf, overlapArea, maxOverlap, insideHouse, canMove,
    snapMove, translateRoom, swapRooms, roomAt, resolveDrop, polyArea, hallwayOnlyWalls,
    cycleDoorSwing,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PlanEdit = api;
})(typeof window !== 'undefined' ? window : globalThis);
