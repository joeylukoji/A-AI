window.PlanStyle = (() => {
  const fills = {
    living: 'rgb(231, 228, 222)',
    kitchen: 'rgb(236, 235, 231)',
    bedroom: 'rgb(236, 223, 198)',
    bathroom: 'rgb(213, 226, 234)', wc: 'rgb(213, 226, 234)', laundry: 'rgb(213, 226, 234)',
    hallway: 'rgb(225, 222, 215)',
    garage: 'rgb(211, 211, 207)',
    office: 'rgb(236, 223, 198)',
    dining: 'rgb(231, 228, 222)',
    storage: 'rgb(221, 219, 214)',
    other: 'rgba(20, 83, 45, 0.08)',
  };
  const labels = {
    living: 'Séjour', kitchen: 'Cuisine', bedroom: 'Chambre', bathroom: 'SDB',
    hallway: 'Couloir', garage: 'Garage', office: 'Bureau', dining: 'Salle à manger',
    storage: 'Rangement', wc: 'WC', laundry: 'Buanderie', other: 'Pièce',
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

  // Mobilier « plan d'architecte » : aplats clairs et trait fin uniforme, sans ombres ni reflets.
  // Toutes les couleurs des symboles passent par `paint` : on les éclaircit ici, une fois.
  function soft(color) {
    const m = /^#([0-9a-f]{6})$/i.exec(color || '');
    if (!m) return color;
    const n = parseInt(m[1], 16);
    const mix = (c) => Math.round(c + (255 - c) * 0.55);
    return `rgb(${mix((n >> 16) & 255)}, ${mix((n >> 8) & 255)}, ${mix(n & 255)})`;
  }
  const LINE = '#77746e';

  function paint(ctx, fillStyle, stroke, lw) {
    if (fillStyle) { ctx.fillStyle = soft(fillStyle); ctx.fill(); }
    if (stroke) { ctx.strokeStyle = LINE; ctx.lineWidth = Math.max(lw || 0.022, 0.018); ctx.stroke(); }
  }

  function ovalShadow() { /* volontairement vide : pas d'ombre portée sur un plan */ }

  function sheen() { /* volontairement vide : pas de reflet sur un plan */ }

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
      if (cid.startsWith('bed.')) drawBed(ctx, w, d, false);
      else if (DRAWERS[cid]) DRAWERS[cid](ctx, w, d);
      else drawGeneric(ctx, w, d);
      ctx.restore();
    });
  }

  // Palette « plan d'architecte » : papier clair, murs pleins gris foncé, sols pâles.
  const PAPER = '#fbfaf7';
  const GAP = '#f6f5f1';
  const INK = '#2f2f2d';
  const WALL = '#4b4b48';

  function drawSite(ctx, bw, bd, toScreen, canvasW, canvasH) {
    ctx.fillStyle = PAPER;
    ctx.fillRect(0, 0, canvasW, canvasH);
  }

  function fmtM(v) {
    return v.toFixed(1).replace('.', ',');
  }

  // Cotes extérieures : largeur sous la maison, profondeur à gauche (traits d'attache + ticks à 45°).
  function drawDimensions(ctx, bw, bd, toScreen) {
    const sc = m2px(toScreen);
    const a = toScreen({ x: 0, y: 0 });
    const b = toScreen({ x: bw, y: bd });
    const off = Math.min(0.95 * sc, 46);
    const gap = Math.min(0.18 * sc, 8);
    const tick = 4;
    ctx.save();
    ctx.strokeStyle = '#8b8b86';
    ctx.fillStyle = '#4a4a47';
    ctx.lineWidth = 1;
    ctx.font = '500 11px "DM Sans", system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const seg = (x0, y0, x1, y1) => { ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); };
    // largeur (bas)
    const yy = b.y + off;
    seg(a.x, b.y + gap, a.x, yy + 5);
    seg(b.x, b.y + gap, b.x, yy + 5);
    seg(a.x, yy, b.x, yy);
    seg(a.x - tick, yy + tick, a.x + tick, yy - tick);
    seg(b.x - tick, yy + tick, b.x + tick, yy - tick);
    const wt = `${fmtM(bw)} m`;
    const ww = ctx.measureText(wt).width + 10;
    ctx.fillStyle = PAPER;
    ctx.fillRect((a.x + b.x) / 2 - ww / 2, yy - 8, ww, 16);
    ctx.fillStyle = '#4a4a47';
    ctx.fillText(wt, (a.x + b.x) / 2, yy);
    // profondeur (gauche)
    const xx = a.x - off;
    seg(a.x - gap, a.y, xx - 5, a.y);
    seg(a.x - gap, b.y, xx - 5, b.y);
    seg(xx, a.y, xx, b.y);
    seg(xx - tick, a.y + tick, xx + tick, a.y - tick);
    seg(xx - tick, b.y + tick, xx + tick, b.y - tick);
    const dt = `${fmtM(bd)} m`;
    ctx.save();
    ctx.translate(xx, (a.y + b.y) / 2);
    ctx.rotate(-Math.PI / 2);
    const dw = ctx.measureText(dt).width + 10;
    ctx.fillStyle = PAPER;
    ctx.fillRect(-dw / 2, -8, dw, 16);
    ctx.fillStyle = '#4a4a47';
    ctx.fillText(dt, 0, 0);
    ctx.restore();
    ctx.restore();
  }

  function polyArea(poly) {
    let s2 = 0;
    for (let i = 0; i < poly.length; i++) {
      const p = poly[i];
      const q = poly[(i + 1) % poly.length];
      s2 += p.x * q.y - q.x * p.y;
    }
    return Math.abs(s2) / 2;
  }

  function sharedEdge(pa, pb, tol) {
    // vrai si deux rectangles/polygones se touchent le long d'une arête d'au moins 0,3 m
    const a = box(pa);
    const b = box(pb);
    const t = tol || 0.06;
    const ov = (u0, u1, v0, v1) => Math.min(u1, v1) - Math.max(u0, v0);
    if (Math.abs(a.x1 - b.x0) < t || Math.abs(b.x1 - a.x0) < t) return ov(a.y0, a.y1, b.y0, b.y1) > 0.3;
    if (Math.abs(a.y1 - b.y0) < t || Math.abs(b.y1 - a.y0) < t) return ov(a.x0, a.x1, b.x0, b.x1) > 0.3;
    return false;
  }

  // Les segments de couloir qui se touchent forment UN couloir : on l'étiquette une fois.
  function hallGroups(rooms) {
    const halls = (rooms || []).map((r, i) => ({ r, i })).filter((h) => h.r.type === 'hallway' && (h.r.polygon || []).length >= 3);
    const group = halls.map((_, k) => k);
    const find = (k) => { while (group[k] !== k) { group[k] = group[group[k]]; k = group[k]; } return k; };
    for (let a = 0; a < halls.length; a++) {
      for (let b = a + 1; b < halls.length; b++) {
        if (sharedEdge(halls[a].r.polygon, halls[b].r.polygon)) group[find(a)] = find(b);
      }
    }
    const byRoot = new Map();
    halls.forEach((h, k) => {
      const root = find(k);
      if (!byRoot.has(root)) byRoot.set(root, []);
      byRoot.get(root).push(h);
    });
    return [...byRoot.values()];
  }

  // Libellés en capitales espacées + surface ; un seul « COULOIR » par couloir continu.
  function drawRoomLabels(ctx, rooms, toScreen, opts) {
    const skip = new Set();
    const hallLabel = new Map();
    hallGroups(rooms).forEach((grp) => {
      const main = grp.reduce((best, h) => (polyArea(h.r.polygon) > polyArea(best.r.polygon) ? h : best), grp[0]);
      grp.forEach((h) => { if (h !== main) skip.add(h.i); });
      hallLabel.set(main.i, true);
    });
    const sc = m2px(toScreen);
    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    (rooms || []).forEach((room, i) => {
      const poly = room.polygon || [];
      if (poly.length < 3 || skip.has(i)) return;
      const bx = box(poly);
      const w = bx.x1 - bx.x0;
      const h = bx.y1 - bx.y0;
      if (Math.min(w, h) < 0.85 || Math.max(w, h) < 1.2) return;
      const c = poly.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), { x: 0, y: 0 });
      const p = toScreen({ x: c.x / poly.length, y: c.y / poly.length });
      const text = (room.type === 'hallway' ? 'Couloir' : label(room)).toUpperCase();
      const size = Math.max(9, Math.min(12, sc * 0.26));
      ctx.font = `600 ${size}px "DM Sans", system-ui, sans-serif`;
      if ('letterSpacing' in ctx) ctx.letterSpacing = '0.06em';
      const showArea = room.type !== 'hallway' && Math.min(w, h) >= 1.3 && !(opts && opts.noArea);
      const y = showArea ? p.y - size * 0.55 : p.y;
      ctx.lineWidth = 3;
      ctx.strokeStyle = 'rgba(251,250,247,0.85)';
      ctx.strokeText(text, p.x, y);
      ctx.fillStyle = INK;
      ctx.fillText(text, p.x, y);
      if (showArea) {
        ctx.font = `500 ${Math.max(8, size - 1.5)}px "DM Sans", system-ui, sans-serif`;
        if ('letterSpacing' in ctx) ctx.letterSpacing = '0';
        const area = `${polyArea(poly).toFixed(1).replace('.', ',')} m²`;
        ctx.strokeText(area, p.x, y + size * 1.15);
        ctx.fillStyle = '#6d6d69';
        ctx.fillText(area, p.x, y + size * 1.15);
      }
      if ('letterSpacing' in ctx) ctx.letterSpacing = '0';
    });
    ctx.restore();
  }

  function woodPlanks(ctx, a, b, sc, tones) {
    const ph = 0.135 * sc;
    const pw = 0.88 * sc;
    let row = 0;
    ctx.strokeStyle = 'rgba(120,90,50,0.10)';
    ctx.lineWidth = 0.6;
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

  function tileGrid(ctx, a, b, step, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.7;
    ctx.beginPath();
    for (let x = a.x; x <= b.x + 0.5; x += step) { ctx.moveTo(x, a.y); ctx.lineTo(x, b.y); }
    for (let y = a.y; y <= b.y + 0.5; y += step) { ctx.moveTo(a.x, y); ctx.lineTo(b.x, y); }
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
    if (type === 'bedroom' || type === 'office') {
      flat('#ecdfc6');
      woodPlanks(ctx, a, b, sc, ['#ecdfc6', '#e8dabf', '#f0e4cd', '#e6d8bc', '#eee1c8']);
    } else if (type === 'living' || type === 'dining') {
      flat('#e7e4de');
      tileGrid(ctx, a, b, 1.2 * sc, 'rgba(90,86,78,0.05)');
    } else if (type === 'hallway') {
      flat('#e1ded7');
      tileGrid(ctx, a, b, 1.2 * sc, 'rgba(90,86,78,0.05)');
    } else if (type === 'kitchen') {
      flat('#ecebe7');
      tileGrid(ctx, a, b, 0.6 * sc, 'rgba(90,90,84,0.07)');
    } else if (type === 'bathroom' || type === 'wc' || type === 'laundry') {
      flat('#d5e2ea');
      tileGrid(ctx, a, b, 0.3 * sc, 'rgba(60,100,130,0.11)');
    } else if (type === 'garage' || type === 'storage') {
      flat(type === 'garage' ? '#d3d3cf' : '#dddbd6');
    } else {
      flat(fill(room));
    }
    ctx.restore();
  }

  function drawFixtures(ctx, room, toScreen) {
    drawFloor(ctx, room, toScreen);
  }

  function drawWalls(ctx, walls, toScreen, scale) {
    ctx.save();
    ctx.fillStyle = WALL;
    (walls || []).forEach((wall) => {
      const a = toScreen(wall.a);
      const b = toScreen(wall.b);
      const t = Math.max(3, (wall.thickness_m || 0.2) * scale);
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len = Math.hypot(dx, dy) || 1;
      const ux = (dx / len) * (t / 2);
      const uy = (dy / len) * (t / 2);
      const nx = (-dy / len) * (t / 2);
      const ny = (dx / len) * (t / 2);
      // Prolongé d'une demi-épaisseur aux deux bouts : les angles et les T se ferment sans trou.
      ctx.beginPath();
      ctx.moveTo(a.x - ux + nx, a.y - uy + ny);
      ctx.lineTo(b.x + ux + nx, b.y + uy + ny);
      ctx.lineTo(b.x + ux - nx, b.y + uy - ny);
      ctx.lineTo(a.x - ux - nx, a.y - uy - ny);
      ctx.closePath();
      ctx.fill();
    });
    ctx.restore();
  }

  // Seuil : une marche pâle devant la porte d'entrée et une flèche noire qui indique l'entrée.
  function drawPorch(ctx, openings, walls, depth, toScreen) {
    const south = (openings || []).find((o) => o.type === 'door' && o.wall_id === 'w_outer_3');
    const wall = (walls || []).find((w) => w.id === 'w_outer_3');
    if (!south || !wall) return;
    const len = Math.hypot(wall.b.x - wall.a.x, wall.b.y - wall.a.y) || 1;
    const t0 = (south.offset_m || 0) / len;
    const t1 = ((south.offset_m || 0) + (south.width_m || 0.9)) / len;
    const xa = wall.a.x + (wall.b.x - wall.a.x) * t0;
    const xb = wall.a.x + (wall.b.x - wall.a.x) * t1;
    const a = toScreen({ x: Math.min(xa, xb) - 0.2, y: depth + 0.1 });
    const b = toScreen({ x: Math.max(xa, xb) + 0.2, y: depth + 0.55 });
    ctx.save();
    ctx.fillStyle = '#ebe8e1';
    ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
    ctx.strokeStyle = '#8b8b86';
    ctx.lineWidth = 1;
    ctx.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);
    const cx = (a.x + b.x) / 2;
    const ty = b.y + 5;
    ctx.fillStyle = '#1f1f1d';
    ctx.beginPath();
    ctx.moveTo(cx, ty);
    ctx.lineTo(cx - 7, ty + 13);
    ctx.lineTo(cx + 7, ty + 13);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
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
      const thick = Math.max(4, (wall.thickness_m || 0.2) * scale);
      const ang = Math.atan2(p1.y - p0.y, p1.x - p0.x);
      const nx = -Math.sin(ang);
      const ny = Math.cos(ang);
      ctx.save();
      ctx.lineCap = 'butt';
      ctx.strokeStyle = GAP;
      ctx.lineWidth = thick + 1;
      ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y); ctx.stroke();
      if (op.type === 'window') {
        // Deux traits de part et d'autre du vitrage, un trait bleu au centre.
        ctx.strokeStyle = '#3d3d3a';
        ctx.lineWidth = 1;
        [-1, 1].forEach((k) => {
          ctx.beginPath();
          ctx.moveTo(p0.x + nx * (thick / 2) * k, p0.y + ny * (thick / 2) * k);
          ctx.lineTo(p1.x + nx * (thick / 2) * k, p1.y + ny * (thick / 2) * k);
          ctx.stroke();
        });
        ctx.strokeStyle = '#6fa3c4';
        ctx.lineWidth = 1.6;
        ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y); ctx.stroke();
      } else {
        const r = w2 * scale;
        // Battant plein + arc fin : lisible à toutes les échelles, sans pointillés.
        ctx.strokeStyle = '#6f6f6a';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(p0.x, p0.y, r, ang, ang + Math.PI / 2);
        ctx.stroke();
        ctx.strokeStyle = INK;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y);
        ctx.lineTo(p0.x + Math.cos(ang + Math.PI / 2) * r, p0.y + Math.sin(ang + Math.PI / 2) * r);
        ctx.stroke();
      }
      ctx.restore();
    });
  }

  return {
    fills, labels, label, fill, drawFixtures, drawFurniture,
    drawFloor, drawSite, drawPorch, drawOpenings, drawWalls,
    drawDimensions, drawRoomLabels, hallGroups, polyArea,
  };
})();
