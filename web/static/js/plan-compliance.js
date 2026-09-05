window.PlanCompliance = (() => {
  const HABITABLE = new Set(['living', 'bedroom', 'dining', 'office']);
  const TOL = 0.15;
  const MIN_SEAM = 0.55;

  function area(poly) {
    if (!poly || poly.length < 3) return 0;
    let acc = 0;
    for (let i = 0; i < poly.length; i++) {
      const p = poly[i], q = poly[(i + 1) % poly.length];
      acc += p.x * q.y - q.x * p.y;
    }
    return Math.abs(acc) / 2;
  }
  function bbox(poly) {
    const xs = poly.map((p) => p.x), ys = poly.map((p) => p.y);
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  function sides(poly) {
    const [x0, y0, x1, y1] = bbox(poly);
    return [x1 - x0, y1 - y0];
  }
  function overlap(a, b) {
    const [ax0, ay0, ax1, ay1] = bbox(a);
    const [bx0, by0, bx1, by1] = bbox(b);
    const ix = Math.max(0, Math.min(ax1, bx1) - Math.max(ax0, bx0));
    const iy = Math.max(0, Math.min(ay1, by1) - Math.max(ay0, by0));
    return ix * iy;
  }
  function shareEdge(a, b) {
    const [ax0, ay0, ax1, ay1] = bbox(a);
    const [bx0, by0, bx1, by1] = bbox(b);
    const yOv = Math.min(ay1, by1) - Math.max(ay0, by0);
    const xOv = Math.min(ax1, bx1) - Math.max(ax0, bx0);
    const xTouch = Math.abs(ax1 - bx0) <= TOL || Math.abs(bx1 - ax0) <= TOL;
    const yTouch = Math.abs(ay1 - by0) <= TOL || Math.abs(by1 - ay0) <= TOL;
    return (xTouch && yOv >= MIN_SEAM) || (yTouch && xOv >= MIN_SEAM);
  }
  function isolatedRooms(rooms) {
    const hubs = [];
    rooms.forEach((r, i) => { if (r.type === 'living' || r.type === 'hallway') hubs.push(i); });
    const start = hubs.length ? hubs : rooms.map((_, i) => i);
    const seen = new Set(start);
    const stack = [...start];
    while (stack.length) {
      const i = stack.pop();
      rooms.forEach((other, j) => {
        if (seen.has(j)) return;
        if (shareEdge(rooms[i].polygon, other.polygon)) { seen.add(j); stack.push(j); }
      });
    }
    return rooms.filter((_, i) => !seen.has(i)).map((r) => r.name || r.type);
  }
  function envelope(rooms) {
    if (!rooms.length) return null;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    rooms.forEach((r) => {
      const [a, b, c, d] = bbox(r.polygon);
      x0 = Math.min(x0, a); y0 = Math.min(y0, b); x1 = Math.max(x1, c); y1 = Math.max(y1, d);
    });
    return [x0, y0, x1, y1];
  }
  function touchesOuter(poly, w, d, env) {
    const [x0, y0, x1, y1] = bbox(poly);
    if (env) {
      if (x0 <= env[0] + TOL || y0 <= env[1] + TOL || x1 >= env[2] - TOL || y1 >= env[3] - TOL) return true;
    }
    return x0 <= TOL || y0 <= TOL || (w && x1 >= w - TOL) || (d && y1 >= d - TOL);
  }
  function isOuter(wall, w, d) {
    if (!wall) return false;
    const xs = [wall.a.x, wall.b.x], ys = [wall.a.y, wall.b.y];
    return Math.max(...xs) <= TOL || Math.min(...xs) >= w - TOL
      || Math.max(...ys) <= TOL || Math.min(...ys) >= d - TOL
      || String(wall.id || '').startsWith('w_outer');
  }

  function evaluate(plan) {
    const rooms = (plan.rooms || []).filter((r) => r.polygon && r.polygon.length >= 3);
    const walls = plan.walls || [];
    const openings = plan.openings || [];
    const bounds = (plan.floor && plan.floor.bounds) || {};
    const width = bounds.width || 0, depth = bounds.depth || 0;
    const height = (plan.floor && plan.floor.height_m) || 0;
    const byId = Object.fromEntries(walls.map((w) => [w.id, w]));
    const checks = [];
    const add = (key, label, ok, weight, detail) => checks.push({ key, label, ok, weight, detail: detail || '' });

    const living = rooms.filter((r) => r.type === 'living');
    const beds = rooms.filter((r) => r.type === 'bedroom');
    const kitchens = rooms.filter((r) => r.type === 'kitchen');
    const baths = rooms.filter((r) => r.type === 'bathroom');
    const halls = rooms.filter((r) => r.type === 'hallway');
    const habit = rooms.filter((r) => HABITABLE.has(r.type));

    add('height', 'Hauteur sous plafond ≥ 2,20 m', height >= 2.2, 8, `${height.toFixed(2)} m`);
    add('living', 'Séjour présent', living.length > 0, 8);
    const livArea = living[0] ? area(living[0].polygon) : 0;
    add('living_area', 'Séjour ≥ 9 m²', livArea >= 9, 10, `${livArea.toFixed(1)} m²`);
    const smallBeds = beds.filter((r) => area(r.polygon) < 9);
    add('bedrooms', 'Chaque chambre ≥ 9 m²', beds.length > 0 && smallBeds.length === 0, 10,
      beds.length ? (smallBeds.length ? `${smallBeds.length} trop petite(s)` : 'ok') : 'aucune chambre');
    add('kitchen', 'Cuisine présente', kitchens.length > 0, 6);
    add('bathroom', 'Salle de bain présente', baths.length > 0, 6);
    const env = envelope(rooms);
    const noFacade = habit.filter((r) => !touchesOuter(r.polygon, width, depth, env)).map((r) => r.name || r.type);
    add('facade', 'Pièces habitables sur façade', habit.length > 0 && noFacade.length === 0, 12, noFacade.join(', ') || 'ok');
    add('window', 'Au moins une fenêtre', openings.some((o) => o.type === 'window'), 6);
    const outerDoors = openings.filter((o) => o.type === 'door' && isOuter(byId[o.wall_id], width, depth));
    add('entry', 'Porte d’entrée sur façade', outerDoors.length > 0, 6);
    const isolated = isolatedRooms(rooms);
    add('access', 'Pièces accessibles (bord partagé)', isolated.length === 0, 10, isolated.join(', ') || 'ok');
    const narrowHall = halls.filter((r) => Math.min(...sides(r.polygon)) < 0.9);
    add('hall', 'Couloir ≥ 0,90 m si présent', narrowHall.length === 0, 6, halls.length ? (narrowHall.length ? 'trop étroit' : 'ok') : 'pas de couloir');
    const thinDoors = openings.filter((o) => o.type === 'door' && (o.width_m || 0) < 0.8);
    add('doors', 'Portes ≥ 0,80 m', openings.length > 0 && thinDoors.length === 0, 4);
    const ortho = walls.length > 0 && walls.every((w) => Math.abs(w.a.x - w.b.x) < 1e-6 || Math.abs(w.a.y - w.b.y) < 1e-6);
    add('ortho', 'Murs orthogonaux', ortho, 6);
    let ov = 0;
    rooms.forEach((a, i) => rooms.slice(i + 1).forEach((b) => { ov += overlap(a.polygon, b.polygon); }));
    add('overlap', 'Pas de chevauchement', ov < 0.25, 8, `${ov.toFixed(2)} m²`);
    let oob = false;
    if (width && depth) {
      rooms.forEach((r) => {
        const [x0, y0, x1, y1] = bbox(r.polygon);
        if (x0 < -TOL || y0 < -TOL || x1 > width + TOL || y1 > depth + TOL) oob = true;
      });
    }
    add('bounds', 'Pièces dans l’emprise', rooms.length > 0 && !oob, 4);

    const totalW = checks.reduce((s, c) => s + c.weight, 0);
    const got = checks.filter((c) => c.ok).reduce((s, c) => s + c.weight, 0);
    const score = totalW ? Math.round((100 * got) / totalW) : 0;
    const grade = score >= 80 ? 'A' : score >= 65 ? 'B' : score >= 50 ? 'C' : score >= 35 ? 'D' : 'E';
    return { score, grade, passed: checks.filter((c) => c.ok).length, total: checks.length, checks,
      disclaimer: 'Indicatif (heuristiques d’habitabilité). Pas un contrôle réglementaire ni un permis.' };
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function render(plan, el) {
    if (!el) return;
    const r = evaluate(plan);
    const color = r.score >= 75 ? '#166534' : r.score >= 50 ? '#9a3412' : '#9f1239';
    el.innerHTML = `<div class="border border-stone-300 p-3 bg-white/80">
      <div class="flex items-baseline justify-between gap-3">
        <strong style="color:${color}">Conformité ${r.score}/100 · ${escapeHtml(r.grade)}</strong>
        <span class="text-xs text-stone-500">${r.passed}/${r.total} critères</span>
      </div>
      <ul class="mt-2 text-sm space-y-0.5">${r.checks.map((c) =>
        `<li>${c.ok ? '✓' : '✗'} ${escapeHtml(c.label)}${c.detail ? ` <span class="text-stone-500">(${escapeHtml(c.detail)})</span>` : ''}</li>`
      ).join('')}</ul>
      <p class="text-xs text-stone-500 mt-2">${escapeHtml(r.disclaimer)}</p>
    </div>`;
  }

  function dimensions(plan) {
    return (plan.rooms || []).map((room) => {
      const poly = room.polygon || [];
      if (poly.length < 3) return { name: room.name || room.type, width_m: 0, depth_m: 0, area_m2: 0 };
      const xs = poly.map((p) => p.x), ys = poly.map((p) => p.y);
      const w = Math.max(...xs) - Math.min(...xs);
      const d = Math.max(...ys) - Math.min(...ys);
      return {
        name: room.name || room.type,
        type: room.type,
        width_m: Math.round(w * 100) / 100,
        depth_m: Math.round(d * 100) / 100,
        area_m2: Math.round(w * d * 100) / 100,
      };
    });
  }

  function renderDimensions(plan, el) {
    if (!el) return;
    const rows = dimensions(plan);
    const b = (plan.floor && plan.floor.bounds) || {};
    el.innerHTML = `<div class="border border-stone-300 p-3 bg-white/80">
      <strong>Cotes exactes</strong>
      <p class="text-xs text-stone-500">Emprise ${b.width || '?'} × ${b.depth || '?'} m · H ${(plan.floor && plan.floor.height_m) || '?'} m</p>
      <table class="w-full text-sm mt-2"><thead><tr class="text-left text-stone-500"><th>Pièce</th><th>L</th><th>P</th><th>m²</th></tr></thead>
      <tbody>${rows.map((r) => `<tr><td>${escapeHtml(r.name)}</td><td>${r.width_m}</td><td>${r.depth_m}</td><td>${r.area_m2}</td></tr>`).join('')}</tbody></table>
    </div>`;
  }

  return { evaluate, render, dimensions, renderDimensions };
})();
