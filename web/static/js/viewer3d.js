(async () => {
  const projectId = window.AAI_PROJECT_ID;
  const statusEl = document.getElementById('viewer-status');
  const mv = document.getElementById('model-viewer');
  const canvas = document.getElementById('view3d');
  const dlGlb = document.getElementById('dl-glb');
  const dlObj = document.getElementById('dl-obj');

  async function loadArtifacts() {
    const res = await fetch(`/api/v1/projects/${projectId}/artifacts`, {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) throw new Error('artifacts fetch failed');
    const data = await res.json();
    const arts = data.artifacts || [];
    const glb = arts.find((a) => a.kind === 'glb');
    const obj = arts.find((a) => a.kind === 'obj');
    if (obj) {
      dlObj.href = `/api/v1/artifacts/${obj.id}/content`;
      dlObj.classList.remove('hidden');
    }
    if (glb) {
      dlGlb.href = `/api/v1/artifacts/${glb.id}/content`;
      dlGlb.classList.remove('hidden');
      const url = `/api/v1/artifacts/${glb.id}/content`;
      // Probe content: real GLB starts with "glTF" magic; stub may be JSON
      const probe = await fetch(url, { headers: { Accept: '*/*' } });
      const buf = await probe.arrayBuffer();
      const head = new TextDecoder().decode(buf.slice(0, 4));
      if (head === 'glTF' || (buf.byteLength > 12 && new DataView(buf).getUint32(0, true) === 0x46546c67)) {
        const blob = new Blob([buf], { type: 'model/gltf-binary' });
        mv.src = URL.createObjectURL(blob);
        mv.style.display = 'block';
        canvas.style.display = 'none';
        statusEl.textContent = 'Modèle Blender (GLB) depuis MinIO';
        return true;
      }
    }
    return false;
  }

  try {
    const ok = await loadArtifacts();
    if (!ok) {
      statusEl.textContent = 'Pas encore de GLB — extrusion locale du plan (génère la 3D depuis le studio).';
      await fallbackCanvas();
    }
  } catch (e) {
    statusEl.textContent = 'Viewer de secours (plan 2D extrudé)';
    await fallbackCanvas();
  }

  async function fallbackCanvas() {
    const res = await fetch(`/api/v1/projects/${projectId}`, { headers: { Accept: 'application/json' } });
    const data = await res.json();
    const plan = data.revision?.plan_document;
    if (!plan || !canvas) return;
    const ctx = canvas.getContext('2d');
    function resize() {
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
    }
    resize();
    window.addEventListener('resize', () => { resize(); draw(performance.now()); });
    function draw(time) {
      const w = canvas.width, h = canvas.height;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.fillStyle = '#1c1917';
      ctx.fillRect(0, 0, w, h);
      const cx = w / 2, cy = h / 2 + 40;
      const scale = 28 * devicePixelRatio;
      const rot = time * 0.0004;
      const cos = Math.cos(rot), sin = Math.sin(rot);
      const height = (plan.floor?.height_m || 2.7) * scale * 0.35;
      function project(x, y, z) {
        const xr = x * cos - y * sin;
        const yr = x * sin + y * cos;
        return { x: cx + xr * scale, y: cy + yr * scale * 0.55 - z };
      }
      ctx.strokeStyle = '#fdba74';
      ctx.lineWidth = 2;
      const ox = plan.floor.bounds.width / 2, oy = plan.floor.bounds.depth / 2;
      (plan.walls || []).forEach((wall) => {
        const a0 = project(wall.a.x - ox, wall.a.y - oy, 0);
        const b0 = project(wall.b.x - ox, wall.b.y - oy, 0);
        const a1 = project(wall.a.x - ox, wall.a.y - oy, height);
        const b1 = project(wall.b.x - ox, wall.b.y - oy, height);
        ctx.beginPath();
        ctx.moveTo(a0.x, a0.y); ctx.lineTo(b0.x, b0.y); ctx.lineTo(b1.x, b1.y); ctx.lineTo(a1.x, a1.y);
        ctx.closePath();
        ctx.fillStyle = 'rgba(231,229,228,0.12)';
        ctx.fill();
        ctx.stroke();
      });
      (plan.furniture || []).forEach((it) => {
        const w = (it.size_m && it.size_m.w) || 0.5;
        const d = (it.size_m && it.size_m.d) || 0.5;
        const zh = ((it.size_m && it.size_m.h) || 0.7) * scale * 0.35;
        const rot = ((it.rotation_deg || 0) * Math.PI) / 180;
        const c = Math.cos(rot), s = Math.sin(rot);
        const hx = w / 2, hy = d / 2;
        const px = (it.position && it.position.x) || 0;
        const py = (it.position && it.position.y) || 0;
        const corners = [[-hx, -hy], [hx, -hy], [hx, hy], [-hx, hy]].map(([lx, ly]) => ([
          px + lx * c - ly * s - ox,
          py + lx * s + ly * c - oy,
        ]));
        ctx.beginPath();
        corners.forEach((p, i) => {
          const q = project(p[0], p[1], zh);
          if (i === 0) ctx.moveTo(q.x, q.y); else ctx.lineTo(q.x, q.y);
        });
        ctx.closePath();
        ctx.fillStyle = 'rgba(180, 140, 90, 0.45)';
        ctx.strokeStyle = '#e7c9a0';
        ctx.fill();
        ctx.stroke();
      });
    }
    function loop(now) { draw(now); requestAnimationFrame(loop); }
    requestAnimationFrame(loop);
  }
})();
