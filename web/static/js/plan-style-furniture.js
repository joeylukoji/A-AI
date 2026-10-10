// Vector furniture in local metres. The item boundary owns transforms and clipping.
window.PlanStyleFurniture = ({ m2px }) => {
  const C = {
    line: '#58646a', oak: '#c8aa80', oakLight: '#dfc9a7', white: '#fcfcf8',
    fabric: '#9eafa6', cushion: '#dce4dc', accent: '#c79870',
    dark: '#29383f', metal: '#6c7c82', glass: '#bcd4dc', rug: '#ded8ca',
  };

  function roundRect(ctx, x, y, w, h, r) {
    const radius = Math.max(0, Math.min(r, w / 2, h / 2));
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, w, h, radius);
    else {
      ctx.moveTo(x + radius, y);
      ctx.lineTo(x + w - radius, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
      ctx.lineTo(x + w, y + h - radius);
      ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
      ctx.lineTo(x + radius, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
      ctx.lineTo(x, y + radius);
      ctx.quadraticCurveTo(x, y, x + radius, y);
      ctx.closePath();
    }
  }

  function paint(ctx, fill, stroke = C.line, width = 0.014) {
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = width; ctx.stroke(); }
  }

  // Coordinates are fractions of the declared footprint; corner radii scale with it.
  function panel(ctx, w, d, x, y, width, depth, fill, radius = 0.035, stroke = C.line) {
    roundRect(ctx, x * w, y * d, width * w, depth * d, Math.min(w, d) * radius);
    paint(ctx, fill, stroke);
  }

  function oval(ctx, x, y, rx, ry, fill, stroke = C.line, rotation = 0) {
    ctx.beginPath();
    ctx.ellipse(x, y, rx, ry, rotation, 0, Math.PI * 2);
    paint(ctx, fill, stroke);
  }

  function line(ctx, x0, y0, x1, y1, color = C.line, width = 0.012) {
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1);
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
  }

  function surface(ctx, w, d, colors) {
    const gradient = ctx.createLinearGradient(-w / 2, -d / 2, w / 2, d / 2);
    colors.forEach((color, index) => gradient.addColorStop(index / (colors.length - 1), color));
    return gradient;
  }

  function woodGrain(ctx, w, d, inset = 0.09) {
    for (let i = -3; i <= 3; i++) {
      const y = i * d * 0.105;
      ctx.beginPath();
      ctx.moveTo(w * (-0.5 + inset), y);
      ctx.bezierCurveTo(-w * 0.12, y - d * 0.035, w * 0.18, y + d * 0.025, w * (0.5 - inset), y);
      ctx.strokeStyle = 'rgba(124,87,43,0.18)';
      ctx.lineWidth = 0.006;
      ctx.stroke();
    }
  }

  function drawBed(ctx, w, d, single) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, C.oakLight);
    panel(ctx, w, d, -0.5, -0.5, 1, 0.12, surface(ctx, w, d, ['#8a9b92', '#c4cec3', '#8b9c92']));
    panel(ctx, w, d, -0.46, -0.35, 0.92, 0.81, C.white, 0.06);
    panel(ctx, w, d, -0.46, -0.06, 0.92, 0.52,
      surface(ctx, w, d, ['#c2a26e', '#ead3a0', '#c5a36d']), 0.035);
    panel(ctx, w, d, -0.46, -0.07, 0.92, 0.08, '#f3eedf', 0.01, '#cfc6b5');
    panel(ctx, w, d, -0.46, 0.29, 0.92, 0.11,
      surface(ctx, w, d, ['#92a69b', '#b7c6ba', '#8fa196']), 0.008, '#879b8f');
    const pillows = single ? [-0.31] : [-0.42, 0.04];
    pillows.forEach((x) => {
      panel(ctx, w, d, x + 0.015, -0.305, single ? 0.62 : 0.38, 0.22, '#d2d3c9', 0.055, null);
      panel(ctx, w, d, x, -0.32, single ? 0.62 : 0.38, 0.22,
        surface(ctx, w, d, ['#fdfef9', '#ffffff', '#e5e6dc']), 0.055, '#a1aaa1');
      line(ctx, (x + 0.04) * w, -d * 0.27, (x + (single ? 0.58 : 0.34)) * w,
        -d * 0.27, '#dce0da', 0.009);
    });
    [-0.36, 0.36].forEach((x) => {
      ctx.beginPath(); ctx.moveTo(w * x, d * 0.035);
      ctx.bezierCurveTo(w * (x - 0.015), d * 0.12, w * (x + 0.02), d * 0.19, w * x, d * 0.26);
      ctx.strokeStyle = 'rgba(143,111,62,0.3)'; ctx.lineWidth = 0.008; ctx.stroke();
    });
  }

  function drawSofa(ctx, w, d, lshape) {
    const body = lshape ? 0.65 : 1;
    const fabric = surface(ctx, w, d, ['#8b9e92', '#bccabf', '#87998e']);
    const cushion = surface(ctx, w, d, ['#f1f3e9', '#d5e0d3', '#b3c3b5']);
    panel(ctx, w, d, -0.5, -0.5, 1, body, fabric, 0.07);
    panel(ctx, w, d, -0.5, -0.5, 1, 0.14 * body, '#82968b', 0.045);
    panel(ctx, w, d, -0.5, -0.5, 0.09, body, fabric);
    panel(ctx, w, d, 0.41, -0.5, 0.09, 1, fabric);
    const seats = lshape ? 3 : 2;
    for (let i = 0; i < seats; i++) {
      panel(ctx, w, d, -0.39 + i * 0.79 / seats, -0.5 + body * 0.18,
        0.79 / seats - 0.018, body * 0.76, cushion, 0.04);
      const x = -0.39 + i * 0.79 / seats;
      panel(ctx, w, d, x + 0.018, -0.5 + body * 0.21,
        0.79 / seats - 0.054, body * 0.69, null, 0.04, 'rgba(255,255,249,0.75)');
    }
    if (lshape) {
      panel(ctx, w, d, 0.13, -0.5, 0.37, 1, fabric, 0.06);
      panel(ctx, w, d, 0.16, -0.34, 0.24, 0.79, cushion, 0.045);
      panel(ctx, w, d, 0.177, -0.315, 0.206, 0.74, null, 0.04, '#e9eee2');
    }
    panel(ctx, w, d, -0.35, -0.32, 0.13, body * 0.23,
      surface(ctx, w, d, ['#a67549', '#d6b075', '#c8965f']), 0.03, '#a88660');
    panel(ctx, w, d, lshape ? -0.03 : 0.2, -0.32, 0.13, body * 0.23, '#faf8ee', 0.03, '#a5b0a2');
  }

  function drawArmchair(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, surface(ctx, w, d, ['#95a797', '#cbd7c6', '#8b9e8e']), 0.13);
    panel(ctx, w, d, -0.5, -0.5, 1, 0.18, '#82968b', 0.09);
    panel(ctx, w, d, -0.5, -0.5, 0.14, 1, C.fabric, 0.06);
    panel(ctx, w, d, 0.36, -0.5, 0.14, 1, C.fabric, 0.06);
    panel(ctx, w, d, -0.31, -0.24, 0.62, 0.66,
      surface(ctx, w, d, ['#f1f4e8', '#d2dfca', '#b4c4ad']), 0.1);
    panel(ctx, w, d, -0.26, -0.19, 0.52, 0.56, null, 0.09, '#edf2e4');
  }

  function drawDiningTable(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, C.oak, 0.13);
    panel(ctx, w, d, -0.47, -0.45, 0.94, 0.9,
      surface(ctx, w, d, ['#b9945e', '#dfc18a', '#c39d61']), 0.11, '#b29570');
    woodGrain(ctx, w, d, 0.13);
  }

  function drawChair(ctx, w, d) {
    panel(ctx, w, d, -0.42, -0.5, 0.84, 0.18, C.oak, 0.06);
    panel(ctx, w, d, -0.43, -0.28, 0.86, 0.76,
      surface(ctx, w, d, ['#f6f5e9', '#e2e5d5', '#c3ccba']), 0.16);
    line(ctx, -w * 0.32, -d * 0.29, -w * 0.32, -d * 0.4);
    line(ctx, w * 0.32, -d * 0.29, w * 0.32, -d * 0.4);
  }

  function drawCoffee(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, C.white, 0.16);
    panel(ctx, w, d, -0.37, -0.3, 0.28, 0.5, '#d1b391', 0.01);
    panel(ctx, w, d, -0.32, -0.25, 0.25, 0.46, '#eef0e8', 0.01);
    oval(ctx, w * 0.23, d * 0.04, w * 0.1, d * 0.17, C.dark);
    oval(ctx, w * 0.23, d * 0.04, w * 0.065, d * 0.11, '#73977c', null);
  }

  function drawCounter(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, C.white, 0.018);
    panel(ctx, w, d, -0.5, -0.5, 1, 0.1, '#d5dcd8', 0.008);
    for (let i = 1; i < 4; i++) line(ctx, w * (-0.5 + i / 4), d * 0.38,
      w * (-0.5 + i / 4), d * 0.5, '#9da9a7');
    panel(ctx, w, d, -0.29, -0.25, 0.53, 0.6, '#b4c4c9', 0.065);
    panel(ctx, w, d, -0.24, -0.19, 0.43, 0.48, C.glass, 0.05);
    oval(ctx, -w * 0.02, d * 0.08, Math.min(w, d) * 0.035, Math.min(w, d) * 0.035, C.metal);
    line(ctx, -w * 0.025, -d * 0.38, -w * 0.025, -d * 0.13, C.dark, 0.035);
    [0.31, 0.36, 0.41].forEach((x) => line(ctx, w * x, -d * 0.17, w * x, d * 0.25, '#b9c3c1', 0.009));
  }

  function drawStove(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, '#243139', 0.04);
    for (const x of [-0.24, 0.24]) for (const y of [-0.22, 0.22]) {
      const radius = Math.min(w, d) * 0.16;
      oval(ctx, w * x, d * y, radius, radius, '#34444c', '#a4b4b8');
      oval(ctx, w * x, d * y, radius * 0.66, radius * 0.66, null, '#71858d');
    }
    line(ctx, -w * 0.16, d * 0.43, w * 0.16, d * 0.43, '#e7eded', 0.018);
  }

  function drawNightstand(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, C.oakLight, 0.04);
    const r = Math.min(w, d);
    oval(ctx, 0, -d * 0.06, r * 0.23, r * 0.23, C.white, '#9d9c8e');
    oval(ctx, 0, -d * 0.06, r * 0.09, r * 0.09, '#d6bd8f', null);
    line(ctx, -w * 0.12, d * 0.36, w * 0.12, d * 0.36, C.dark, 0.018);
  }

  function drawWardrobe(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1,
      surface(ctx, w, d, ['#d0b181', '#e6cda3', '#c7a774']), 0.015);
    woodGrain(ctx, w, d);
    line(ctx, 0, -d * 0.5, 0, d * 0.5, '#a88d68');
    [-0.06, 0.06].forEach((x) => line(ctx, x * w, -d * 0.14, x * w, d * 0.14, C.dark, 0.018));
    [-0.35, -0.27, 0.27, 0.35].forEach((x) => line(ctx, x * w, -d * 0.43, x * w, d * 0.43, '#d4bd99', 0.006));
  }

  function drawDesk(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, C.oakLight, 0.035);
    panel(ctx, w, d, -0.13, -0.3, 0.36, 0.46, C.dark, 0.02);
    panel(ctx, w, d, -0.1, -0.26, 0.3, 0.28, '#7696a0', 0.01);
    panel(ctx, w, d, -0.16, 0.09, 0.42, 0.19, '#e1e6e4', 0.018);
    panel(ctx, w, d, -0.42, -0.2, 0.19, 0.43, C.white, 0.005);
  }

  function drawFireplace(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, '#49565c', 0.14);
    panel(ctx, w, d, -0.36, -0.33, 0.72, 0.69, C.dark, 0.07);
    oval(ctx, 0, d * 0.08, w * 0.19, d * 0.22, '#c8864b', null);
    oval(ctx, 0, d * 0.13, w * 0.09, d * 0.12, '#efc478', null);
  }

  function drawBathtub(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, C.white, 0.36);
    panel(ctx, w, d, -0.44, -0.36, 0.88, 0.72, '#e0ecee', 0.29);
    oval(ctx, w * 0.32, 0, Math.min(w, d) * 0.04, Math.min(w, d) * 0.04, C.metal);
    line(ctx, -w * 0.33, -d * 0.34, -w * 0.33, -d * 0.13, C.dark, 0.028);
  }

  function drawToilet(ctx, w, d) {
    panel(ctx, w, d, -0.43, -0.5, 0.86, 0.23, C.white, 0.05);
    oval(ctx, 0, d * 0.1, w * 0.42, d * 0.38, C.white);
    oval(ctx, 0, d * 0.13, w * 0.27, d * 0.26, '#dfebed', '#a9bbbf');
    panel(ctx, w, d, -0.12, -0.43, 0.24, 0.07, '#c7d0d0', 0.018);
  }

  function drawSink(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, C.oakLight, 0.04);
    panel(ctx, w, d, -0.43, -0.32, 0.86, 0.76, C.white, 0.15);
    panel(ctx, w, d, -0.29, -0.17, 0.58, 0.46, '#e0ecee', 0.1);
    line(ctx, 0, -d * 0.44, 0, -d * 0.12, C.dark, 0.03);
    oval(ctx, 0, d * 0.08, Math.min(w, d) * 0.035, Math.min(w, d) * 0.035, C.metal);
  }

  function drawCar(ctx, w, d) {
    ctx.beginPath();
    ctx.moveTo(-w * 0.49, -d * 0.3);
    ctx.quadraticCurveTo(-w * 0.5, -d * 0.43, -w * 0.36, -d * 0.46);
    ctx.lineTo(w * 0.36, -d * 0.46);
    ctx.quadraticCurveTo(w * 0.49, -d * 0.43, w * 0.49, -d * 0.28);
    ctx.lineTo(w * 0.49, d * 0.28);
    ctx.quadraticCurveTo(w * 0.49, d * 0.43, w * 0.36, d * 0.46);
    ctx.lineTo(-w * 0.36, d * 0.46);
    ctx.quadraticCurveTo(-w * 0.5, d * 0.43, -w * 0.49, d * 0.3);
    ctx.closePath();
    paint(ctx, surface(ctx, w, d, ['#526570', '#b3c2c7', '#dce6e6', '#586e7a']), '#425862', 0.018);
    roundRect(ctx, -w * 0.18, -d * 0.38, w * 0.44, d * 0.76, d * 0.18);
    paint(ctx, surface(ctx, w, d, ['#728893', '#d0dfe1', '#8ba0a8']), '#526b78', 0.014);
    [[-0.155, 0.12], [0.135, 0.1]].forEach(([x, width]) => {
      roundRect(ctx, w * x, -d * 0.3, w * width, d * 0.6, d * 0.09);
      paint(ctx, surface(ctx, w, d, ['#253e4b', '#86a8b8', '#364f5b']), '#304c5a', 0.015);
    });
    [-1, 1].forEach((side) => {
      line(ctx, -w * 0.37, side * d * 0.3, -w * 0.2, side * d * 0.28, '#72858e', 0.012);
      line(ctx, w * 0.29, side * d * 0.28, w * 0.41, side * d * 0.3, '#72858e', 0.012);
      line(ctx, -w * 0.12, side * d * 0.4, w * 0.22, side * d * 0.4, '#e3eded', 0.018);
      line(ctx, -w * 0.015, side * d * 0.385, w * 0.025, side * d * 0.385, '#435e6b', 0.022);
    });
    line(ctx, -w * 0.465, -d * 0.16, -w * 0.465, d * 0.16, '#273e48', 0.025);
    line(ctx, w * 0.455, -d * 0.13, w * 0.455, d * 0.13, '#d8e3e4', 0.026);
    const wheelW = w * 0.09;
    const wheelD = d * 0.07;
    [[-w * 0.41, -d * 0.48], [w * 0.23, -d * 0.48],
     [-w * 0.41, d * 0.41], [w * 0.23, d * 0.41]].forEach(([x, y]) => {
      roundRect(ctx, x, y, wheelW, wheelD, d * 0.02);
      paint(ctx, '#1c1c1e', '#08080a', 0.01);
    });
    [[-w * 0.46, -d * 0.22, '#f4e890'], [-w * 0.46, d * 0.22, '#f4e890'],
     [w * 0.46, -d * 0.2, '#e07060'], [w * 0.46, d * 0.2, '#e07060']]
      .forEach(([x, y, color]) => {
        ctx.beginPath();
        ctx.ellipse(x, y, w * 0.015, d * 0.025, 0, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      });
  }


  function drawRug(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, C.rug, 0.025, '#bfb7a8');
    panel(ctx, w, d, -0.46, -0.46, 0.92, 0.92, '#eee9de', 0.015, '#cec7b9');
    for (let i = -4; i <= 4; i++) line(ctx, -w * 0.42, d * i * 0.09,
      w * 0.42, d * i * 0.09, '#ded8cc', 0.008);
    for (const side of [-1, 1]) for (let i = -3; i <= 3; i++) {
      oval(ctx, w * i * 0.11, side * d * 0.39, w * 0.025, d * 0.018,
        i % 2 ? '#abb69b' : '#c5cbb7', null, side * 0.55);
    }
  }

  function drawPlant(ctx, w, d) {
    const r = Math.min(w, d);
    oval(ctx, 0, 0, r * 0.2, r * 0.2, '#d3c2a4');
    for (let i = 0; i < 9; i++) {
      const angle = i * Math.PI * 2 / 9;
      oval(ctx, Math.cos(angle) * r * 0.2, Math.sin(angle) * r * 0.2,
        r * 0.26, r * 0.095, i % 2 ? '#548268' : '#365f4b', '#2f5744', angle);
      line(ctx, 0, 0, Math.cos(angle) * r * 0.4, Math.sin(angle) * r * 0.4, '#80a383', 0.009);
    }
  }

  function drawFridge(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, '#e3e8e6', 0.03);
    panel(ctx, w, d, -0.45, -0.45, 0.9, 0.9, '#f6f8f5', 0.025);
    line(ctx, -w * 0.45, d * 0.06, w * 0.45, d * 0.06, '#a5b1b2');
    [ -0.2, 0.29 ].forEach((y) => line(ctx, w * 0.34, d * (y - 0.11), w * 0.34, d * (y + 0.11), C.dark, 0.025));
  }

  function drawTv(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, C.oak, 0.02);
    panel(ctx, w, d, -0.4, -0.32, 0.8, 0.32, C.dark, 0.018);
    line(ctx, -w * 0.08, 0, -w * 0.13, d * 0.21, C.dark, 0.025);
    line(ctx, w * 0.08, 0, w * 0.13, d * 0.21, C.dark, 0.025);
    [-0.32, 0.32].forEach((x) => line(ctx, w * x, d * 0.17, w * x, d * 0.5, '#a88d68'));
  }

  function drawGeneric(ctx, w, d) {
    panel(ctx, w, d, -0.5, -0.5, 1, 1, '#cbd2cb', 0.055);
  }

  const DRAWERS = {
    'bed.single': (ctx, w, d) => drawBed(ctx, w, d, true),
    'bed.double': (ctx, w, d) => drawBed(ctx, w, d, false),
    'sofa.lshape': (ctx, w, d) => drawSofa(ctx, w, d, true),
    'sofa.2seat': (ctx, w, d) => drawSofa(ctx, w, d, false),
    armchair: drawArmchair, 'table.dining': drawDiningTable, 'chair.dining': drawChair,
    'table.coffee': drawCoffee, 'counter.kitchen': drawCounter, stove: drawStove,
    nightstand: drawNightstand, wardrobe: drawWardrobe, desk: drawDesk,
    fireplace: drawFireplace, bathtub: drawBathtub, toilet: drawToilet,
    'sink.basin': drawSink, sink: drawSink, 'car.sedan': drawCar,
    'rug.rect': drawRug, 'plant.pot': drawPlant, fridge: drawFridge, 'tv.console': drawTv,
  };

  function drawFurniture(ctx, items, toScreen) {
    const list = (items || []).filter(Boolean).slice().sort((a, b) =>
      Number(!(a.catalog_id || '').startsWith('rug')) - Number(!(b.catalog_id || '').startsWith('rug')));
    const scale = m2px(toScreen);
    list.forEach((it) => {
      const w = it.size_m?.w ?? 0.5;
      const d = it.size_m?.d ?? 0.5;
      const rotation = it.rotation_deg ?? 0;
      if (![w, d, rotation, it.position?.x, it.position?.y].every(Number.isFinite) || w <= 0 || d <= 0) return;
      const origin = toScreen(it.position);
      ctx.save();
      ctx.translate(origin.x, origin.y);
      ctx.rotate(rotation * Math.PI / 180);
      ctx.scale(scale, scale);
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.beginPath(); ctx.rect(-w / 2, -d / 2, w, d); ctx.clip();
      if (!window.PlanStyleAssets?.draw(ctx, it.catalog_id, w, d)) {
        (DRAWERS[it.catalog_id] || drawGeneric)(ctx, w, d);
      }
      ctx.restore();
    });
  }

  return { drawFurniture };
};
