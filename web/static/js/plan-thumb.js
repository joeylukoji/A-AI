// Renders a PlanDocument thumbnail onto <canvas id="plan-thumb"> from the JSON
// embedded in <script type="application/json" id="plan-thumb-data">, and fills
// <ul id="room-legend"> with the room colour legend.
//
// Extracted from the inline script in project.html so the admin plan detail
// page can draw the same thumbnail without duplicating the drawing code.
// Optional companions, used when present: window.PlanStyle (colours, walls,
// furniture) and window.PlanCompliance (score + dimensions panels).
(function () {
  const dataEl = document.getElementById('plan-thumb-data');
  if (!dataEl) return;

  let plan;
  try {
    plan = JSON.parse(dataEl.textContent || '{}');
  } catch {
    return;
  }

  const style = window.PlanStyle;

  if (window.PlanCompliance) {
    window.PlanCompliance.render(plan, document.getElementById('compliance-score'));
    window.PlanCompliance.renderDimensions(plan, document.getElementById('plan-dimensions'));
  }

  // Room names come from user-editable plan data, so they must never be
  // interpolated into HTML unescaped (stored XSS).
  const escapeHtml = (value) => String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  const legend = document.getElementById('room-legend');
  if (legend && style) {
    legend.innerHTML = (plan.rooms || []).map((room) => (
      `<li class="flex items-center gap-2"><span class="inline-block w-3 h-3 rounded-sm border border-zinc-400" style="background:${escapeHtml(style.fill(room))}"></span>${escapeHtml(style.label(room))}</li>`
    )).join('');
  }

  const canvas = document.getElementById('plan-thumb');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const scale = 24;
  const pad = 28;
  const bounds = (plan.floor && plan.floor.bounds) || {};
  const bw = bounds.width || 12;
  const bd = bounds.depth || 10;
  const toScreen = (p) => ({ x: pad + p.x * scale, y: pad + p.y * scale });

  if (style && style.drawSite) {
    style.drawSite(ctx, bw, bd, toScreen, canvas.width, canvas.height);
  } else {
    ctx.fillStyle = '#f7f4ef';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  const hasFurniture = (plan.furniture || []).length > 0;
  (plan.rooms || []).forEach((room) => {
    if (!room.polygon || room.polygon.length < 3) return;
    if (style && style.drawFloor) style.drawFloor(ctx, room, toScreen);
    if (style && !hasFurniture) style.drawFixtures(ctx, room, toScreen);
  });
  if (style && hasFurniture) style.drawFurniture(ctx, plan.furniture, toScreen);
  if (style && style.drawPorch) style.drawPorch(ctx, plan.openings, plan.walls, bd, toScreen);

  if (style && style.drawWalls) {
    style.drawWalls(ctx, plan.walls, toScreen, scale);
  } else {
    (plan.walls || []).forEach((w) => {
      ctx.beginPath();
      ctx.moveTo(pad + w.a.x * scale, pad + w.a.y * scale);
      ctx.lineTo(pad + w.b.x * scale, pad + w.b.y * scale);
      ctx.strokeStyle = '#585856';
      ctx.lineWidth = 3;
      ctx.stroke();
    });
  }
  if (style && style.drawOpenings) style.drawOpenings(ctx, plan.openings, plan.walls, toScreen, scale);

  (plan.rooms || []).forEach((room) => {
    if (!room.polygon || room.polygon.length < 3) return;
    const centroid = room.polygon.reduce((a, p) => ({ x: a.x + p.x, y: a.y + p.y }), { x: 0, y: 0 });
    centroid.x /= room.polygon.length;
    centroid.y /= room.polygon.length;
    const text = style ? style.label(room) : (room.name || room.type || '');
    ctx.fillStyle = '#1c1917';
    ctx.font = 'bold 11px sans-serif';
    ctx.fillText(text, pad + centroid.x * scale - ctx.measureText(text).width / 2, pad + centroid.y * scale);
  });
})();
