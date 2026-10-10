window.PlanStyleAnnotations = ({ box, m2px, label, ink, paper }) => {
  const INK = ink;
  const PAPER = paper;

  function furnitureBounds(items, toScreen) {
    return (items || []).filter((item) => item && !(item.catalog_id || '').startsWith('rug'))
      .flatMap((item) => {
        const { x, y } = item.position || {};
        const w = item.size_m?.w ?? 0.5;
        const d = item.size_m?.d ?? 0.5;
        const rotation = item.rotation_deg ?? 0;
        if (![x, y, w, d, rotation].every(Number.isFinite) || w <= 0 || d <= 0) return [];
        const angle = rotation * Math.PI / 180;
        const corners = [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]];
        return [box(corners.map(([cx, cy]) => toScreen({
          x: x + cx * Math.cos(angle) - cy * Math.sin(angle),
          y: y + cx * Math.sin(angle) + cy * Math.cos(angle),
        })))];
      });
  }

  function inside(point, polygon) {
    let result = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const a = polygon[i]; const b = polygon[j];
      if ((a.y > point.y) !== (b.y > point.y) &&
          point.x < (b.x - a.x) * (point.y - a.y) / (b.y - a.y) + a.x) result = !result;
    }
    return result;
  }

  function containsRectangle(rect, polygon) {
    const corners = [{ x: rect.x0, y: rect.y0 }, { x: rect.x1, y: rect.y0 },
      { x: rect.x1, y: rect.y1 }, { x: rect.x0, y: rect.y1 }];
    if (!corners.every((point) => inside(point, polygon))) return false;
    const cross = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
    // All four corners can be inside while an edge crosses a concave notch.
    for (let i = 0; i < polygon.length; i++) {
      const a = polygon[i]; const b = polygon[(i + 1) % polygon.length];
      if (a.x > rect.x0 && a.x < rect.x1 && a.y > rect.y0 && a.y < rect.y1) return false;
      for (let j = 0; j < 4; j++) {
        const c = corners[j]; const d = corners[(j + 1) % 4];
        if (cross(a, b, c) * cross(a, b, d) < 0 && cross(c, d, a) * cross(c, d, b) < 0) return false;
      }
    }
    return true;
  }

  function freeAnchor(polygon, preferred, width, above, below, obstacles) {
    const bounds = box(polygon);
    const candidates = [preferred];
    for (let row = 1; row < 10; row++) for (let col = 1; col < 10; col++) {
      candidates.push({ x: bounds.x0 + (bounds.x1 - bounds.x0) * col / 10,
        y: bounds.y0 + (bounds.y1 - bounds.y0) * row / 10 });
    }
    const distance = (point) => (point.x - preferred.x) ** 2 + (point.y - preferred.y) ** 2;
    candidates.sort((a, b) => distance(a) - distance(b));
    return candidates.find((point) => {
      const rect = { x0: point.x - width / 2 - 3, x1: point.x + width / 2 + 3,
        y0: point.y - above - 3, y1: point.y + below + 3 };
      return containsRectangle(rect, polygon) && !obstacles.some((obstacle) =>
        rect.x0 < obstacle.x1 && rect.x1 > obstacle.x0 && rect.y0 < obstacle.y1 && rect.y1 > obstacle.y0);
    });
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

  function roomDimensions(poly) {
    if (!Array.isArray(poly) || poly.length !== 4 ||
        !poly.every((point) => point && Number.isFinite(point.x) && Number.isFinite(point.y))) return null;
    const bounds = box(poly);
    const width = bounds.x1 - bounds.x0;
    const depth = bounds.y1 - bounds.y0;
    if (width <= 0 || depth <= 0 || Math.abs(polyArea(poly) - width * depth) > 1e-6) return null;
    const tolerance = 1e-6;
    for (let index = 0; index < poly.length; index++) {
      const point = poly[index];
      const next = poly[(index + 1) % poly.length];
      const horizontal = Math.abs(point.y - next.y) <= tolerance &&
        Math.abs(point.x - next.x) > tolerance;
      const vertical = Math.abs(point.x - next.x) <= tolerance &&
        Math.abs(point.y - next.y) > tolerance;
      if (!horizontal && !vertical) return null;
    }
    const format = (value) => value.toFixed(1).replace('.', ',');
    return `${format(width)} × ${format(depth)} m`;
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
    const sc = m2px(toScreen);
    const avoidFurniture = Array.isArray(opts?.furniture);
    const obstacles = avoidFurniture ? furnitureBounds(opts.furniture, toScreen) : [];
    ctx.save();
    try {
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const placement = (poly) => {
      const bounds = box(poly);
      const c = poly.reduce((acc, point) => ({ x: acc.x + point.x, y: acc.y + point.y }), { x: 0, y: 0 });
      const p = toScreen({ x: c.x / poly.length, y: c.y / poly.length });
      const a = toScreen({ x: bounds.x0, y: bounds.y0 });
      const b = toScreen({ x: bounds.x1, y: bounds.y1 });
      const left = Math.min(a.x, b.x) + 4;
      const right = Math.max(a.x, b.x) - 4;
      const top = Math.min(a.y, b.y) + 4;
      const bottom = Math.max(a.y, b.y) - 4;
      return {
        bounds, p, top, bottom,
        availableWidth: 2 * Math.min(p.x - left, right - p.x),
        availableHeight: 2 * Math.min(p.y - top, bottom - p.y),
      };
    };
    const largeEnough = (bounds) => {
      const w = bounds.x1 - bounds.x0;
      const h = bounds.y1 - bounds.y0;
      return Math.min(w, h) >= 0.85 && Math.max(w, h) >= 1.2;
    };
    const sequence = (rooms || []).map((r, i) => ({ r, i }));
    const hallGroupByIndex = new Map();
    const labelledGroups = new Set();
    ctx.font = '600 8px "DM Sans", system-ui, sans-serif';
    if ('letterSpacing' in ctx) ctx.letterSpacing = '0.06em';
    hallGroups(rooms).forEach((grp, groupIndex) => {
      const ranked = [...grp].sort((a, b) => polyArea(b.r.polygon) - polyArea(a.r.polygon));
      const main = ranked.find((h) => {
        const space = placement(h.r.polygon);
        return largeEnough(space.bounds) &&
          ctx.measureText('COULOIR').width <= space.availableWidth && 8 <= space.availableHeight;
      }) || ranked[0];
      const priority = [main, ...ranked.filter((h) => h !== main)];
      grp.forEach((h, index) => {
        sequence[h.i] = priority[index];
        hallGroupByIndex.set(h.i, groupIndex);
      });
    });
    sequence.forEach(({ r: room, i }) => {
      const poly = room.polygon || [];
      const groupIndex = hallGroupByIndex.get(i);
      if (poly.length < 3 || (groupIndex !== undefined && labelledGroups.has(groupIndex))) return;
      const space = placement(poly);
      const { bounds: bx, p, top, bottom, availableWidth, availableHeight } = space;
      const w = bx.x1 - bx.x0;
      const h = bx.y1 - bx.y0;
      const fitWidth = avoidFurniture ? w * sc - 8 : availableWidth;
      const fitHeight = avoidFurniture ? h * sc - 8 : availableHeight;
      if (!largeEnough(bx)) return;
      const text = (room.type === 'hallway' ? 'Couloir' : label(room)).toUpperCase();
      let size = Math.max(9, Math.min(12, sc * 0.26));
      if ('letterSpacing' in ctx) ctx.letterSpacing = '0.06em';
      while (size >= 8) {
        ctx.font = `600 ${size}px "DM Sans", system-ui, sans-serif`;
        if (ctx.measureText(text).width <= fitWidth && size <= fitHeight) break;
        if (size === 8) { size = 0; break; }
        size = Math.max(8, size - 1);
      }
      if (!size) {
        if ('letterSpacing' in ctx) ctx.letterSpacing = '0';
        return;
      }
      let showArea = room.type !== 'hallway' && Math.min(w, h) >= 1.3 && !(opts && opts.noArea);
      let area;
      let areaFontSize;
      let areaWidth = 0;
      if (showArea) {
        areaFontSize = Math.max(8, size - 1.5);
        ctx.font = `500 ${areaFontSize}px "DM Sans", system-ui, sans-serif`;
        if ('letterSpacing' in ctx) ctx.letterSpacing = '0';
        area = `${polyArea(poly).toFixed(1).replace('.', ',')} m²`;
        areaWidth = ctx.measureText(area).width;
        showArea = areaWidth <= fitWidth && (avoidFurniture
          ? size * 1.65 + areaFontSize / 2 <= fitHeight
          : p.y - size * 1.05 >= top && p.y + size * 0.6 + areaFontSize / 2 <= bottom);
        ctx.font = `600 ${size}px "DM Sans", system-ui, sans-serif`;
        if ('letterSpacing' in ctx) ctx.letterSpacing = '0.06em';
      }
      let dimensions = opts?.dimensions && room.type !== 'hallway'
        ? roomDimensions(poly) : null;
      let dimensionsFontSize = 0;
      let dimensionsWidth = 0;
      if (dimensions && showArea) {
        dimensionsFontSize = Math.max(7, areaFontSize - 1);
        ctx.font = `500 ${dimensionsFontSize}px "DM Sans", system-ui, sans-serif`;
        if ('letterSpacing' in ctx) ctx.letterSpacing = '0';
        dimensionsWidth = ctx.measureText(dimensions).width;
        if (dimensionsWidth > fitWidth || size + areaFontSize + dimensionsFontSize + 8 > fitHeight) {
          dimensions = null;
        }
        ctx.font = `600 ${size}px "DM Sans", system-ui, sans-serif`;
        if ('letterSpacing' in ctx) ctx.letterSpacing = '0.06em';
      } else {
        dimensions = null;
      }
      if (avoidFurniture) {
        const screenPolygon = poly.map(toScreen);
        const nameWidth = ctx.measureText(text).width;
        let anchor = dimensions ? freeAnchor(screenPolygon, p,
          Math.max(nameWidth, areaWidth, dimensionsWidth), size * 1.45,
          areaFontSize / 2 + dimensionsFontSize + 5, obstacles) : null;
        if (!anchor && dimensions) dimensions = null;
        if (!anchor && showArea) anchor = freeAnchor(screenPolygon, p, Math.max(nameWidth, areaWidth),
          size * 1.05, size * 0.6 + areaFontSize / 2, obstacles);
        if (!anchor) {
          showArea = false;
          dimensions = null;
          anchor = freeAnchor(screenPolygon, p, nameWidth, size / 2, size / 2, obstacles);
        }
        if (!anchor) return;
        p.x = anchor.x; p.y = anchor.y;
      }
      const y = dimensions ? p.y - size * 0.95 : showArea ? p.y - size * 0.55 : p.y;
      ctx.lineWidth = 3;
      ctx.strokeStyle = 'rgba(255,255,255,0.88)';
      ctx.strokeText(text, p.x, y);
      ctx.fillStyle = INK;
      ctx.fillText(text, p.x, y);
      if (showArea) {
        ctx.font = `500 ${areaFontSize}px "DM Sans", system-ui, sans-serif`;
        if ('letterSpacing' in ctx) ctx.letterSpacing = '0';
        const areaY = y + size * 1.15;
        ctx.strokeText(area, p.x, areaY);
        ctx.fillStyle = '#6d6d69';
        ctx.fillText(area, p.x, areaY);
        if (dimensions) {
          ctx.font = `500 ${dimensionsFontSize}px "DM Sans", system-ui, sans-serif`;
          const dimensionsY = areaY + areaFontSize * 1.15;
          ctx.strokeText(dimensions, p.x, dimensionsY);
          ctx.fillStyle = '#858b8a';
          ctx.fillText(dimensions, p.x, dimensionsY);
        }
      }
      if ('letterSpacing' in ctx) ctx.letterSpacing = '0';
      if (groupIndex !== undefined) labelledGroups.add(groupIndex);
    });
    } finally {
      ctx.restore();
    }
  }

  return { drawRoomLabels, hallGroups, polyArea, roomDimensions };
};
