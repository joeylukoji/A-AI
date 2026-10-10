// Room floor materials. Geometry helpers and the fallback fill are injected by PlanStyle.
window.PlanStyleFloors = ({ box, m2px, fill }) => {
  function woodPlanks(ctx, a, b, sc, tones) {
    const ph = 0.2 * sc;
    const pw = 1.4 * sc;
    let row = 0;
    ctx.strokeStyle = 'rgba(127,99,64,0.22)';
    ctx.lineWidth = 0.45;
    for (let y = a.y; y < b.y; y += ph) {
      const off = (row % 2) * pw * 0.38;
      let col = 0;
      for (let x = a.x - off; x < b.x; x += pw) {
        ctx.fillStyle = tones[(row * 3 + col) % tones.length];
        const x0 = Math.max(x, a.x);
        const x1 = Math.min(x + pw - 0.45, b.x);
        if (x1 > x0) {
          ctx.fillRect(x0, y, x1 - x0, Math.min(ph - 0.45, b.y - y));
          ctx.beginPath();
          ctx.moveTo(x0, y);
          ctx.lineTo(x1, y);
          ctx.stroke();
        }
        col += 1;
      }
      row += 1;
    }
  }

  function tileGrid(ctx, a, b, step, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.55;
    ctx.beginPath();
    for (let x = a.x; x <= b.x + 0.5; x += step) { ctx.moveTo(x, a.y); ctx.lineTo(x, b.y); }
    for (let y = a.y; y <= b.y + 0.5; y += step) { ctx.moveTo(a.x, y); ctx.lineTo(b.x, y); }
    ctx.stroke();
  }

  function crossHatch(ctx, a, b, step, color) {
    const height = b.y - a.y;
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.45;
    ctx.beginPath();
    for (let x = a.x - height; x <= b.x + height; x += step) {
      ctx.moveTo(x, a.y);
      ctx.lineTo(x + height, b.y);
      ctx.moveTo(x, b.y);
      ctx.lineTo(x + height, a.y);
    }
    ctx.stroke();
  }

  function drawFloor(ctx, room, toScreen) {
    if (!room.polygon || room.polygon.length < 3) return;
    const type = room.type || '';
    const { x0, y0, x1, y1 } = box(room.polygon);
    ctx.save();
    ctx.beginPath();
    room.polygon.forEach((p, i) => {
      const s = toScreen(p);
      if (i === 0) ctx.moveTo(s.x, s.y); else ctx.lineTo(s.x, s.y);
    });
    ctx.closePath();
    ctx.clip();
    const a = toScreen({ x: x0, y: y0 });
    const b = toScreen({ x: x1, y: y1 });
    const sc = m2px(toScreen);
    const flat = (color) => { ctx.fillStyle = color; ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y); };
    flat(fill(room));
    if (type === 'bedroom' || type === 'office') {
      woodPlanks(ctx, a, b, sc, ['#e6d4b7', '#e0ccac', '#eadac1', '#e4d1b2']);
    } else if (type === 'living' || type === 'dining') {
      crossHatch(ctx, a, b, 0.85 * sc, 'rgba(116,123,116,0.17)');
    } else if (type === 'hallway') {
      crossHatch(ctx, a, b, 0.85 * sc, 'rgba(116,123,116,0.13)');
    } else if (type === 'kitchen') {
      tileGrid(ctx, a, b, 0.75 * sc, 'rgba(104,125,118,0.2)');
    } else if (type === 'bathroom' || type === 'wc' || type === 'laundry') {
      tileGrid(ctx, a, b, 0.45 * sc, 'rgba(89,127,141,0.18)');
    } else if (type === 'garage') {
      tileGrid(ctx, a, b, 1.2 * sc, 'rgba(115,127,126,0.14)');
    }
    ctx.restore();
  }

  return { drawFloor };
};
