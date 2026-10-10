window.PlanStyleOpenings = ({ ink, paper }) => {
  const STRUCTURE = '#30383b';
  const FRAME = '#596466';
  const GLASS = '#dcebf2';
  const GLASS_LINE = '#739eb5';
  const THRESHOLD = '#a6adae';
  const MAX_HINGED_DOOR_M = 1.3;

  function finitePoint(point) {
    return point && Number.isFinite(point.x) && Number.isFinite(point.y);
  }

  function openingGeometry(opening, walls, toScreen, scale) {
    if (!opening || (opening.type !== 'door' && opening.type !== 'window') ||
        !Number.isFinite(opening.offset_m) || !Number.isFinite(opening.width_m) ||
        opening.width_m <= 0 || !Number.isFinite(scale) || scale <= 0) return null;
    const wall = (walls || []).find((candidate) => candidate.id === opening.wall_id);
    if (!wall || !finitePoint(wall.a) || !finitePoint(wall.b)) return null;
    const modelLength = Math.hypot(wall.b.x - wall.a.x, wall.b.y - wall.a.y);
    if (!Number.isFinite(modelLength) || modelLength <= 0) return null;
    const start = Math.min(modelLength, Math.max(0, opening.offset_m));
    const end = Math.min(modelLength, Math.max(0, opening.offset_m + opening.width_m));
    if (end <= start) return null;
    const pointAt = (distance) => toScreen({
      x: wall.a.x + (wall.b.x - wall.a.x) * distance / modelLength,
      y: wall.a.y + (wall.b.y - wall.a.y) * distance / modelLength,
    });
    const p0 = pointAt(start);
    const p1 = pointAt(end);
    if (!finitePoint(p0) || !finitePoint(p1)) return null;
    const pixelLength = Math.hypot(p1.x - p0.x, p1.y - p0.y);
    if (!Number.isFinite(pixelLength) || pixelLength <= 0) return null;
    const tx = (p1.x - p0.x) / pixelLength;
    const ty = (p1.y - p0.y) / pixelLength;
    const thicknessM = Number.isFinite(wall.thickness_m) && wall.thickness_m > 0
      ? wall.thickness_m : 0.2;
    return {
      p0, p1, pixelLength, nx: -ty, ny: tx,
      thickness: Math.max(4, thicknessM * scale),
      angle: Math.atan2(p1.y - p0.y, p1.x - p0.x),
      widthM: end - start,
      explicitSemantics: opening.hinge !== undefined && opening.swing !== undefined,
      hingeAtEnd: opening.hinge === 'end',
      swingSign: opening.swing === 'negative' ? -1 : 1,
    };
  }

  function segment(ctx, a, b) {
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }

  function normalPoint(point, geometry, distance) {
    return { x: point.x + geometry.nx * distance, y: point.y + geometry.ny * distance };
  }

  function drawGap(ctx, geometry) {
    ctx.lineCap = 'butt';
    ctx.strokeStyle = paper;
    ctx.lineWidth = geometry.thickness + 1.5;
    segment(ctx, geometry.p0, geometry.p1);
  }

  function drawJambs(ctx, geometry) {
    ctx.strokeStyle = STRUCTURE;
    ctx.lineWidth = 1.2;
    for (const point of [geometry.p0, geometry.p1]) {
      segment(ctx, normalPoint(point, geometry, -geometry.thickness / 2),
        normalPoint(point, geometry, geometry.thickness / 2));
    }
  }

  function drawDoor(ctx, geometry) {
    drawGap(ctx, geometry);
    drawJambs(ctx, geometry);
    ctx.strokeStyle = THRESHOLD;
    ctx.lineWidth = 0.8;
    segment(ctx, geometry.p0, geometry.p1);
    // New generated garage doors carry explicit semantics but are overhead
    // openings, not implausibly large hinged leaves. Keep legacy documents
    // visually stable until they are explicitly edited or regenerated.
    if (geometry.explicitSemantics && geometry.widthM > MAX_HINGED_DOOR_M) return;

    const hinge = geometry.hingeAtEnd ? geometry.p1 : geometry.p0;
    const leafEnd = normalPoint(hinge, geometry, geometry.pixelLength * geometry.swingSign);
    ctx.lineCap = 'round';
    ctx.strokeStyle = paper;
    ctx.lineWidth = 3.2;
    segment(ctx, hinge, leafEnd);
    ctx.strokeStyle = ink;
    ctx.lineWidth = 1.5;
    segment(ctx, hinge, leafEnd);

    ctx.strokeStyle = '#858f91';
    ctx.lineWidth = 0.9;
    ctx.beginPath();
    const closedAngle = geometry.angle + (geometry.hingeAtEnd ? Math.PI : 0);
    const rotation = (geometry.hingeAtEnd ? -1 : 1) * geometry.swingSign * Math.PI / 2;
    if (rotation < 0) {
      ctx.arc(hinge.x, hinge.y, geometry.pixelLength,
        closedAngle, closedAngle + rotation, true);
    } else {
      ctx.arc(hinge.x, hinge.y, geometry.pixelLength,
        closedAngle, closedAngle + rotation);
    }
    ctx.stroke();
    ctx.fillStyle = STRUCTURE;
    ctx.beginPath();
    ctx.arc(hinge.x, hinge.y, 1.5, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawWindow(ctx, geometry) {
    drawGap(ctx, geometry);
    const glassHalf = Math.min(geometry.thickness * 0.24, 2.5);
    const glassPoints = [normalPoint(geometry.p0, geometry, glassHalf),
      normalPoint(geometry.p1, geometry, glassHalf),
      normalPoint(geometry.p1, geometry, -glassHalf),
      normalPoint(geometry.p0, geometry, -glassHalf)];
    ctx.fillStyle = GLASS;
    ctx.beginPath();
    ctx.moveTo(glassPoints[0].x, glassPoints[0].y);
    for (const point of glassPoints.slice(1)) ctx.lineTo(point.x, point.y);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = FRAME;
    ctx.lineWidth = 1;
    const railOffset = geometry.thickness * 0.28;
    for (const offset of [-railOffset, railOffset]) {
      segment(ctx, normalPoint(geometry.p0, geometry, offset),
        normalPoint(geometry.p1, geometry, offset));
    }
    ctx.strokeStyle = GLASS_LINE;
    ctx.lineWidth = 1.2;
    segment(ctx, geometry.p0, geometry.p1);
    drawJambs(ctx, geometry);

    if (geometry.pixelLength >= 28) {
      const middle = { x: (geometry.p0.x + geometry.p1.x) / 2,
        y: (geometry.p0.y + geometry.p1.y) / 2 };
      ctx.strokeStyle = FRAME;
      ctx.lineWidth = 0.8;
      segment(ctx, normalPoint(middle, geometry, -geometry.thickness / 2),
        normalPoint(middle, geometry, geometry.thickness / 2));
    }
    ctx.strokeStyle = THRESHOLD;
    ctx.lineWidth = 0.8;
    segment(ctx, normalPoint(geometry.p0, geometry, geometry.thickness * 0.72),
      normalPoint(geometry.p1, geometry, geometry.thickness * 0.72));
  }

  function drawOpenings(ctx, openings, walls, toScreen, scale) {
    (openings || []).forEach((opening) => {
      const geometry = openingGeometry(opening, walls, toScreen, scale);
      if (!geometry) return;
      ctx.save();
      try {
        if (opening.type === 'door') drawDoor(ctx, geometry);
        else drawWindow(ctx, geometry);
      } finally {
        ctx.restore();
      }
    });
  }

  return { drawOpenings };
};

