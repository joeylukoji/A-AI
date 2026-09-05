(() => {
  const canvas = document.getElementById('plan-canvas');
  const planEl = document.getElementById('plan-document-data');
  if (!canvas || !planEl) return;

  let plan;
  try {
    plan = structuredClone(JSON.parse(planEl.textContent || '{}'));
  } catch {
    return;
  }
  plan.walls = plan.walls || [];
  plan.rooms = plan.rooms || [];
  plan.openings = plan.openings || [];
  plan.furniture = plan.furniture || [];
  if (!plan.floor) plan.floor = { level: 0, height_m: 2.7, bounds: { width: 12, depth: 10 } };
  if (!plan.floor.bounds) plan.floor.bounds = { width: 12, depth: 10 };

  const cfg = {
    projectId: canvas.dataset.projectId || '',
    revisionId: canvas.dataset.revisionId || '',
    canEdit: canvas.dataset.canEdit === 'true',
  };

  const ctx = canvas.getContext('2d');
  const status = document.getElementById('save-status');
  const topoEl = document.getElementById('topo-status');
  let revisionId = cfg.revisionId || null;
  let drag = null;
  let tool = 'select';
  let saveTimer = null;
  const pad = 40;
  const GRID = 0.1; // snap 10 cm
  const EPS = 0.06; // coïncidence sommets murs <-> polygones

  // ---- vue : échelle auto pour que le plan + jardin remplissent le canvas -------------
  let scale = 40;
  let ox = pad;
  let oy = pad;
  function fitView() {
    const bw = plan.floor.bounds.width || 12;
    const bd = plan.floor.bounds.depth || 10;
    const garden = 1.8;
    scale = Math.min((canvas.width - 2 * pad) / (bw + garden), (canvas.height - 2 * pad) / (bd + garden));
    ox = (canvas.width - (bw + garden) * scale) / 2;
    oy = (canvas.height - (bd + garden) * scale) / 2;
  }

  const snap = (v) => Math.round(v / GRID) * GRID;
  function toScreen(p) {
    return { x: ox + p.x * scale, y: oy + p.y * scale };
  }
  function toWorld(x, y) {
    return { x: snap((x - ox) / scale), y: snap((y - oy) / scale) };
  }
  function wallLen(w) {
    return Math.hypot(w.b.x - w.a.x, w.b.y - w.a.y) || 0.1;
  }
  function uid(prefix) {
    return prefix + Math.random().toString(36).slice(2, 8);
  }
  const samePt = (a, b, eps = EPS) => Math.abs(a.x - b.x) < eps && Math.abs(a.y - b.y) < eps;

  function topology() {
    const walls = plan.walls;
    if (walls.length < 4) return 'Au moins 4 murs';
    const ortho = walls.every((w) => Math.abs(w.a.x - w.b.x) < 1e-6 || Math.abs(w.a.y - w.b.y) < 1e-6);
    if (!ortho) return 'Murs non orthogonaux';
    const ids = new Set(walls.map((w) => w.id));
    if (plan.openings.some((o) => !ids.has(o.wall_id))) return 'Ouverture hors mur';
    return '';
  }

  // ---- dessin ----------------------------------------------------------------
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const bw = plan.floor.bounds.width || 12;
    const bd = plan.floor.bounds.depth || 10;
    const style = window.PlanStyle;

    if (style && style.drawSite) style.drawSite(ctx, bw, bd, toScreen, canvas.width, canvas.height);
    else {
      ctx.fillStyle = '#f7f4ef';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    // grille 0,5 m
    ctx.strokeStyle = 'rgba(40, 40, 40, 0.08)';
    ctx.lineWidth = 1;
    for (let gx = 0; gx <= bw + 1e-6; gx += 0.5) {
      const s0 = toScreen({ x: gx, y: 0 });
      const s1 = toScreen({ x: gx, y: bd });
      ctx.beginPath(); ctx.moveTo(s0.x, s0.y); ctx.lineTo(s1.x, s1.y); ctx.stroke();
    }
    for (let gy = 0; gy <= bd + 1e-6; gy += 0.5) {
      const s0 = toScreen({ x: 0, y: gy });
      const s1 = toScreen({ x: bw, y: gy });
      ctx.beginPath(); ctx.moveTo(s0.x, s0.y); ctx.lineTo(s1.x, s1.y); ctx.stroke();
    }

    // pièces
    (plan.rooms || []).forEach((room) => {
      if (!room.polygon?.length) return;
      if (style && style.drawFloor) style.drawFloor(ctx, room, toScreen);
      else {
        ctx.beginPath();
        room.polygon.forEach((p, i) => {
          const s = toScreen(p);
          if (i === 0) ctx.moveTo(s.x, s.y); else ctx.lineTo(s.x, s.y);
        });
        ctx.closePath();
        ctx.fillStyle = style ? style.fill(room) : 'rgba(20, 83, 45, 0.08)';
        ctx.fill();
      }
      if (style && !(plan.furniture || []).length) style.drawFixtures(ctx, room, toScreen);
    });

    // mobilier (les mêmes instances que le 3D)
    if (style && (plan.furniture || []).length) {
      style.drawFurniture(ctx, plan.furniture, toScreen);
    }

    if (style && style.drawPorch) style.drawPorch(ctx, plan.openings, plan.walls, bd, toScreen);

    if (style && style.drawWalls) {
      style.drawWalls(ctx, plan.walls, toScreen, scale);
    } else {
      (plan.walls || []).forEach((wall) => {
        const a = toScreen(wall.a);
        const b = toScreen(wall.b);
        ctx.strokeStyle = '#6e6e6a';
        ctx.lineWidth = Math.max(5, (wall.thickness_m || 0.2) * scale);
        ctx.lineCap = 'square';
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      });
    }

    // noms de pièces par-dessus le mobilier, discrets
    (plan.rooms || []).forEach((room) => {
      if (!room.polygon?.length) return;
      const c = room.polygon.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), { x: 0, y: 0 });
      c.x /= room.polygon.length; c.y /= room.polygon.length;
      const sc = toScreen(c);
      const text = style ? style.label(room) : (room.name || room.type);
      ctx.font = '600 12px "DM Sans", sans-serif';
      ctx.fillStyle = 'rgba(255,255,255,0.72)';
      ctx.fillText(text, sc.x - ctx.measureText(text).width / 2 + 1, sc.y + 1);
      ctx.fillStyle = '#2a2a28';
      ctx.fillText(text, sc.x - ctx.measureText(text).width / 2, sc.y);
    });

    // ouvertures : vitrage blanc / porte + battant
    if (style && style.drawOpenings) {
      style.drawOpenings(ctx, plan.openings, plan.walls, toScreen, scale);
    } else {
      (plan.openings || []).forEach((op) => {
        const wall = plan.walls.find((w) => w.id === op.wall_id);
        if (!wall) return;
        const len = wallLen(wall);
        const w2 = op.width_m || 0.9;
        const t0 = Math.min(1, Math.max(0, (op.offset_m || 0) / len));
        const t1 = Math.min(1, Math.max(0, ((op.offset_m || 0) + w2) / len));
        const p0 = toScreen({ x: wall.a.x + (wall.b.x - wall.a.x) * t0, y: wall.a.y + (wall.b.y - wall.a.y) * t0 });
        const p1 = toScreen({ x: wall.a.x + (wall.b.x - wall.a.x) * t1, y: wall.a.y + (wall.b.y - wall.a.y) * t1 });
        ctx.strokeStyle = '#ecece8';
        ctx.lineWidth = Math.max(4, (wall.thickness_m || 0.15) * scale + 2);
        ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y); ctx.stroke();
      });
    }

    // poignées de murs (par-dessus tout)
    (plan.walls || []).forEach((wall) => {
      [toScreen(wall.a), toScreen(wall.b)].forEach((pt) => {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2);
        ctx.fillStyle = '#14b8a6';
        ctx.fill();
        ctx.strokeStyle = '#0f766e';
        ctx.stroke();
      });
    });

    // légende
    const legend = document.getElementById('room-legend');
    if (legend) {
      legend.innerHTML = (plan.rooms || []).map((room) => {
        const name = style ? style.label(room) : (room.name || room.type);
        const color = style ? style.fill(room) : '#ddd';
        return `<li class="flex items-center gap-2"><span class="inline-block w-3 h-3 rounded-sm border border-zinc-400" style="background:${color}"></span>${name}</li>`;
      }).join('');
    }

    if (topoEl) topoEl.textContent = topology();
    if (window.PlanCompliance) {
      window.PlanCompliance.render(plan, document.getElementById('compliance-score'));
      window.PlanCompliance.renderDimensions(plan, document.getElementById('plan-dimensions'));
    }
  }

  // ---- hit testing -------------------------------------------------------------
  function hitHandle(x, y) {
    for (let i = 0; i < plan.walls.length; i++) {
      const wall = plan.walls[i];
      for (const end of ['a', 'b']) {
        const s = toScreen(wall[end]);
        if ((s.x - x) ** 2 + (s.y - y) ** 2 < 144) return { kind: 'wall', i, end };
      }
    }
    return null;
  }

  function hitWall(x, y) {
    const p = toWorld(x, y);
    let best = null;
    let bestD = 0.45;
    plan.walls.forEach((wall, i) => {
      const dx = wall.b.x - wall.a.x;
      const dy = wall.b.y - wall.a.y;
      const len2 = dx * dx + dy * dy || 1;
      let t = ((p.x - wall.a.x) * dx + (p.y - wall.a.y) * dy) / len2;
      t = Math.min(1, Math.max(0, t));
      const qx = wall.a.x + t * dx;
      const qy = wall.a.y + t * dy;
      const d = Math.hypot(p.x - qx, p.y - qy);
      if (d < bestD) {
        bestD = d;
        best = { i, t, wall, offset: t * wallLen(wall) };
      }
    });
    return best;
  }

  function hitRoom(x, y) {
    const p = toWorld(x, y);
    for (let i = plan.rooms.length - 1; i >= 0; i--) {
      const poly = plan.rooms[i].polygon || [];
      if (poly.length < 3) continue;
      let inside = false;
      for (let j = 0, k = poly.length - 1; j < poly.length; k = j++) {
        const xi = poly[j].x, yi = poly[j].y, xk = poly[k].x, yk = poly[k].y;
        if ((yi > p.y) !== (yk > p.y) && p.x < ((xk - xi) * (p.y - yi)) / ((yk - yi) || 1e-9) + xi) {
          inside = !inside;
        }
      }
      if (inside) return i;
    }
    return -1;
  }

  function hitOpening(x, y) {
    for (let i = 0; i < plan.openings.length; i++) {
      const op = plan.openings[i];
      const wall = plan.walls.find((w) => w.id === op.wall_id);
      if (!wall) continue;
      const len = wallLen(wall);
      const t = Math.min(1, Math.max(0, ((op.offset_m || 0) + (op.width_m || 0.9) / 2) / len));
      const s = toScreen({
        x: wall.a.x + (wall.b.x - wall.a.x) * t,
        y: wall.a.y + (wall.b.y - wall.a.y) * t,
      });
      if ((s.x - x) ** 2 + (s.y - y) ** 2 < 169) return i;
    }
    return -1;
  }

  // ---- mutations ----------------------------------------------------------------
  function addRoomAt(x, y) {
    const p = toWorld(x, y);
    const w = 3, d = 2.5;
    const id = uid('r');
    plan.rooms.push({
      id,
      name: 'Pièce',
      type: 'other',
      polygon: [
        { x: p.x, y: p.y },
        { x: p.x + w, y: p.y },
        { x: p.x + w, y: p.y + d },
        { x: p.x, y: p.y + d },
      ],
    });
    const edges = [
      [{ x: p.x, y: p.y }, { x: p.x + w, y: p.y }],
      [{ x: p.x + w, y: p.y }, { x: p.x + w, y: p.y + d }],
      [{ x: p.x + w, y: p.y + d }, { x: p.x, y: p.y + d }],
      [{ x: p.x, y: p.y + d }, { x: p.x, y: p.y }],
    ];
    edges.forEach(([a, b]) => {
      const exists = plan.walls.some((wall) =>
        (samePt(wall.a, a, 1e-6) && samePt(wall.b, b, 1e-6)) || (samePt(wall.a, b, 1e-6) && samePt(wall.b, a, 1e-6)));
      if (!exists) plan.walls.push({ id: uid('w'), a, b, thickness_m: 0.15 });
    });
  }

  function addOpening(type, hit) {
    plan.openings.push({
      id: uid('o'),
      wall_id: hit.wall.id,
      type,
      offset_m: Math.max(0.2, +(hit.offset - 0.45).toFixed(2)),
      width_m: type === 'window' ? 1.2 : 0.9,
    });
  }

  // Déplace un sommet de mur et synchronise les sommets de polygones coïncidents,
  // pour que le rendu 2D (polygones) et le 3D (murs) restent alignés.
  function moveWallEndpoint(wall, end, p) {
    const old = { x: wall[end].x, y: wall[end].y };
    wall[end] = { x: p.x, y: p.y };
    (plan.rooms || []).forEach((room) => {
      (room.polygon || []).forEach((v, idx) => {
        if (samePt(v, old)) room.polygon[idx] = { x: p.x, y: p.y };
      });
    });
    // les autres murs qui partagent ce sommet suivent aussi
    (plan.walls || []).forEach((w2) => {
      if (w2 === wall) return;
      for (const e2 of ['a', 'b']) {
        if (samePt(w2[e2], old)) w2[e2] = { x: p.x, y: p.y };
      }
    });
  }

  // Déplace une pièce entière : polygone + murs coïncidents + mobilier de la pièce.
  function moveRoom(ri, dx, dy) {
    const room = plan.rooms[ri];
    if (!room) return;
    const mapping = [];
    (room.polygon || []).forEach((v, idx) => {
      mapping.push({ old: { x: v.x, y: v.y }, neo: { x: snap(v.x + dx), y: snap(v.y + dy) } });
      room.polygon[idx] = mapping[mapping.length - 1].neo;
    });
    (plan.walls || []).forEach((wall) => {
      for (const e of ['a', 'b']) {
        const m = mapping.find((mm) => samePt(mm.old, wall[e]));
        if (m) wall[e] = { x: m.neo.x, y: m.neo.y };
      }
    });
    (plan.furniture || []).forEach((it) => {
      if (it.room_id === room.id && it.position) {
        it.position.x = snap(it.position.x + dx);
        it.position.y = snap(it.position.y + dy);
      }
    });
  }

  function markDirty() {
    status.textContent = 'Modifié';
    draw();
    if (!cfg.canEdit) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 1200);
  }

  // ---- événements ----------------------------------------------------------------
  function evtPos(e) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) * (canvas.width / rect.width),
      y: (e.clientY - rect.top) * (canvas.height / rect.height),
    };
  }

  canvas.addEventListener('mousedown', (e) => {
    if (!cfg.canEdit) return;
    const { x, y } = evtPos(e);

    if (tool === 'select') {
      const h = hitHandle(x, y);
      if (h) { drag = h; return; }
      const ri = hitRoom(x, y);
      if (ri >= 0) {
        const p = toWorld(x, y);
        drag = { kind: 'room', i: ri, last: p };
      }
      return;
    }
    if (tool === 'room') {
      addRoomAt(x, y);
      markDirty();
      return;
    }
    if (tool === 'door' || tool === 'window') {
      const hit = hitWall(x, y);
      if (hit) {
        addOpening(tool, hit);
        markDirty();
      }
      return;
    }
    if (tool === 'delete') {
      const oi = hitOpening(x, y);
      if (oi >= 0) {
        plan.openings.splice(oi, 1);
        markDirty();
        return;
      }
      const ri = hitRoom(x, y);
      if (ri >= 0) {
        const room = plan.rooms[ri];
        // retire les murs qui coïncident avec les arêtes de la pièce supprimée
        const poly = room.polygon || [];
        const n = poly.length;
        const edgeOf = [];
        for (let i = 0; i < n; i++) edgeOf.push([poly[i], poly[(i + 1) % n]]);
        plan.walls = plan.walls.filter((wall) => {
          const onEdge = edgeOf.some(([a, b]) =>
            (samePt(wall.a, a) && samePt(wall.b, b)) || (samePt(wall.a, b) && samePt(wall.b, a)));
          if (onEdge) {
            plan.openings = plan.openings.filter((o) => o.wall_id !== wall.id);
            return false;
          }
          return true;
        });
        plan.furniture = plan.furniture.filter((f) => f.room_id !== room.id);
        plan.rooms.splice(ri, 1);
        markDirty();
        return;
      }
      const wh = hitHandle(x, y) || hitWall(x, y);
      if (wh) {
        const wall = plan.walls[wh.i];
        plan.openings = plan.openings.filter((o) => o.wall_id !== wall.id);
        plan.walls.splice(wh.i, 1);
        markDirty();
      }
    }
  });

  canvas.addEventListener('mousemove', (e) => {
    if (!drag) return;
    const { x, y } = evtPos(e);
    const p = toWorld(x, y);
    if (drag.kind === 'wall') {
      const wall = plan.walls[drag.i];
      const other = drag.end === 'a' ? wall.b : wall.a;
      // snap orthogonal
      if (Math.abs(p.x - other.x) > Math.abs(p.y - other.y)) p.y = other.y;
      else p.x = other.x;
      moveWallEndpoint(wall, drag.end, p);
      draw();
      status.textContent = 'Modifié';
    } else if (drag.kind === 'room') {
      const dx = p.x - drag.last.x;
      const dy = p.y - drag.last.y;
      if (Math.abs(dx) < 1e-9 && Math.abs(dy) < 1e-9) return;
      moveRoom(drag.i, dx, dy);
      drag.last = p;
      draw();
      status.textContent = 'Modifié';
    }
  });

  window.addEventListener('mouseup', () => {
    if (drag) {
      drag = null;
      markDirty();
    }
  });

  // ---- outils ---------------------------------------------------------------------
  const toolBtns = [...document.querySelectorAll('.tool-btn')];
  toolBtns.forEach((btn) => { btn.dataset.base = btn.dataset.base || 'btn-line'; });
  function setTool(name) {
    tool = name;
    toolBtns.forEach((b) => {
      b.classList.remove('btn-dark', 'btn-line', 'btn-danger');
      b.classList.add(b.dataset.tool === name ? 'btn-dark' : (b.dataset.tool === 'delete' ? 'btn-danger' : 'btn-line'));
    });
    canvas.style.cursor = name === 'select' ? 'move' : (name === 'delete' ? 'not-allowed' : 'crosshair');
  }
  toolBtns.forEach((btn) => btn.addEventListener('click', () => setTool(btn.dataset.tool)));
  setTool('select');

  // ---- sauvegarde -------------------------------------------------------------------
  async function save() {
    if (!cfg.canEdit) return;
    const issue = topology();
    if (issue) {
      status.textContent = issue;
      return;
    }
    status.textContent = 'Enregistrement…';
    try {
      const res = await fetch(`/api/v1/projects/${cfg.projectId}/plan`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          plan_document: plan,
          base_revision_id: revisionId || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        status.textContent = data.error?.message || 'Erreur';
        return;
      }
      revisionId = data.id;
      status.textContent = `Enregistré v${data.version}`;
    } catch {
      status.textContent = 'Réseau indisponible';
    }
  }

  document.getElementById('btn-save')?.addEventListener('click', save);

  fitView();
  draw();
})();
