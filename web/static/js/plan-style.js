window.PlanStyle = (() => {
  const fills = {
    living: 'rgba(196, 148, 72, 0.55)',
    kitchen: 'rgba(248, 248, 246, 0.95)',
    bedroom: 'rgba(232, 214, 176, 0.85)',
    bathroom: 'rgba(210, 214, 216, 0.9)',
    hallway: 'rgba(220, 196, 150, 0.55)',
    garage: 'rgba(210, 210, 208, 0.95)',
    office: 'rgba(232, 214, 176, 0.85)',
    dining: 'rgba(196, 148, 72, 0.5)',
    storage: 'rgba(210, 210, 208, 0.9)',
    other: 'rgba(20, 83, 45, 0.08)',
  };
  const labels = {
    living: 'Séjour', kitchen: 'Cuisine', bedroom: 'Chambre', bathroom: 'SDB',
    hallway: 'Couloir', garage: 'Garage', office: 'Bureau', dining: 'Salle à manger',
    storage: 'Rangement', other: 'Pièce',
  };

  function label(room) {
    const name = (room && room.name) || '';
    const type = (room && room.type) || '';
    if (name && name !== type && name !== 'other' && name !== 'Pièce') return name;
    return labels[type] || name || 'Pièce';
  }
  function fill(room) {
    return fills[(room && room.type) || 'other'] || fills.other;
  }
  function box(poly) {
    const xs = poly.map((p) => p.x);
    const ys = poly.map((p) => p.y);
    return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
  }
  function m2px(toScreen) {
    const a = toScreen({ x: 0, y: 0 });
    const b = toScreen({ x: 1, y: 0 });
    return Math.hypot(b.x - a.x, b.y - a.y) || 40;
  }
  function hash(a, b) {
    let n = (a * 73856093) ^ (b * 19349663);
    n = (n << 13) ^ n;
    return ((n * (n * n * 15731 + 789221) + 1376312589) >>> 0) / 4294967296;
  }

  function roundRect(ctx, x, y, w, h, r) {
    const rr = Math.max(0, Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2));
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, w, h, rr);
    else {
      ctx.moveTo(x + rr, y);
      ctx.lineTo(x + w - rr, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + rr);
      ctx.lineTo(x + w, y + h - rr);
      ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
      ctx.lineTo(x + rr, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - rr);
      ctx.lineTo(x, y + rr);
      ctx.quadraticCurveTo(x, y, x + rr, y);
      ctx.closePath();
    }
  }

  function paint(ctx, fillStyle, stroke, lw) {
    if (fillStyle) { ctx.fillStyle = fillStyle; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw || 0.022; ctx.stroke(); }
  }

  function ovalShadow(ctx, w, d) {
    ctx.save();
    ctx.translate(0.05, 0.06);
    ctx.beginPath();
    ctx.ellipse(0, 0, w * 0.52, d * 0.48, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(28, 22, 14, 0.28)';
    ctx.fill();
    ctx.restore();
  }

  function sheen(ctx, x, y, rx, ry, a) {
    ctx.beginPath();
    ctx.ellipse(x, y, rx, ry, a || -0.5, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.22)';
    ctx.fill();
  }

  function beginItem(ctx, toScreen, px, py, rot) {
    const o = toScreen({ x: px, y: py });
    ctx.save();
    ctx.translate(o.x, o.y);
    ctx.rotate(((rot || 0) * Math.PI) / 180);
    ctx.scale(m2px(toScreen), m2px(toScreen));
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
  }

  /* ---- glyphes mobilier (mètres, origine au centre) ---- */
  function drawBed(ctx, w, d, dark) {
    ovalShadow(ctx, w, d);
    const frame = dark ? '#3d2e24' : '#c4a882';
    const edge = dark ? '#2a1e18' : '#8a6a48';
    const linen = dark ? '#3e4248' : '#f4efe6';
    const linenEdge = dark ? '#2a2e32' : '#d0c6b4';
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.08);
    paint(ctx, frame, edge, 0.024);
    roundRect(ctx, -w / 2 + 0.04, -d / 2 + 0.16, w - 0.08, d - 0.22, 0.07);
    paint(ctx, linen, linenEdge, 0.016);
    roundRect(ctx, -w / 2, -d / 2, w, 0.16, 0.03);
    paint(ctx, dark ? '#241c18' : '#b89a78', edge, 0.016);
    const pw = w * 0.26;
    const ph = 0.26;
    const py = -d / 2 + 0.38;
    [[-w * 0.22, py], [w * 0.22, py]].forEach(([x, y]) => {
      ctx.beginPath();
      ctx.ellipse(x, y, pw, ph, 0, 0, Math.PI * 2);
      paint(ctx, '#fbf8f2', '#d4cfc4', 0.014);
      sheen(ctx, x - 0.05, y - 0.04, pw * 0.42, ph * 0.38, -0.4);
      ctx.beginPath();
      ctx.moveTo(x - pw * 0.55, y);
      ctx.quadraticCurveTo(x, y + 0.05, x + pw * 0.55, y);
      ctx.strokeStyle = 'rgba(80,70,60,0.18)';
      ctx.lineWidth = 0.012;
      ctx.stroke();
    });
    ctx.beginPath();
    ctx.moveTo(-w / 2 + 0.1, 0.02);
    ctx.bezierCurveTo(-w * 0.15, 0.16, w * 0.15, -0.02, w / 2 - 0.1, 0.08);
    ctx.strokeStyle = dark ? 'rgba(255,255,255,0.14)' : 'rgba(90,70,50,0.28)';
    ctx.lineWidth = 0.022;
    ctx.stroke();
    roundRect(ctx, -w / 2 + 0.08, d / 2 - 0.46, w - 0.16, 0.3, 0.05);
    paint(ctx, dark ? '#4a4440' : '#e4d4b8', dark ? '#2e2a28' : '#c4b090', 0.012);
    sheen(ctx, -w * 0.12, d / 2 - 0.32, w * 0.18, 0.07, -0.3);
  }

  function drawCushion(ctx, x, y, w, h, fillCol, stroke) {
    roundRect(ctx, x, y, w, h, 0.08);
    paint(ctx, fillCol, stroke, 0.014);
    sheen(ctx, x + w * 0.28, y + h * 0.28, w * 0.18, h * 0.14, -0.4);
  }

  function drawSofa(ctx, w, d, lshape) {
    const chaise = lshape ? 0.72 : 0;
    ovalShadow(ctx, w, d + chaise);
    const fabric = '#5a5e66';
    const dark = '#3a3e44';
    const seat = '#6a6e76';
    roundRect(ctx, -w / 2, -d / 2, w, d + chaise, 0.12);
    paint(ctx, fabric, '#2a2e34', 0.022);
    roundRect(ctx, -w / 2, -d / 2, w, 0.2, 0.07);
    paint(ctx, dark, '#24282c', 0.014);
    roundRect(ctx, -w / 2, -d / 2, 0.18, d, 0.07);
    paint(ctx, dark, '#24282c', 0.014);
    roundRect(ctx, w / 2 - 0.18, -d / 2, 0.18, d + chaise, 0.07);
    paint(ctx, dark, '#24282c', 0.014);
    const seats = lshape ? 3 : 2;
    const innerW = w - 0.4;
    const seatH = d - 0.32;
    for (let i = 0; i < seats; i++) {
      const cw = innerW / seats - 0.04;
      drawCushion(ctx, -w / 2 + 0.22 + i * (innerW / seats), -d / 2 + 0.24, cw, seatH, seat, '#3e4248');
    }
    if (lshape) {
      roundRect(ctx, w / 2 - 1.02, -d / 2, 1.02, d + chaise, 0.12);
      paint(ctx, fabric, '#2a2e34', 0.022);
      roundRect(ctx, w / 2 - 0.18, -d / 2, 0.18, d + chaise, 0.07);
      paint(ctx, dark, '#24282c', 0.014);
      drawCushion(ctx, w / 2 - 0.92, d / 2 - 0.06, 0.7, chaise - 0.08, seat, '#3e4248');
    }
  }

  function drawArmchair(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.14);
    paint(ctx, '#6e4a30', '#3a2414', 0.02);
    roundRect(ctx, -w / 2, -d / 2, w, 0.16, 0.06);
    paint(ctx, '#54361c', '#3a2414', 0.014);
    roundRect(ctx, -w / 2, -d / 2, 0.12, d, 0.05);
    paint(ctx, '#54361c', '#3a2414', 0.012);
    roundRect(ctx, w / 2 - 0.12, -d / 2, 0.12, d, 0.05);
    paint(ctx, '#54361c', '#3a2414', 0.012);
    ctx.beginPath();
    ctx.ellipse(0, 0.06, w * 0.3, d * 0.24, 0, 0, Math.PI * 2);
    paint(ctx, '#8a6040', '#4a301c', 0.012);
    sheen(ctx, -0.06, -0.02, w * 0.12, d * 0.08, -0.4);
  }

  function drawDiningTable(ctx, w, d) {
    ovalShadow(ctx, w, d);
    ctx.beginPath();
    ctx.ellipse(0, 0, w / 2, d / 2, 0, 0, Math.PI * 2);
    paint(ctx, '#8a5828', '#5a3414', 0.024);
    ctx.beginPath();
    ctx.ellipse(0, 0, w / 2 - 0.06, d / 2 - 0.06, 0, 0, Math.PI * 2);
    paint(ctx, '#c48a48', '#8a5a28', 0.014);
    [0.22, 0.42, 0.62].forEach((k, i) => {
      ctx.beginPath();
      ctx.ellipse(0, 0, (w / 2) * k, (d / 2) * k, 0, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(90,50,18,${0.1 + i * 0.05})`;
      ctx.lineWidth = 0.012;
      ctx.stroke();
    });
    sheen(ctx, -w * 0.14, -d * 0.12, w * 0.2, d * 0.1, -0.5);
  }

  function drawChair(ctx, w, d) {
    ovalShadow(ctx, w * 0.9, d * 0.9);
    ctx.beginPath();
    ctx.ellipse(0, 0.06, w * 0.44, d * 0.36, 0, 0, Math.PI * 2);
    paint(ctx, '#ecc44a', '#b08a18', 0.016);
    sheen(ctx, -0.05, 0.0, w * 0.16, d * 0.1, -0.45);
    roundRect(ctx, -w * 0.36, -d / 2, w * 0.72, 0.11, 0.04);
    paint(ctx, '#d4a82e', '#8a6a14', 0.012);
    roundRect(ctx, -w * 0.32, -d / 2 - 0.02, w * 0.64, 0.05, 0.02);
    paint(ctx, '#c89822', '#7a5a10', 0.01);
  }

  function drawCoffee(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.08);
    paint(ctx, '#e8e4da', '#b8b4aa', 0.016);
    roundRect(ctx, -w / 2 + 0.05, -d / 2 + 0.05, w - 0.1, d - 0.1, 0.05);
    paint(ctx, '#faf8f4', '#d4cfc6', 0.01);
    sheen(ctx, -w * 0.12, -d * 0.08, w * 0.18, d * 0.1, -0.4);
    ctx.beginPath();
    ctx.arc(-w * 0.18, 0, 0.06, 0, Math.PI * 2);
    paint(ctx, 'rgba(180,80,50,0.35)', null);
    ctx.beginPath();
    ctx.arc(w * 0.12, 0.04, 0.045, 0, Math.PI * 2);
    paint(ctx, 'rgba(40,90,140,0.28)', null);
  }

  function drawCounter(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.03);
    paint(ctx, '#ece8e0', '#b8b4ac', 0.016);
    roundRect(ctx, -w / 2 + 0.02, -d / 2 + 0.02, w - 0.04, 0.07, 0.02);
    paint(ctx, '#d8d2c8', '#b0aaa0', 0.01);
    const nCab = Math.max(2, Math.round(w / 0.55));
    for (let i = 1; i < nCab; i++) {
      const x = -w / 2 + (w * i) / nCab;
      ctx.beginPath();
      ctx.moveTo(x, -d / 2 + 0.1);
      ctx.lineTo(x, d / 2 - 0.04);
      ctx.strokeStyle = 'rgba(140,136,128,0.55)';
      ctx.lineWidth = 0.012;
      ctx.stroke();
    }
    const sx = -w * 0.18;
    roundRect(ctx, sx - 0.24, -d / 2 + 0.16, 0.46, d - 0.26, 0.07);
    paint(ctx, '#c4d6de', '#7a98a4', 0.014);
    roundRect(ctx, sx + 0.26, -d / 2 + 0.16, 0.46, d - 0.26, 0.07);
    paint(ctx, '#c4d6de', '#7a98a4', 0.014);
    ctx.beginPath();
    ctx.arc(sx + 0.23, -d / 2 + 0.12, 0.032, 0, Math.PI * 2);
    paint(ctx, '#8a9096', '#4a5056', 0.01);
    ctx.beginPath();
    ctx.moveTo(sx + 0.23, -d / 2 + 0.12);
    ctx.lineTo(sx + 0.23, -d / 2 + 0.02);
    ctx.strokeStyle = '#6a7076';
    ctx.lineWidth = 0.016;
    ctx.stroke();
  }

  function drawStove(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.04);
    paint(ctx, '#2a2a2c', '#101012', 0.016);
    [[-0.15, -0.13, 0.11], [0.15, -0.13, 0.09], [-0.15, 0.13, 0.09], [0.15, 0.13, 0.11]].forEach(([x, y, r]) => {
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      paint(ctx, '#161618', '#6a6a70', 0.014);
      for (let k = 3; k >= 1; k--) {
        ctx.beginPath();
        ctx.arc(x, y, r * k / 4, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(160,160,168,0.45)';
        ctx.lineWidth = 0.008;
        ctx.stroke();
      }
    });
  }

  function drawNightstand(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.04);
    paint(ctx, '#7a5230', '#3e2818', 0.016);
    ctx.beginPath();
    ctx.moveTo(-w / 2 + 0.04, 0);
    ctx.lineTo(w / 2 - 0.04, 0);
    ctx.strokeStyle = '#4a321c';
    ctx.lineWidth = 0.012;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, -0.02, 0.075, 0, Math.PI * 2);
    paint(ctx, '#f0dc9c', '#c4a060', 0.012);
    ctx.beginPath();
    ctx.arc(0, -0.02, 0.035, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,248,210,0.75)';
    ctx.fill();
  }

  function drawWardrobe(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.03);
    paint(ctx, '#6e4e32', '#3a2818', 0.02);
    ctx.beginPath();
    ctx.moveTo(0, -d / 2 + 0.04);
    ctx.lineTo(0, d / 2 - 0.04);
    ctx.strokeStyle = '#3a2414';
    ctx.lineWidth = 0.018;
    ctx.stroke();
    [-0.09, 0.09].forEach((x) => {
      ctx.beginPath();
      ctx.arc(x, 0, 0.028, 0, Math.PI * 2);
      paint(ctx, '#d0ccc4', '#8a8680', 0.01);
    });
    sheen(ctx, -w * 0.18, -d * 0.12, w * 0.12, d * 0.08, -0.4);
  }

  function drawDesk(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.04);
    paint(ctx, '#3e3e42', '#1c1c20', 0.016);
    roundRect(ctx, -w / 2 + 0.06, -d / 2 + 0.08, w - 0.12, 0.04, 0.01);
    paint(ctx, '#2a2a2e', '#111114', 0.01);
    roundRect(ctx, w * 0.08, -d * 0.16, 0.32, 0.22, 0.02);
    paint(ctx, '#16161a', '#08080c', 0.01);
    roundRect(ctx, w * 0.12, -d * 0.12, 0.24, 0.14, 0.01);
    paint(ctx, '#1e3a52', '#0c1c28', 0.008);
  }

  function drawFireplace(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.04);
    paint(ctx, '#4a4644', '#1c1a18', 0.02);
    roundRect(ctx, -w / 2 + 0.08, -d / 2 + 0.1, w - 0.16, d - 0.2, 0.03);
    paint(ctx, '#2a2220', '#0c0808', 0.012);
    ctx.beginPath();
    ctx.ellipse(0, d / 2 - 0.22, 0.14, 0.09, 0, 0, Math.PI * 2);
    ctx.fillStyle = '#c44a22';
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(0, d / 2 - 0.26, 0.07, 0.06, 0, 0, Math.PI * 2);
    ctx.fillStyle = '#f0c040';
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(-0.04, d / 2 - 0.28, 0.03, 0.04, 0, 0, Math.PI * 2);
    ctx.fillStyle = '#fff4c0';
    ctx.fill();
  }

  function drawBathtub(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, Math.min(w, d) * 0.32);
    paint(ctx, '#f6f6f4', '#b0b0b4', 0.022);
    roundRect(ctx, -w / 2 + 0.1, -d / 2 + 0.1, w - 0.2, d - 0.2, Math.min(w, d) * 0.26);
    paint(ctx, '#c8dde6', '#8aa8b4', 0.014);
    sheen(ctx, -w * 0.12, -d * 0.08, w * 0.22, d * 0.12, -0.4);
    ctx.beginPath();
    ctx.arc(w / 2 - 0.22, 0, 0.04, 0, Math.PI * 2);
    paint(ctx, '#8a8e92', '#5a5e62', 0.01);
    ctx.beginPath();
    ctx.arc(-w / 2 + 0.18, 0, 0.032, 0, Math.PI * 2);
    paint(ctx, '#c8ccd0', '#8a8e92', 0.01);
  }

  function drawToilet(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, 0.2, 0.03);
    paint(ctx, '#f2f2f0', '#b8b8bc', 0.014);
    ctx.beginPath();
    ctx.ellipse(0, 0.1, w * 0.44, d * 0.38, 0, 0, Math.PI * 2);
    paint(ctx, '#f8f8f6', '#b8b8bc', 0.016);
    ctx.beginPath();
    ctx.ellipse(0, 0.12, w * 0.24, d * 0.2, 0, 0, Math.PI * 2);
    paint(ctx, '#dce6ea', '#a0a8ac', 0.012);
  }

  function drawSink(ctx, w, d) {
    ovalShadow(ctx, w, d);
    ctx.beginPath();
    ctx.ellipse(0, 0.05, w * 0.44, d * 0.4, 0, 0, Math.PI * 2);
    paint(ctx, '#f6f6f4', '#b8b8bc', 0.016);
    ctx.beginPath();
    ctx.ellipse(0, 0.07, w * 0.28, d * 0.24, 0, 0, Math.PI * 2);
    paint(ctx, '#d0e0e6', '#90a4ac', 0.012);
    roundRect(ctx, -0.04, -d / 2, 0.08, 0.14, 0.02);
    paint(ctx, '#c8ccd0', '#8a8e92', 0.01);
    ctx.beginPath();
    ctx.arc(0, -d / 2 + 0.04, 0.025, 0, Math.PI * 2);
    paint(ctx, '#9aa0a4', '#5a6064', 0.008);
  }

  function drawCar(ctx, w, d) {
    ovalShadow(ctx, w, d);
    ctx.beginPath();
    ctx.moveTo(-w / 2 + 0.18, -d / 2);
    ctx.lineTo(w / 2 - 0.35, -d / 2);
    ctx.quadraticCurveTo(w / 2, -d / 2, w / 2, -d / 2 + 0.28);
    ctx.lineTo(w / 2, d / 2 - 0.28);
    ctx.quadraticCurveTo(w / 2, d / 2, w / 2 - 0.35, d / 2);
    ctx.lineTo(-w / 2 + 0.18, d / 2);
    ctx.quadraticCurveTo(-w / 2, d / 2, -w / 2, d / 2 - 0.22);
    ctx.lineTo(-w / 2, -d / 2 + 0.22);
    ctx.quadraticCurveTo(-w / 2, -d / 2, -w / 2 + 0.18, -d / 2);
    ctx.closePath();
    paint(ctx, '#ececea', '#9a9aa0', 0.02);
    roundRect(ctx, -w * 0.16, -d / 2 + 0.14, w * 0.4, d - 0.28, 0.14);
    paint(ctx, '#7aa0b4', '#4a7084', 0.014);
    roundRect(ctx, -w * 0.08, -d / 2 + 0.22, w * 0.16, d - 0.44, 0.05);
    ctx.fillStyle = 'rgba(255,255,255,0.28)';
    ctx.fill();
    [[-w / 2 + 0.38, -d / 2 - 0.04], [w / 2 - 0.72, -d / 2 - 0.04],
     [-w / 2 + 0.38, d / 2 - 0.08], [w / 2 - 0.72, d / 2 - 0.08]].forEach(([x, y]) => {
      roundRect(ctx, x, y, 0.38, 0.12, 0.04);
      paint(ctx, '#1c1c1e', '#08080a', 0.01);
    });
    ctx.beginPath();
    ctx.ellipse(-w / 2 + 0.1, -d * 0.22, 0.07, 0.05, 0, 0, Math.PI * 2);
    ctx.fillStyle = '#f4e890';
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(-w / 2 + 0.1, d * 0.22, 0.07, 0.05, 0, 0, Math.PI * 2);
    ctx.fillStyle = '#f4e890';
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(w / 2 - 0.12, -d * 0.2, 0.05, 0.04, 0, 0, Math.PI * 2);
    ctx.fillStyle = '#e07060';
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(w / 2 - 0.12, d * 0.2, 0.05, 0.04, 0, 0, Math.PI * 2);
    ctx.fillStyle = '#e07060';
    ctx.fill();
  }

  function drawRug(ctx, w, d) {
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.06);
    paint(ctx, '#c45a3a', '#8a3820', 0.02);
    roundRect(ctx, -w / 2 + 0.08, -d / 2 + 0.08, w - 0.16, d - 0.16, 0.04);
    paint(ctx, '#d4784c', '#a04828', 0.012);
    roundRect(ctx, -w / 2 + 0.16, -d / 2 + 0.16, w - 0.32, d - 0.32, 0.03);
    ctx.fillStyle = 'rgba(255,220,180,0.18)';
    ctx.fill();
  }

  function drawPlant(ctx, w, d) {
    ovalShadow(ctx, w * 0.7, d * 0.7);
    ctx.beginPath();
    ctx.ellipse(0, 0.08, w * 0.28, d * 0.22, 0, 0, Math.PI * 2);
    paint(ctx, '#8a5a32', '#5a3818', 0.014);
    [[-0.08, -0.1, 0.16], [0.1, -0.12, 0.18], [0.0, -0.18, 0.14], [-0.12, 0.0, 0.12], [0.12, 0.02, 0.13]].forEach(([x, y, r], i) => {
      ctx.beginPath();
      ctx.ellipse(x, y, r, r * 0.85, i * 0.4, 0, Math.PI * 2);
      paint(ctx, i % 2 ? '#4a8a2c' : '#2e6a1c', '#1e4a10', 0.01);
    });
  }

  function drawFridge(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.04);
    paint(ctx, '#e8ecee', '#a8b0b4', 0.016);
    ctx.beginPath();
    ctx.moveTo(-w / 2 + 0.04, 0.02);
    ctx.lineTo(w / 2 - 0.04, 0.02);
    ctx.strokeStyle = '#b0b8bc';
    ctx.lineWidth = 0.014;
    ctx.stroke();
    roundRect(ctx, w / 2 - 0.1, -d / 2 + 0.12, 0.05, 0.18, 0.015);
    paint(ctx, '#c8ced2', '#8a9094', 0.008);
    roundRect(ctx, w / 2 - 0.1, d / 2 - 0.32, 0.05, 0.18, 0.015);
    paint(ctx, '#c8ced2', '#8a9094', 0.008);
  }

  function drawTv(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.03);
    paint(ctx, '#3a322c', '#1c1814', 0.016);
    roundRect(ctx, -w / 2 + 0.12, -d / 2 + 0.04, w - 0.24, 0.1, 0.015);
    paint(ctx, '#121416', '#08080a', 0.01);
    ctx.beginPath();
    ctx.moveTo(-w / 2 + 0.4, -d / 2);
    ctx.lineTo(-w / 2 + 0.4, d / 2);
    ctx.strokeStyle = 'rgba(20,16,12,0.4)';
    ctx.lineWidth = 0.012;
    ctx.stroke();
  }

  function drawGeneric(ctx, w, d) {
    ovalShadow(ctx, w, d);
    roundRect(ctx, -w / 2, -d / 2, w, d, 0.06);
    paint(ctx, '#c8b8a4', '#6a5a48', 0.016);
  }

  const DRAWERS = {
    'sofa.lshape': (ctx, w, d) => drawSofa(ctx, w, d, true),
    'sofa.2seat': (ctx, w, d) => drawSofa(ctx, w, d, false),
    armchair: drawArmchair,
    'table.dining': drawDiningTable,
    'chair.dining': drawChair,
    'table.coffee': drawCoffee,
    'counter.kitchen': drawCounter,
    stove: drawStove,
    nightstand: drawNightstand,
    wardrobe: drawWardrobe,
    desk: drawDesk,
    fireplace: drawFireplace,
    bathtub: drawBathtub,
    toilet: drawToilet,
    'sink.basin': drawSink,
    sink: drawSink,
    'car.sedan': drawCar,
    'rug.rect': drawRug,
    'plant.pot': drawPlant,
    fridge: drawFridge,
    'tv.console': drawTv,
  };

  function drawFurniture(ctx, items, toScreen) {
    const list = (items || []).slice().sort((a, b) => {
      const za = (a.catalog_id || '').startsWith('rug') ? 0 : 1;
      const zb = (b.catalog_id || '').startsWith('rug') ? 0 : 1;
      return za - zb;
    });
    list.forEach((it) => {
      const w = (it.size_m && it.size_m.w) || 0.5;
      const d = (it.size_m && it.size_m.d) || 0.5;
      const rot = it.rotation_deg || 0;
      const px = it.position && it.position.x;
      const py = it.position && it.position.y;
      if (typeof px !== 'number' || typeof py !== 'number') return;
      const cid = it.catalog_id || '';
      beginItem(ctx, toScreen, px, py, rot);
      if (cid.startsWith('bed.')) drawBed(ctx, w, d, cid.endsWith('double') && w >= 1.4);
      else if (DRAWERS[cid]) DRAWERS[cid](ctx, w, d);
      else drawGeneric(ctx, w, d);
      ctx.restore();
    });
  }

  function drawTree(ctx, x, y, r) {
    ctx.beginPath();
    ctx.arc(x + 2, y + 3, r, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(30,50,16,0.22)';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = '#3a6a22';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x - r * 0.28, y - r * 0.22, r * 0.58, 0, Math.PI * 2);
    ctx.fillStyle = '#5a9434';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x + r * 0.18, y - r * 0.08, r * 0.42, 0, Math.PI * 2);
    ctx.fillStyle = '#6eaa44';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x, y + r * 0.12, r * 0.12, 0, Math.PI * 2);
    ctx.fillStyle = '#6a4828';
    ctx.fill();
  }

  function drawSite(ctx, bw, bd, toScreen, canvasW, canvasH) {
    const g = ctx.createLinearGradient(0, 0, canvasW, canvasH);
    g.addColorStop(0, '#6e9a44');
    g.addColorStop(0.45, '#5e8a38');
    g.addColorStop(1, '#4e7630');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, canvasW, canvasH);
    for (let i = 0; i < 420; i++) {
      const x = hash(i, 3) * canvasW;
      const y = hash(i, 7) * canvasH;
      const s = 4 + hash(i, 11) * 10;
      ctx.fillStyle = hash(i, 13) > 0.5 ? 'rgba(70,110,36,0.22)' : 'rgba(190,220,90,0.12)';
      ctx.beginPath();
      ctx.ellipse(x, y, s, s * 0.7, hash(i, 17) * 3, 0, Math.PI * 2);
      ctx.fill();
    }
    const origin = toScreen({ x: 0, y: 0 });
    const end = toScreen({ x: bw, y: bd });
    [[end.x + 38, (origin.y + end.y) * 0.35, 22],
     [end.x + 70, (origin.y + end.y) * 0.62, 28],
     [(origin.x + end.x) * 0.22, end.y + 48, 20],
     [(origin.x + end.x) * 0.55, end.y + 58, 26],
     [(origin.x + end.x) * 0.82, end.y + 42, 18]].forEach(([x, y, r]) => drawTree(ctx, x, y, r));
    ctx.strokeStyle = 'rgba(70,110,40,0.55)';
    ctx.lineWidth = 7;
    ctx.beginPath();
    ctx.moveTo(end.x + 10, origin.y + 8);
    ctx.lineTo(end.x + 10, end.y + 8);
    ctx.lineTo(origin.x, end.y + 10);
    ctx.stroke();
    ctx.font = 'italic 13px Georgia, serif';
    ctx.fillStyle = 'rgba(40,64,22,0.8)';
    ctx.fillText('Jardin', end.x + 22, (origin.y + end.y) / 2);
    ctx.fillText('Jardin', (origin.x + end.x) / 2 - 18, end.y + 32);
  }

  function woodPlanks(ctx, a, b, sc, tones) {
    const ph = 0.135 * sc;
    const pw = 0.88 * sc;
    let row = 0;
    ctx.strokeStyle = 'rgba(80,50,20,0.22)';
    ctx.lineWidth = 0.7;
    for (let y = a.y; y < b.y; y += ph) {
      const off = (row % 2) * pw * 0.38;
      let col = 0;
      for (let x = a.x - off; x < b.x; x += pw) {
        ctx.fillStyle = tones[(row * 3 + col) % tones.length];
        const x0 = Math.max(x, a.x);
        const x1 = Math.min(x + pw - 0.8, b.x);
        if (x1 > x0) {
          ctx.fillRect(x0, y, x1 - x0, Math.min(ph - 0.6, b.y - y));
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
    if (type === 'living' || type === 'dining' || type === 'hallway') {
      ctx.fillStyle = '#c49448';
      ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
      woodPlanks(ctx, a, b, sc, ['#c49448', '#b48238', '#d0a456', '#a87830', '#c89a50']);
    } else if (type === 'bedroom' || type === 'office') {
      ctx.fillStyle = '#e4d2ae';
      ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
      woodPlanks(ctx, a, b, sc, ['#e8d4b0', '#decaa4', '#f0e0c0', '#d4be98', '#ead8b4']);
    } else if (type === 'kitchen') {
      ctx.fillStyle = '#d8d4cc';
      ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
      const step = 0.38 * sc;
      const grout = 1.6;
      for (let x = a.x, col = 0; x < b.x; x += step, col++) {
        for (let y = a.y, row = 0; y < b.y; y += step, row++) {
          ctx.fillStyle = (row + col) % 2 === 0 ? '#f6f4ee' : '#e8e4dc';
          ctx.fillRect(x + grout, y + grout, step - grout * 2, step - grout * 2);
        }
      }
    } else if (type === 'bathroom' || type === 'wc' || type === 'laundry') {
      ctx.fillStyle = '#c8ced2';
      ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
      const step = 0.22 * sc;
      for (let x = a.x, col = 0; x < b.x; x += step, col++) {
        for (let y = a.y, row = 0; y < b.y; y += step, row++) {
          ctx.fillStyle = (row + col) % 2 === 0 ? '#e4eaee' : '#d0d8dc';
          ctx.fillRect(x + 1, y + 1, step - 2, step - 2);
        }
      }
    } else if (type === 'garage' || type === 'storage') {
      ctx.fillStyle = '#c8c8c4';
      ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
      ctx.strokeStyle = 'rgba(120,120,116,0.45)';
      ctx.lineWidth = 1.2;
      const step = 1.4 * sc;
      for (let x = a.x; x < b.x; x += step) {
        ctx.beginPath(); ctx.moveTo(x, a.y); ctx.lineTo(x, b.y); ctx.stroke();
      }
      for (let y = a.y; y < b.y; y += step) {
        ctx.beginPath(); ctx.moveTo(a.x, y); ctx.lineTo(b.x, y); ctx.stroke();
      }
      ctx.fillStyle = 'rgba(255,255,255,0.08)';
      ctx.fillRect(a.x, a.y, (b.x - a.x) * 0.35, b.y - a.y);
    } else {
      ctx.fillStyle = fill(room);
      ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
    }
    ctx.restore();
  }

  function drawFixtures(ctx, room, toScreen) {
    drawFloor(ctx, room, toScreen);
  }

  function drawWalls(ctx, walls, toScreen, scale) {
    (walls || []).forEach((wall) => {
      const a = toScreen(wall.a);
      const b = toScreen(wall.b);
      const t = Math.max(5, (wall.thickness_m || 0.2) * scale);
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len = Math.hypot(dx, dy) || 1;
      const nx = (-dy / len) * (t / 2);
      const ny = (dx / len) * (t / 2);
      ctx.beginPath();
      ctx.moveTo(a.x + nx, a.y + ny);
      ctx.lineTo(b.x + nx, b.y + ny);
      ctx.lineTo(b.x - nx, b.y - ny);
      ctx.lineTo(a.x - nx, a.y - ny);
      ctx.closePath();
      ctx.fillStyle = '#8a8a84';
      ctx.fill();
      ctx.strokeStyle = '#5c5c58';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.save();
      ctx.clip();
      ctx.strokeStyle = 'rgba(70,70,66,0.28)';
      ctx.lineWidth = 1;
      const minX = Math.min(a.x, b.x) - t;
      const maxX = Math.max(a.x, b.x) + t;
      const minY = Math.min(a.y, b.y) - t;
      const maxY = Math.max(a.y, b.y) + t;
      for (let x = minX - (maxY - minY); x < maxX + 20; x += 6) {
        ctx.beginPath();
        ctx.moveTo(x, minY);
        ctx.lineTo(x + (maxY - minY), maxY);
        ctx.stroke();
      }
      ctx.restore();
    });
  }

  function drawPorch(ctx, openings, walls, depth, toScreen) {
    const south = (openings || []).find((o) => o.type === 'door' && o.wall_id === 'w_outer_3');
    const wall = (walls || []).find((w) => w.id === 'w_outer_3');
    if (!south || !wall) return;
    const len = Math.hypot(wall.b.x - wall.a.x, wall.b.y - wall.a.y) || 1;
    const t0 = (south.offset_m || 0) / len;
    const t1 = ((south.offset_m || 0) + (south.width_m || 0.9)) / len;
    const x0 = wall.a.x + (wall.b.x - wall.a.x) * t0 - 0.45;
    const x1 = wall.a.x + (wall.b.x - wall.a.x) * t1 + 0.45;
    const a = toScreen({ x: x0, y: depth });
    const b = toScreen({ x: x1, y: depth + 1.25 });
    const sc = m2px(toScreen);
    ctx.fillStyle = '#b48a52';
    ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
    ctx.strokeStyle = '#7a5428';
    ctx.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);
    ctx.strokeStyle = 'rgba(90,60,28,0.4)';
    for (let y = a.y; y < b.y; y += 0.15 * sc) {
      ctx.beginPath(); ctx.moveTo(a.x, y); ctx.lineTo(b.x, y); ctx.stroke();
    }
  }

  function drawOpenings(ctx, openings, walls, toScreen, scale) {
    (openings || []).forEach((op) => {
      const wall = (walls || []).find((w) => w.id === op.wall_id);
      if (!wall) return;
      const len = Math.hypot(wall.b.x - wall.a.x, wall.b.y - wall.a.y) || 1;
      const w2 = op.width_m || 0.9;
      const t0 = Math.min(1, Math.max(0, (op.offset_m || 0) / len));
      const t1 = Math.min(1, Math.max(0, ((op.offset_m || 0) + w2) / len));
      const p0 = toScreen({
        x: wall.a.x + (wall.b.x - wall.a.x) * t0,
        y: wall.a.y + (wall.b.y - wall.a.y) * t0,
      });
      const p1 = toScreen({
        x: wall.a.x + (wall.b.x - wall.a.x) * t1,
        y: wall.a.y + (wall.b.y - wall.a.y) * t1,
      });
      const thick = Math.max(6, (wall.thickness_m || 0.2) * scale + 3);
      ctx.lineCap = 'butt';
      ctx.strokeStyle = '#f2f2ee';
      ctx.lineWidth = thick;
      ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y); ctx.stroke();
      if (op.type === 'window') {
        ctx.strokeStyle = '#7eb4d0';
        ctx.lineWidth = Math.max(2.5, thick * 0.38);
        ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y); ctx.stroke();
        ctx.strokeStyle = '#ecece8';
        ctx.lineWidth = 1.4;
        const mx = (p0.x + p1.x) / 2;
        const my = (p0.y + p1.y) / 2;
        const dx = p1.x - p0.x;
        const dy = p1.y - p0.y;
        const n = Math.hypot(dx, dy) || 1;
        ctx.beginPath();
        ctx.moveTo(mx - (dy / n) * thick * 0.35, my + (dx / n) * thick * 0.35);
        ctx.lineTo(mx + (dy / n) * thick * 0.35, my - (dx / n) * thick * 0.35);
        ctx.stroke();
      } else {
        const ang = Math.atan2(p1.y - p0.y, p1.x - p0.x);
        const r = w2 * scale;
        ctx.strokeStyle = '#c4a06a';
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.arc(p0.x, p0.y, r, ang, ang + Math.PI / 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y);
        ctx.lineTo(p0.x + Math.cos(ang + Math.PI / 2) * r, p0.y + Math.sin(ang + Math.PI / 2) * r);
        ctx.stroke();
      }
    });
  }

  return {
    fills, labels, label, fill, drawFixtures, drawFurniture,
    drawFloor, drawSite, drawPorch, drawOpenings, drawWalls,
  };
})();
