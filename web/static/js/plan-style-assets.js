// Local presentation assets only: never derive a URL from plan/user data.
window.PlanStyleAssets = (() => {
  const catalogue = new Map([
    ['bed.double', { file: 'bed-double-v1-opt1.png' }],
    ['bed.single', { file: 'bed-single-v1-opt1.png' }],
    ['sofa.lshape', { file: 'sofa-l-v1-opt1.png' }],
    ['sofa.2seat', { file: 'sofa-two-v1-opt1.png' }],
    ['armchair', { file: 'armchair-v1-opt1.png' }],
    ['plant.pot', { file: 'plant-v1-opt1.png' }],
    ['table.dining', { file: 'table-dining-v2-opt1.png' }],
    ['chair.dining', { file: 'chair-dining-v2-opt1.png' }],
    ['table.coffee', { file: 'table-coffee-v2-opt1.png' }],
    ['counter.kitchen', { file: 'counter-kitchen-v2-opt1.png' }],
    ['stove', { file: 'stove-v2-opt1.png' }],
    ['fridge', { file: 'fridge-v2-opt1.png' }],
    ['bathtub', { file: 'bathtub-v2-opt1.png' }],
    ['toilet', { file: 'toilet-v3-opt1.png' }],
    ['sink.basin', { file: 'sink-basin-v2-opt1.png' }],
    ['nightstand', { file: 'nightstand-v1-opt1.png' }],
    ['wardrobe', { file: 'wardrobe-v1-opt1.png' }],
    ['desk', { file: 'desk-v1-opt1.png' }],
    ['fireplace', { file: 'fireplace-v2-opt1.png' }],
    ['rug.rect', { file: 'rug-v1-opt1.png' }],
    ['tv.console', { file: 'tv-console-v1-opt1.png' }],
    // The catalogue's car points left; its source image points up.
    ['car.sedan', { file: 'car-v1-opt1.png', quarterTurn: true }],
  ]);
  const cache = new Map();

  function load(id) {
    if (cache.has(id)) return cache.get(id).ready;
    const entry = { image: null, ready: null };
    cache.set(id, entry);
    entry.ready = new Promise(resolve => {
      if (typeof window.Image !== 'function') {
        resolve({ id, status: 'failed' });
        return;
      }
      const image = new window.Image();
      image.crossOrigin = 'anonymous';
      const finish = loaded => {
        clearTimeout(timeout);
        image.onload = null;
        image.onerror = null;
        if (loaded && image.naturalWidth > 0 && image.naturalHeight > 0) entry.image = image;
        resolve({ id, status: entry.image ? 'loaded' : 'failed' });
      };
      const timeout = setTimeout(() => finish(false), 15000);
      image.onload = () => finish(true);
      image.onerror = () => finish(false);
      image.src = '/static/assets/furniture/' + catalogue.get(id).file;
    });
    return entry.ready;
  }

  function prepare(items = []) {
    const ids = new Set((items || []).map(item => item?.catalog_id).filter(id => catalogue.has(id)));
    return Promise.all([...ids].map(load));
  }

  // Called within the furniture renderer's local metre transform and footprint clip.
  function draw(ctx, id, width, depth) {
    const image = cache.get(id)?.image;
    if (!image) return false;
    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    if (catalogue.get(id).quarterTurn) {
      ctx.rotate(-Math.PI / 2);
      ctx.drawImage(image, -depth / 2, -width / 2, depth, width);
    } else {
      ctx.drawImage(image, -width / 2, -depth / 2, width, depth);
    }
    ctx.restore();
    return true;
  }

  return { prepare, draw };
})();
