window.PlanStyle = (() => {
  const { fills, labels, label, fill } = window.PlanStylePalette;
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
  const { drawFloor } = window.PlanStyleFloors({ box, m2px, fill });
  const { drawFurniture } = window.PlanStyleFurniture({ m2px });

  // Palette « plan d'architecte » : papier clair, murs pleins gris foncé, sols pâles.
  const PAPER = '#ffffff';
  const INK = '#25343b';
  const { drawSite, drawDimensions } = window.PlanStylePresentation({
    m2px, ink: INK, paper: PAPER,
  });
  const { drawWalls, drawPorch } = window.PlanStyleWalls();
  const { drawOpenings } = window.PlanStyleOpenings({ ink: INK, paper: PAPER });
  const { drawRoomLabels, hallGroups, polyArea, roomDimensions } = window.PlanStyleAnnotations({
    box, m2px, label, ink: INK, paper: PAPER,
  });

  function drawFixtures(ctx, room, toScreen) {
    drawFloor(ctx, room, toScreen);
  }

  return {
    prepareFurniture: items => window.PlanStyleAssets?.prepare(items) ?? Promise.resolve([]),
    fills, labels, label, fill, drawFixtures, drawFurniture,
    drawFloor, drawSite, drawPorch, drawOpenings, drawWalls,
    drawDimensions, drawRoomLabels, hallGroups, polyArea, roomDimensions,
  };
})();
