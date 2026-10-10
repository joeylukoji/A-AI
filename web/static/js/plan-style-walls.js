window.PlanStyleWalls = () => {
  const WALL = '#30383b';

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

  // Point d'extension historique. PlanDocument ne décrit pas de porche.
  function drawPorch() {
  }

  return { drawWalls, drawPorch };
};

