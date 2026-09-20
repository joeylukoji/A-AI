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
  function ensurePlan() {
    plan.walls = plan.walls || [];
    plan.rooms = plan.rooms || [];
    plan.openings = plan.openings || [];
    plan.furniture = plan.furniture || [];
    if (!plan.floor) plan.floor = { level: 0, height_m: 2.7, bounds: { width: 12, depth: 10 } };
    if (!plan.floor.bounds) plan.floor.bounds = { width: 12, depth: 10 };
  }
  ensurePlan();

  // Historique : l'enregistrement est automatique, une erreur (un échange par exemple) doit pouvoir s'annuler.
  const history = [];
  function checkpoint() {
    history.push(JSON.stringify(plan));
    if (history.length > 50) history.shift();
  }

  const cfg = {
    projectId: canvas.dataset.projectId || '',
    revisionId: canvas.dataset.revisionId || '',
    canEdit: canvas.dataset.canEdit === 'true',
  };

  const ctx = canvas.getContext('2d');
  const status = document.getElementById('save-status');
  const topoEl = document.getElementById('topo-status');
  const Edit = window.PlanEdit;
  let revisionId = cfg.revisionId || null;
  let drag = null;
  let tool = 'select';
  let saveTimer = null;
  let selected = -1;        // pièce sélectionnée
  let hoverRoom = -1;
  let hoverHandleRef = null;
  const GRID = 0.1;         // snap 10 cm
  const EPS = 0.06;         // coïncidence sommets murs <-> polygones
  const MARGIN = { left: 74, right: 30, top: 30, bottom: 74 }; // place des cotes autour de la maison

  // ---- vue : taille du canvas adaptée à la page, zoom et déplacement ------------------
  let W = 960;
  let H = 640;
  let dpr = 1;
  let scale = 40;
  let ox = 0;
  let oy = 0;
  let fitScale = 40;
  let userView = false;     // vrai dès que l'utilisateur zoome ou déplace la vue

  function planSize() {
    return { bw: plan.floor.bounds.width || 12, bd: plan.floor.bounds.depth || 10 };
  }

  function fitView() {
    const { bw, bd } = planSize();
    const aw = W - MARGIN.left - MARGIN.right;
    const ah = H - MARGIN.top - MARGIN.bottom;
    fitScale = Math.max(8, Math.min(aw / bw, ah / bd));
    scale = fitScale;
    ox = MARGIN.left + (aw - bw * scale) / 2;
    oy = MARGIN.top + (ah - bd * scale) / 2;
    userView = false;
  }

  // La hauteur suit les proportions de la maison (plus de grand vide autour d'un petit plan)
  // et reste bornée par l'écran : l'éditeur ne déborde plus.
  function resize() {
    const wrap = canvas.parentElement;
    const cssW = Math.max(320, Math.floor((wrap && wrap.clientWidth) || 960));
    const { bw, bd } = planSize();
    const aspect = (bd * 1 + (MARGIN.top + MARGIN.bottom) / 40) / (bw * 1 + (MARGIN.left + MARGIN.right) / 40);
    const maxH = Math.max(360, Math.floor(window.innerHeight * 0.66));
    const cssH = Math.round(Math.min(maxH, Math.max(320, cssW * aspect)));
    dpr = Math.min(2, window.devicePixelRatio || 1);
    W = cssW;
    H = cssH;
    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${cssH}px`;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    if (userView) {
      // on garde le zoom courant, mais la maison reste dans le cadre
      const keep = scale / (fitScale || scale);
      const oldFit = fitScale;
      fitView();
      scale = fitScale * (oldFit ? keep : 1);
      userView = true;
    } else {
      fitView();
    }
    draw(true);
  }

  const snap = (v) => Math.round(v / GRID) * GRID;
  function toScreen(p) {
    return { x: ox + p.x * scale, y: oy + p.y * scale };
  }
  function toWorld(x, y) {
    return { x: snap((x - ox) / scale), y: snap((y - oy) / scale) };
  }
  function toWorldRaw(x, y) {
    return { x: (x - ox) / scale, y: (y - oy) / scale };
  }
  function wallLen(w) {
    return Math.hypot(w.b.x - w.a.x, w.b.y - w.a.y) || 0.1;
  }
  function uid(prefix) {
    return prefix + Math.random().toString(36).slice(2, 8);
  }
  const samePt = (a, b, eps = EPS) => Math.abs(a.x - b.x) < eps && Math.abs(a.y - b.y) < eps;
  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

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
  function polyPath(poly, dx = 0, dy = 0) {
    ctx.beginPath();
    poly.forEach((p, i) => {
      const s = toScreen({ x: p.x + dx, y: p.y + dy });
      if (i === 0) ctx.moveTo(s.x, s.y); else ctx.lineTo(s.x, s.y);
    });
    ctx.closePath();
  }

  function drawGhost() {
    if (!drag || drag.kind !== 'room' || !drag.moved) return;
    const room = plan.rooms[drag.i];
    if (!room) return;
    const swap = !drag.valid && drag.target >= 0;
    const tone = drag.valid ? '20,184,166' : (swap ? '245,158,11' : '220,38,38');
    if (swap) {
      const t = plan.rooms[drag.target];
      polyPath(t.polygon);
      ctx.fillStyle = 'rgba(245,158,11,0.16)';
      ctx.fill();
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = 'rgba(217,119,6,0.95)';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.setLineDash([]);
    }
    polyPath(room.polygon, drag.dx, drag.dy);
    ctx.fillStyle = `rgba(${tone},0.20)`;
    ctx.fill();
    ctx.strokeStyle = `rgba(${tone},0.95)`;
    ctx.lineWidth = 2;
    ctx.stroke();
    const c = room.polygon.reduce((a, p) => ({ x: a.x + p.x, y: a.y + p.y }), { x: 0, y: 0 });
    const s = toScreen({ x: c.x / room.polygon.length + drag.dx, y: c.y / room.polygon.length + drag.dy });
    const msg = drag.valid ? 'Déposer ici' : (swap ? `Échanger avec ${style_label(plan.rooms[drag.target])}` : 'Chevauchement');
    ctx.font = '600 11px "DM Sans", system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const tw = ctx.measureText(msg).width + 14;
    ctx.fillStyle = `rgba(${tone},0.95)`;
    ctx.fillRect(s.x - tw / 2, s.y - 11, tw, 22);
    ctx.fillStyle = '#fff';
    ctx.fillText(msg, s.x, s.y);
  }

  function style_label(room) {
    const style = window.PlanStyle;
    return style ? style.label(room) : (room.name || room.type);
  }

  function draw(full = true) {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    const { bw, bd } = planSize();
    const style = window.PlanStyle;

    if (style && style.drawSite) style.drawSite(ctx, bw, bd, toScreen, W, H);
    else {
      ctx.fillStyle = '#fbfaf7';
      ctx.fillRect(0, 0, W, H);
    }

    // grille 1 m, très discrète, à l'intérieur de l'emprise seulement
    ctx.strokeStyle = 'rgba(40, 40, 40, 0.045)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let gx = 0; gx <= bw + 1e-6; gx += 1) {
      const s0 = toScreen({ x: gx, y: 0 });
      const s1 = toScreen({ x: gx, y: bd });
      ctx.moveTo(s0.x, s0.y); ctx.lineTo(s1.x, s1.y);
    }
    for (let gy = 0; gy <= bd + 1e-6; gy += 1) {
      const s0 = toScreen({ x: 0, y: gy });
      const s1 = toScreen({ x: bw, y: gy });
      ctx.moveTo(s0.x, s0.y); ctx.lineTo(s1.x, s1.y);
    }
    ctx.stroke();

    // pièces
    (plan.rooms || []).forEach((room) => {
      if (!room.polygon?.length) return;
      if (style && style.drawFloor) style.drawFloor(ctx, room, toScreen);
      else {
        polyPath(room.polygon);
        ctx.fillStyle = style ? style.fill(room) : 'rgba(20, 83, 45, 0.08)';
        ctx.fill();
      }
    });

    // survol et sélection : sous le mobilier et les murs
    if (cfg.canEdit && tool === 'select') {
      if (hoverRoom >= 0 && hoverRoom !== selected && plan.rooms[hoverRoom]) {
        polyPath(plan.rooms[hoverRoom].polygon);
        ctx.fillStyle = 'rgba(20,184,166,0.07)';
        ctx.fill();
      }
      if (selected >= 0 && plan.rooms[selected]) {
        polyPath(plan.rooms[selected].polygon);
        ctx.fillStyle = 'rgba(20,184,166,0.12)';
        ctx.fill();
      }
    }

    // mobilier (les mêmes instances que le 3D)
    if (style && (plan.furniture || []).length) {
      style.drawFurniture(ctx, plan.furniture, toScreen);
    } else if (style) {
      (plan.rooms || []).forEach((room) => style.drawFixtures(ctx, room, toScreen));
    }

    if (style && style.drawPorch) style.drawPorch(ctx, plan.openings, plan.walls, bd, toScreen);

    if (style && style.drawWalls) {
      const open = Edit.hallwayOnlyWalls(plan);
      style.drawWalls(ctx, open.size ? plan.walls.filter((w) => !open.has(w.id)) : plan.walls, toScreen, scale);
    } else {
      (plan.walls || []).forEach((wall) => {
        const a = toScreen(wall.a);
        const b = toScreen(wall.b);
        ctx.strokeStyle = '#4b4b48';
        ctx.lineWidth = Math.max(4, (wall.thickness_m || 0.2) * scale);
        ctx.lineCap = 'square';
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      });
    }

    // libellés : capitales + surface, un seul pour un couloir continu
    if (style && style.drawRoomLabels) {
      style.drawRoomLabels(ctx, plan.rooms, toScreen);
    } else {
      (plan.rooms || []).forEach((room) => {
        if (!room.polygon?.length) return;
        const c = room.polygon.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), { x: 0, y: 0 });
        c.x /= room.polygon.length; c.y /= room.polygon.length;
        const sc = toScreen(c);
        const text = style_label(room);
        ctx.font = '600 12px "DM Sans", sans-serif';
        ctx.fillStyle = '#2a2a28';
        ctx.fillText(text, sc.x - ctx.measureText(text).width / 2, sc.y);
      });
    }

    // ouvertures : vitrage / porte + battant
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
        ctx.strokeStyle = '#f6f5f1';
        ctx.lineWidth = Math.max(4, (wall.thickness_m || 0.15) * scale + 2);
        ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y); ctx.stroke();
      });
    }

    if (style && style.drawDimensions) style.drawDimensions(ctx, bw, bd, toScreen);

    // contour de la pièce sélectionnée, par-dessus les murs
    if (cfg.canEdit && tool === 'select' && selected >= 0 && plan.rooms[selected] && !(drag && drag.moved)) {
      polyPath(plan.rooms[selected].polygon);
      ctx.strokeStyle = 'rgba(13,148,136,0.95)';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // poignée de mur : seulement celle qu'on survole
    if (cfg.canEdit && tool === 'select' && hoverHandleRef) {
      const wall = plan.walls[hoverHandleRef.i];
      if (wall) {
        const pt = toScreen(wall[hoverHandleRef.end]);
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 6, 0, Math.PI * 2);
        ctx.fillStyle = '#14b8a6';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    }

    drawGhost();

    if (!full) return;

    // légende
    const legend = document.getElementById('room-legend');
    if (legend) {
      const seen = new Set();
      legend.innerHTML = (plan.rooms || []).filter((room) => {
        const key = room.type === 'hallway' ? 'hallway' : room.id;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      }).map((room) => {
        const name = room.type === 'hallway' ? 'Couloir' : style_label(room);
        const color = style ? style.fill(room) : '#ddd';
        return `<li class="flex items-center gap-2"><span class="inline-block w-3 h-3 rounded-sm border border-zinc-400" style="background:${escapeHtml(color)}"></span>${escapeHtml(name)}</li>`;
      }).join('');
    }

    if (topoEl) topoEl.textContent = topology();
    if (window.PlanCompliance) {
      window.PlanCompliance.render(plan, document.getElementById('compliance-score'));
      window.PlanCompliance.renderDimensions(plan, document.getElementById('plan-dimensions'));
    }
  }

  let rafPending = false;
  function redraw() {
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(() => { rafPending = false; draw(false); });
  }

  // ---- hit testing -------------------------------------------------------------
  function hitHandle(x, y) {
    for (let i = 0; i < plan.walls.length; i++) {
      const wall = plan.walls[i];
      for (const end of ['a', 'b']) {
        const s = toScreen(wall[end]);
        if ((s.x - x) ** 2 + (s.y - y) ** 2 < 100) return { kind: 'wall', i, end };
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
    return Edit.roomAt(plan, toWorldRaw(x, y), -1);
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

  function markDirty(message) {
    status.textContent = message || 'Modifié';
    draw(true);
    if (!cfg.canEdit) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 1200);
  }

  function say(text) {
    if (status) status.textContent = text;
  }

  function undo() {
    const last = history.pop();
    if (!last) { say('Rien à annuler'); return; }
    plan = JSON.parse(last);
    ensurePlan();
    selected = -1;
    hoverRoom = -1;
    hoverHandleRef = null;
    drag = null;
    markDirty('Modification annulée');
  }

  // ---- événements ----------------------------------------------------------------
  function evtPos(e) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) * (W / rect.width),
      y: (e.clientY - rect.top) * (H / rect.height),
    };
  }

  canvas.addEventListener('mousedown', (e) => {
    const { x, y } = evtPos(e);

    // Molette enfoncée : déplacer la vue, quel que soit l'outil.
    if (e.button === 1) {
      e.preventDefault();
      drag = { kind: 'pan', last: { x, y } };
      canvas.style.cursor = 'grabbing';
      return;
    }
    if (e.button !== 0) return;

    if (tool === 'select') {
      const h = cfg.canEdit ? hitHandle(x, y) : null;
      if (h) { checkpoint(); drag = h; return; }
      const ri = hitRoom(x, y);
      if (ri >= 0) {
        selected = ri;
        if (cfg.canEdit) {
          drag = { kind: 'room', i: ri, start: toWorldRaw(x, y), startScreen: { x, y }, moved: false, dx: 0, dy: 0, valid: true, target: -1 };
        }
        say(`${style_label(plan.rooms[ri])} : glisser pour déplacer, déposer sur une autre pièce pour l'échanger`);
        draw(false);
        return;
      }
      // Fond vide : on déplace la vue.
      selected = -1;
      drag = { kind: 'pan', last: { x, y } };
      canvas.style.cursor = 'grabbing';
      draw(false);
      return;
    }
    if (!cfg.canEdit) return;
    if (tool === 'room') {
      checkpoint();
      addRoomAt(x, y);
      markDirty();
      return;
    }
    if (tool === 'door' || tool === 'window') {
      const hit = hitWall(x, y);
      if (hit) {
        checkpoint();
        addOpening(tool, hit);
        markDirty();
      }
      return;
    }
    if (tool === 'delete') {
      const oi = hitOpening(x, y);
      if (oi >= 0) {
        checkpoint();
        plan.openings.splice(oi, 1);
        markDirty();
        return;
      }
      const ri = hitRoom(x, y);
      if (ri >= 0) {
        checkpoint();
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
        selected = -1;
        markDirty();
        return;
      }
      const wh = hitHandle(x, y) || hitWall(x, y);
      if (wh) {
        checkpoint();
        const wall = plan.walls[wh.i];
        plan.openings = plan.openings.filter((o) => o.wall_id !== wall.id);
        plan.walls.splice(wh.i, 1);
        markDirty();
      }
    }
  });

  canvas.addEventListener('mousemove', (e) => {
    const { x, y } = evtPos(e);

    if (!drag) {
      if (tool !== 'select' || !cfg.canEdit) return;
      const h = hitHandle(x, y);
      const ri = h ? -1 : hitRoom(x, y);
      const changed = ri !== hoverRoom || (h ? `${h.i}${h.end}` : '') !== (hoverHandleRef ? `${hoverHandleRef.i}${hoverHandleRef.end}` : '');
      hoverHandleRef = h;
      hoverRoom = ri;
      canvas.style.cursor = h ? 'crosshair' : (ri >= 0 ? 'grab' : 'default');
      if (changed) redraw();
      return;
    }

    if (drag.kind === 'pan') {
      ox += x - drag.last.x;
      oy += y - drag.last.y;
      drag.last = { x, y };
      userView = true;
      redraw();
      return;
    }

    if (drag.kind === 'wall') {
      const p = toWorld(x, y);
      const wall = plan.walls[drag.i];
      const other = drag.end === 'a' ? wall.b : wall.a;
      // snap orthogonal
      if (Math.abs(p.x - other.x) > Math.abs(p.y - other.y)) p.y = other.y;
      else p.x = other.x;
      moveWallEndpoint(wall, drag.end, p);
      redraw();
      say('Modifié');
      return;
    }

    if (drag.kind === 'room') {
      if (!drag.moved && Math.hypot(x - drag.startScreen.x, y - drag.startScreen.y) < 5) return;
      drag.moved = true;
      canvas.style.cursor = 'grabbing';
      const raw = toWorldRaw(x, y);
      const rawDx = raw.x - drag.start.x;
      const rawDy = raw.y - drag.start.y;
      const s = Edit.snapMove(plan, drag.i, rawDx, rawDy);
      drag.rawDx = rawDx;
      drag.rawDy = rawDy;
      drag.dx = s.dx;
      drag.dy = s.dy;
      drag.valid = Edit.canMove(plan, drag.i, s.dx, s.dy);
      drag.pointer = raw;
      drag.target = drag.valid ? -1 : Edit.roomAt(plan, raw, drag.i);
      redraw();
    }
  });

  function dropRoom() {
    const d = drag;
    if (!d.moved) return;
    const room = plan.rooms[d.i];
    const res = Edit.resolveDrop(plan, d.i, d.rawDx || 0, d.rawDy || 0, d.pointer || d.start);
    if (res.action === 'move') {
      checkpoint();
      Edit.translateRoom(plan, d.i, res.dx, res.dy, uid);
      drag = null;
      markDirty('Pièce déplacée');
    } else if (res.action === 'swap') {
      const other = plan.rooms[res.target];
      const names = `${style_label(room)} ⇄ ${style_label(other)}`;
      checkpoint();
      const areas = Edit.swapRooms(plan, d.i, res.target);
      drag = null;
      markDirty(`Pièces échangées : ${names} (${areas.a.toFixed(1)} et ${areas.b.toFixed(1)} m²). Ctrl+Z pour annuler`);
    } else {
      say('Déplacement impossible : chevauchement. Déposez sur une pièce pour l\'échanger.');
      drag = null;
      draw(false);
    }
  }

  window.addEventListener('mouseup', () => {
    if (!drag) return;
    const d = drag;
    if (d.kind === 'room') {
      dropRoom();
      canvas.style.cursor = 'grab';
      return;
    }
    drag = null;
    canvas.style.cursor = tool === 'select' ? 'default' : (tool === 'delete' ? 'not-allowed' : 'crosshair');
    if (d.kind === 'wall') markDirty();
  });

  // Échap annule un déplacement en cours ; les flèches déplacent la pièce sélectionnée de 10 cm (Maj : 50 cm).
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z' && cfg.canEdit
        && !(e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName))) {
      e.preventDefault();
      undo();
      return;
    }
    if (e.key === 'Escape' && drag && drag.kind === 'room') {
      drag = null;
      say('Déplacement annulé');
      draw(false);
      return;
    }
    if (!cfg.canEdit || tool !== 'select' || selected < 0 || !plan.rooms[selected]) return;
    if (e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
    const step = e.shiftKey ? 0.5 : GRID;
    const delta = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    if (!delta) return;
    e.preventDefault();
    if (Edit.canMove(plan, selected, delta[0], delta[1])) {
      checkpoint();
      Edit.translateRoom(plan, selected, delta[0], delta[1], uid);
      markDirty();
    } else {
      say('Déplacement impossible : chevauchement ou hors de la maison');
    }
  });

  // Molette : zoom centré sur le curseur.
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const { x, y } = evtPos(e);
    zoomAt(x, y, Math.exp(-e.deltaY * 0.0015));
  }, { passive: false });

  function zoomAt(x, y, factor) {
    const next = Math.min(fitScale * 6, Math.max(fitScale * 0.5, scale * factor));
    const k = next / scale;
    ox = x - (x - ox) * k;
    oy = y - (y - oy) * k;
    scale = next;
    userView = true;
    draw(false);
  }

  document.getElementById('btn-undo')?.addEventListener('click', undo);

  document.querySelectorAll('[data-zoom]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const mode = btn.dataset.zoom;
      if (mode === 'fit') { fitView(); draw(false); return; }
      zoomAt(W / 2, H / 2, mode === 'in' ? 1.25 : 0.8);
    });
  });

  canvas.addEventListener('contextmenu', (e) => e.preventDefault());

  // ---- outils ---------------------------------------------------------------------
  const toolBtns = [...document.querySelectorAll('.tool-btn')];
  toolBtns.forEach((btn) => { btn.dataset.base = btn.dataset.base || 'btn-line'; });
  function setTool(name) {
    tool = name;
    if (name !== 'select') { selected = -1; hoverRoom = -1; hoverHandleRef = null; }
    toolBtns.forEach((b) => {
      b.classList.remove('btn-dark', 'btn-line', 'btn-danger');
      b.classList.add(b.dataset.tool === name ? 'btn-dark' : (b.dataset.tool === 'delete' ? 'btn-danger' : 'btn-line'));
    });
    canvas.style.cursor = name === 'select' ? 'default' : (name === 'delete' ? 'not-allowed' : 'crosshair');
    draw(false);
  }
  toolBtns.forEach((btn) => btn.addEventListener('click', () => setTool(btn.dataset.tool)));

  // ---- sauvegarde -------------------------------------------------------------------
  let saving = false;
  async function save() {
    if (!cfg.canEdit || saving) return;
    const issue = topology();
    if (issue) {
      status.textContent = issue;
      return;
    }
    saving = true;
    const saveBtn = document.getElementById('btn-save');
    if (saveBtn) saveBtn.disabled = true;
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
      let data = {};
      try { data = await res.json(); } catch { /* réponse non-JSON */ }
      if (!res.ok) {
        status.textContent = data.error?.message || 'Erreur';
        return;
      }
      revisionId = data.id;
      status.textContent = `Enregistré v${data.version}`;
    } catch {
      status.textContent = 'Réseau indisponible';
    } finally {
      saving = false;
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  document.getElementById('btn-save')?.addEventListener('click', save);

  if (typeof ResizeObserver !== 'undefined' && canvas.parentElement) {
    let last = 0;
    new ResizeObserver(() => {
      const w = canvas.parentElement.clientWidth;
      if (Math.abs(w - last) > 1) { last = w; resize(); }
    }).observe(canvas.parentElement);
  }
  window.addEventListener('resize', resize);

  setTool('select');
  resize();
})();
