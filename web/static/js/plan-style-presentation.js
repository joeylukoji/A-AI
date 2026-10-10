window.PlanStylePresentation = ({ m2px, ink, paper }) => {
  const BACKDROP = '#f3f2ed';
  const DIMENSION_INK = '#586164';

  function finitePoint(point) {
    return point && Number.isFinite(point.x) && Number.isFinite(point.y);
  }

  function fmtM(value) {
    return value.toFixed(1).replace('.', ',');
  }

  function metricScale(toScreen) {
    const origin = toScreen({ x: 0, y: 0 });
    const unit = toScreen({ x: 1, y: 0 });
    if (!finitePoint(origin) || !finitePoint(unit)) return Number.NaN;
    const observed = Math.hypot(unit.x - origin.x, unit.y - origin.y);
    const scale = m2px(toScreen);
    return Number.isFinite(observed) && observed > 0 && Number.isFinite(scale) && scale > 0
      ? scale : Number.NaN;
  }

  function drawSite(ctx, width, depth, toScreen, canvasWidth, canvasHeight) {
    if (![canvasWidth, canvasHeight].every(Number.isFinite) || canvasWidth < 0 || canvasHeight < 0) return;
    ctx.save();
    try {
      ctx.fillStyle = BACKDROP;
      ctx.fillRect(0, 0, canvasWidth, canvasHeight);
      if (![width, depth].every(Number.isFinite) || width <= 0 || depth <= 0) return;
      const a = toScreen({ x: 0, y: 0 });
      const b = toScreen({ x: width, y: depth });
      if (!finitePoint(a) || !finitePoint(b)) return;
      const x = Math.min(a.x, b.x);
      const y = Math.min(a.y, b.y);
      const w = Math.abs(b.x - a.x);
      const h = Math.abs(b.y - a.y);
      if (w <= 0 || h <= 0) return;
      ctx.shadowColor = 'rgba(36, 47, 51, 0.16)';
      ctx.shadowBlur = 18;
      ctx.shadowOffsetX = 0;
      ctx.shadowOffsetY = 5;
      ctx.fillStyle = paper;
      ctx.fillRect(x, y, w, h);
    } finally {
      ctx.restore();
    }
  }

  function drawScaleBar(ctx, width, depth, toScreen) {
    const scale = metricScale(toScreen);
    const a = toScreen({ x: 0, y: 0 });
    const b = toScreen({ x: width, y: depth });
    if (!Number.isFinite(scale) || scale <= 0 || !finitePoint(a) || !finitePoint(b)) return;
    const x = Math.min(a.x, b.x);
    const y = Math.min(a.y, b.y) - Math.min(scale * 0.34, 16);
    const barHeight = 4;
    ctx.save();
    ctx.lineWidth = 1;
    ctx.strokeStyle = DIMENSION_INK;
    ctx.fillStyle = ink;
    ctx.fillRect(x, y, scale, barHeight);
    ctx.fillStyle = paper;
    ctx.fillRect(x + scale, y, scale, barHeight);
    ctx.strokeRect(x, y, scale * 2, barHeight);
    ctx.fillStyle = DIMENSION_INK;
    ctx.font = '500 9px "DM Sans", system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillText('0', x, y - 2);
    ctx.fillText('1', x + scale, y - 2);
    ctx.fillText('2 m', x + scale * 2, y - 2);
    ctx.restore();
  }

  function drawDimensions(ctx, width, depth, toScreen) {
    if (![width, depth].every(Number.isFinite) || width <= 0 || depth <= 0) return;
    const scale = metricScale(toScreen);
    const a = toScreen({ x: 0, y: 0 });
    const b = toScreen({ x: width, y: depth });
    if (!Number.isFinite(scale) || scale <= 0 || !finitePoint(a) || !finitePoint(b)) return;
    const offset = Math.min(0.95 * scale, 46);
    const gap = Math.min(0.18 * scale, 8);
    const tick = 4;
    const segment = (x0, y0, x1, y1) => {
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    };
    ctx.save();
    ctx.strokeStyle = '#7c8587';
    ctx.fillStyle = DIMENSION_INK;
    ctx.lineWidth = 1;
    ctx.font = '500 11px "DM Sans", system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    const dimensionY = b.y + offset;
    segment(a.x, b.y + gap, a.x, dimensionY + 5);
    segment(b.x, b.y + gap, b.x, dimensionY + 5);
    segment(a.x, dimensionY, b.x, dimensionY);
    segment(a.x - tick, dimensionY + tick, a.x + tick, dimensionY - tick);
    segment(b.x - tick, dimensionY + tick, b.x + tick, dimensionY - tick);
    const widthText = `${fmtM(width)} m`;
    const widthLabel = ctx.measureText(widthText).width + 10;
    ctx.fillStyle = paper;
    ctx.fillRect((a.x + b.x) / 2 - widthLabel / 2, dimensionY - 8, widthLabel, 16);
    ctx.fillStyle = DIMENSION_INK;
    ctx.fillText(widthText, (a.x + b.x) / 2, dimensionY);

    const dimensionX = a.x - offset;
    segment(a.x - gap, a.y, dimensionX - 5, a.y);
    segment(a.x - gap, b.y, dimensionX - 5, b.y);
    segment(dimensionX, a.y, dimensionX, b.y);
    segment(dimensionX - tick, a.y + tick, dimensionX + tick, a.y - tick);
    segment(dimensionX - tick, b.y + tick, dimensionX + tick, b.y - tick);
    const depthText = `${fmtM(depth)} m`;
    ctx.save();
    ctx.translate(dimensionX, (a.y + b.y) / 2);
    ctx.rotate(-Math.PI / 2);
    const depthLabel = ctx.measureText(depthText).width + 10;
    ctx.fillStyle = paper;
    ctx.fillRect(-depthLabel / 2, -8, depthLabel, 16);
    ctx.fillStyle = DIMENSION_INK;
    ctx.fillText(depthText, 0, 0);
    ctx.restore();
    ctx.restore();
    drawScaleBar(ctx, width, depth, toScreen);
  }

  return { drawSite, drawDimensions, drawScaleBar };
};
