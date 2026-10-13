'use strict';
// Match the local API contract, with jobs and downloadable artifacts kept in this tab.
window.workshopBrowser = (() => {
  const workerURL = new URL('worker.js', document.currentScript.src);
  const pending = new Map(), jobs = new Map();
  let worker, sequence = 0, latest = null, savedFiles = null, active = null, restoreNeeded = false;
  const cancel = document.createElement('button');
  cancel.id = 'cancel-generation'; cancel.textContent = 'Cancel'; cancel.hidden = true;
  document.addEventListener('DOMContentLoaded', () => document.querySelector('.header-actions').append(cancel));

  function failWorker(message) {
    for (const {reject, timer} of pending.values()) { clearTimeout(timer); reject(new Error(message)); }
    pending.clear();
    worker?.terminate(); worker = null; restoreNeeded = Boolean(latest);
  }
  function ensureWorker() {
    if (worker) return;
    worker = new Worker(workerURL, {type: 'module'});
    worker.onerror = event => { event.preventDefault(); failWorker('Browser engine stopped unexpectedly. Try again or reload the page.'); };
    worker.onmessage = ({data}) => {
      if (data.type === 'fatal') return failWorker(data.error);
      if (data.type === 'loading') { if (!active) document.getElementById('status').textContent = data.message; return; }
      if (data.type === 'progress') {
        const job = jobs.get(data.job_id); if (!job || job.state !== 'running') return;
        job.message = data.message.replace('Province candidate', 'Iteration');
        const match = /candidate (\d+)\/(\d+)/.exec(data.message);
        job.progress = match ? .15 + .75 * Number(match[1]) / Number(match[2]) : .05;
        return;
      }
      if (data.type === 'response') {
        const request = pending.get(data.id); if (!request) return;
        pending.delete(data.id); clearTimeout(request.timer);
        if (data.error) request.reject(new Error(data.error)); else request.resolve(data.value);
      }
    };
  }
  function rpc(payload) {
    ensureWorker();
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      // Generation may take time on slower devices; Cancel remains available.
      const timer = payload.path === '/api/config' ? setTimeout(() => failWorker('Loading timed out. Check your connection and reload the page.'), 120000) : null;
      pending.set(id, {resolve, reject, timer});
      const restore = restoreNeeded && latest ? {id: latest.id, files: savedFiles} : null;
      restoreNeeded = false;
      worker.postMessage({id, payload, restore});
    });
  }
  function artifacts(result, files) {
    const urls = {};
    for (const [name, content] of Object.entries(files)) {
      if (name === 'index.html') continue;
      urls[name] = URL.createObjectURL(new Blob([content], {type: name.endsWith('.svg') ? 'image/svg+xml' : 'application/json'}));
    }
    // This in-tab preview can link to its sibling artifacts through blob URLs.
    let html = files['index.html'];
    for (const [name, url] of Object.entries(urls)) html = html.split(`="${name}"`).join(`="${url}"`);
    urls['index.html'] = URL.createObjectURL(new Blob([html], {type: 'text/html'}));
    const old = latest;
    result.urls = urls; latest = result; savedFiles = files;
    // Allow the image element and download links time to switch to the new result.
    if (old) setTimeout(() => Object.values(old.urls).forEach(url => URL.revokeObjectURL(url)), 3000);
    return result;
  }
  cancel.addEventListener('click', () => failWorker('Generation cancelled. Previous map retained.'));

  async function api(path, values) {
    if (path === '/api/latest') return latest;
    if (path.startsWith('/api/jobs/')) {
      const job = jobs.get(path.split('/').pop());
      if (!job) throw new Error('Unknown generation');
      return job;
    }
    if (path === '/api/generate' || path === '/api/rerun') {
      if (active) throw new Error('A map is already generating.');
      const id = Array.from(crypto.getRandomValues(new Uint8Array(8)), v => v.toString(16).padStart(2, '0')).join('');
      jobs.clear(); active = id; cancel.hidden = false;
      jobs.set(id, {id, state: 'running', message: 'Generating in your browser...', progress: 0});
      rpc({path, values, job_id: id}).then(({result, files}) => {
        jobs.set(id, artifacts(result, files));
      }).catch(error => jobs.set(id, {id, state: 'error', message: error.message, progress: 0}))
        .finally(() => { active = null; cancel.hidden = true; });
      return {id};
    }
    return rpc({path, values});
  }
  return {api};
})();
