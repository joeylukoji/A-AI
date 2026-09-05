/**
 * Temps réel global : une connexion SSE par page dashboard, reconnexion
 * permanente, indicateur « En direct », bus d'événements pour les pages.
 *
 * Événements window :
 *   caia:job          { type, status, step, project_id, job_id, error, output }
 *   caia:plan.ready   { project_id, revision_id }
 *   caia:model.ready  { project_id, glb_artifact_id }
 *   caia:ping
 *   caia:live         { connected: boolean }
 */
(function () {
  const orgId = document.body.getAttribute('data-org-id') || '';
  const projectId = document.body.getAttribute('data-project-id') || '';
  if (!orgId) return;

  const pip = document.getElementById('live-dot-pip');
  const label = document.getElementById('live-label');
  const jobEl = document.getElementById('live-job');
  const toastEl = document.getElementById('live-toast');

  const labels = {
    generate_2d: 'Plan 2D',
    edit_plan: 'Modification',
    generate_3d: 'Maquette 3D',
    generate_devis: 'Devis',
    adapt_plan: 'Adaptation',
    export: 'Export',
  };
  const steps = {
    nlu: 'analyse du brief',
    flux: 'dessin du plan',
    verify: 'vérification du plan',
    regenerate: 'On régénère le plan…',
    edit: 'modification du plan',
    diffusion: 'disposition des pièces',
    refine: 'rendu',
    vectorize: 'vectorisation',
    adapt: 'calage parcelle',
    devis: 'rédaction du devis',
    blender: 'extrusion 3D',
  };

  let es = null;
  let retryMs = 1000;
  let lastPayload = '';
  let connected = false;

  function setLive(on) {
    connected = on;
    if (pip) {
      pip.classList.toggle('bg-teal-500', on);
      pip.classList.toggle('live-pulse', on);
      pip.classList.toggle('bg-zinc-400', !on);
    }
    if (label) {
      label.textContent = on ? 'En direct' : 'Reconnexion…';
      label.classList.toggle('text-teal-600', on);
      label.classList.toggle('dark:text-teal-400', on);
      label.classList.toggle('text-zinc-400', !on);
    }
    window.dispatchEvent(new CustomEvent('caia:live', { detail: { connected: on } }));
  }

  function toast(text) {
    if (!toastEl || !text) return;
    toastEl.textContent = text;
    toastEl.classList.remove('opacity-0', 'pointer-events-none', 'translate-y-2');
    clearTimeout(toastEl._t);
    toastEl._t = setTimeout(() => {
      toastEl.classList.add('opacity-0', 'pointer-events-none', 'translate-y-2');
    }, 4200);
  }

  function jobLine(data) {
    const kind = labels[data.type] || data.type || 'Tâche';
    const st = data.status || '';
    if (st === 'queued') return `${kind} · en file`;
    if (st === 'running') return `${kind} · ${steps[data.step] || data.step || 'en cours'}`;
    if (st === 'succeeded') return `${kind} · terminé`;
    if (st === 'failed') return `${kind} · échec${data.error ? ' — ' + data.error : ''}`;
    return `${kind} · ${st}`;
  }

  function showJob(data) {
    if (!jobEl) return;
    jobEl.textContent = jobLine(data);
    jobEl.classList.remove('hidden');
  }

  function emit(name, detail) {
    window.dispatchEvent(new CustomEvent(name, { detail }));
  }

  function onPayload(eventName, raw) {
    let data;
    try { data = JSON.parse(raw || '{}'); } catch { return; }
    const key = eventName + ':' + raw;
    if (key === lastPayload) return;
    lastPayload = key;

    if (eventName === 'ping') {
      setLive(true);
      emit('caia:ping', data);
      return;
    }
    if (eventName === 'job.updated') {
      showJob(data);
      emit('caia:job', data);
      if (data.status === 'failed') toast(jobLine(data));
      if (data.status === 'running' && data.step === 'regenerate') toast('On régénère le plan…');
      return;
    }
    if (eventName === 'plan.ready') {
      showJob({ type: 'generate_2d', status: 'succeeded' });
      toast('Plan 2D prêt');
      emit('caia:plan.ready', data);
      return;
    }
    if (eventName === 'model.ready') {
      showJob({ type: 'generate_3d', status: 'succeeded' });
      toast('Maquette 3D prête');
      emit('caia:model.ready', data);
    }
  }

  function connect() {
    if (es) {
      try { es.close(); } catch { /* ignore */ }
    }
    es = new EventSource('/api/v1/events');
    es.onopen = () => {
      retryMs = 1000;
      setLive(true);
    };
    es.onerror = () => {
      setLive(false);
      try { es.close(); } catch { /* ignore */ }
      es = null;
      setTimeout(connect, retryMs);
      retryMs = Math.min(15000, retryMs * 1.6);
    };
    ['ping', 'job.updated', 'plan.ready', 'model.ready'].forEach((name) => {
      es.addEventListener(name, (e) => onPayload(name, e.data));
    });
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && (!es || es.readyState === EventSource.CLOSED)) {
      retryMs = 1000;
      connect();
    }
  });

  window.CAIA = Object.assign(window.CAIA || {}, {
    orgId,
    projectId,
    isLive: () => connected,
    jobStep: (step) => steps[step] || step || '',
    onJob(fn) { window.addEventListener('caia:job', (e) => fn(e.detail)); },
    onPlanReady(fn) { window.addEventListener('caia:plan.ready', (e) => fn(e.detail)); },
    onModelReady(fn) { window.addEventListener('caia:model.ready', (e) => fn(e.detail)); },
  });

  connect();
})();
