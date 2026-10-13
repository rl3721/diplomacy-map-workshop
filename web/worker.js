// The Python engine runs off the UI thread. Nothing is sent to a generation server.
let python;
let queue = Promise.resolve();
const boot = (async () => {
  self.postMessage({type: 'loading', message: 'Loading the Python engine for your browser...'});
  const {loadPyodide} = await import('https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs');
  python = await loadPyodide();
  const response = await fetch(new URL('python/manifest.json', import.meta.url));
  if (!response.ok) throw new Error('Could not load the generator manifest.');
  const files = await response.json();
  python.FS.mkdirTree('/workshop');
  await Promise.all(files.map(async name => {
    const source = await fetch(new URL(`python/${name}`, import.meta.url));
    if (!source.ok) throw new Error(`Could not load ${name}.`);
    python.FS.writeFile(`/workshop/${name}`, await source.text(), {encoding: 'utf8'});
  }));
  python.runPython("import sys\nsys.path.insert(0, '/workshop')\nfrom browser_api import request");
  self.postMessage({type: 'ready'});
})();
boot.catch(error => self.postMessage({type: 'fatal', error: `Browser engine could not load: ${error.message}. Check your connection and reload.`}));

self.onmessage = event => {
  queue = queue.then(async () => {
    const {id, payload, restore} = event.data;
    try {
      await boot;
      if (restore) {
        if (!/^[a-f0-9]{16}$/.test(restore.id)) throw new Error('Invalid saved run.');
        const folder = `/workshop/output/${restore.id}`;
        python.FS.mkdirTree(folder);
        for (const [name, content] of Object.entries(restore.files)) {
          if (!/^[a-zA-Z0-9_.]+$/.test(name)) throw new Error('Invalid artifact.');
          python.FS.writeFile(`${folder}/${name}`, content, {encoding: 'utf8'});
        }
      }
      self.generationProgress = message => self.postMessage({type: 'progress', job_id: payload.job_id, message: String(message)});
      python.globals.set('request_json', JSON.stringify(payload));
      const result = python.runPython("from js import generationProgress\nrequest(request_json, generationProgress)");
      self.postMessage({type: 'response', id, value: JSON.parse(result)});
    } catch (error) {
      self.postMessage({type: 'response', id, error: error.message});
    }
  });
};
