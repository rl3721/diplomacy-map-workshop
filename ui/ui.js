'use strict';
const $ = id => document.getElementById(id);
const state = {defaults: null, presets: null, parameters: {}, token: '', result: null, stage: '03_provinces.svg', zoom: 1, busy: false, targetRequest: 0};
const controls = new Map();
const formats = {percent: v => `${Math.round(v * 100)}%`, ratio: v => `${Number(v).toFixed(2)}x`, decimal: v => Number(v).toFixed(2), scale: v => Number(v).toFixed(3)};

async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Workshop-Token': state.token}, body: JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The request failed.');
  return result;
}
function showError(message) { $('error').textContent = message; $('error').hidden = !message; }
function changed() {
  showError('');
  $('status').textContent = state.result ? 'Settings changed. Generate to update the preview.' : 'Ready to generate';
  refreshTargets();
}
function rangeField(parent, key, label, min, max, step, format, compact = false) {
  const field = document.createElement('div'); field.className = compact ? 'compact-field' : 'range-field';
  field.innerHTML = `<label for="${key}">${label}</label><div class="range-input"><input id="${key}" type="range" min="${min}" max="${max}" step="${step}"><output for="${key}" id="${key}-value"></output></div>`;
  parent.append(field);
  const input = $(key), output = $(`${key}-value`);
  function display(value) {
    input.min = Math.min(min, value); input.max = Math.max(max, value); input.value = value;
    output.textContent = formats[format](value);
    input.style.setProperty('--fill', `${100 * (Number(input.value) - Number(input.min)) / (Number(input.max) - Number(input.min))}%`);
    input.setAttribute('aria-valuetext', output.textContent);
  }
  input.addEventListener('input', () => { state.parameters[key] = Number(input.value); display(Number(input.value)); changed(); });
  controls.set(key, display);
}
function numberField(parent, key, label, min, max, step = 1) {
  const field = document.createElement('div'); field.className = 'compact-field';
  field.innerHTML = `<label for="${key}">${label}</label><input type="number" id="${key}" min="${min}" max="${max}" step="${step}" required>`;
  parent.append(field); const input = $(key);
  input.addEventListener('input', () => { state.parameters[key] = input.value === '' ? null : Number(input.value); changed(); });
  controls.set(key, value => { input.value = value; });
}
function selectField(parent, key, label, values) {
  const field = document.createElement('div'); field.className = 'compact-field';
  const title = document.createElement('label'); title.htmlFor = key; title.textContent = label;
  const select = document.createElement('select'); select.id = key;
  for (const [value, text] of values) { const option = document.createElement('option'); option.value = value; option.textContent = text; select.append(option); }
  field.append(title, select); parent.append(field);
  select.addEventListener('change', () => { state.parameters[key] = select.value; changed(); });
  controls.set(key, value => { select.value = value; });
}
function buildControls() {
  rangeField($('terrain-sliders'), 'land_fraction', 'Land coverage', 0, 1, .01, 'percent');
  rangeField($('terrain-sliders'), 'landmass_scale', 'Feature scale', .01, .5, .001, 'scale');
  rangeField($('terrain-sliders'), 'roughness', 'Elevation detail', 0, 1, .01, 'decimal');
  numberField($('terrain-advanced'), 'hex_count', 'Hex resolution', 1, 500000);
  numberField($('terrain-advanced'), 'aspect_ratio', 'Aspect ratio', .2, 5, .1);
  numberField($('terrain-advanced'), 'min_land_component', 'Minimum land area', 0, 500000);
  numberField($('terrain-advanced'), 'min_water_component', 'Minimum water area', 0, 500000);
  numberField($('province-sliders'), 'players', 'Players', 1, 100);
  rangeField($('province-sliders'), 'size_ratio', 'Map size', .8, 1.2, .01, 'ratio', true);
  rangeField($('province-sliders'), 'inland_ratio', 'Inland rate', .8, 1.2, .01, 'ratio', true);
  rangeField($('province-sliders'), 'connectivity_ratio', 'Connectivity', .8, 1.2, .01, 'ratio', true);
  rangeField($('province-sliders'), 'shape_regularity', 'Shape regularity', 0, 1, .01, 'decimal', true);
  rangeField($('province-sliders'), 'size_flexibility', 'Size flexibility', 0, 1, .01, 'decimal', true);
  selectField($('province-advanced'), 'province_style', 'Target profile', [['peninsula', 'Peninsula'], ['continental', 'Continental'], ['islands', 'Islands']]);
  selectField($('province-advanced'), 'reference_profile', 'Variant reference', [['auto', 'Auto'], ['peninsula', 'Regional'], ['classic', 'Classic'], ['world', 'World']]);
  numberField($('province-advanced'), 'land_province_fraction', 'Land province share', -1, 1, 'any');
  const note = document.createElement('p'); note.className = 'advanced-note'; note.textContent = 'Land province share: −1 uses the reference target. Terrain presets do not change province targets.'; $('province-advanced').append(note);
  numberField($('province-advanced'), 'candidates', 'Candidate layouts', 1, 100);
  numberField($('province-advanced'), 'size_variation', 'Size variation', 0, 2, .05);
  numberField($('province-advanced'), 'compactness', 'Compactness', 0, 1, .05);
  numberField($('province-advanced'), 'repair_passes', 'Repair passes', 0, 30);
  for (const [name, label] of [['degree', 'Connectivity'], ['composition', 'Composition'], ['global', 'Travel structure'], ['size', 'Province size'], ['shape', 'Province shape']]) numberField($('scoring-fields'), `weight_${name}`, `${label} weight`, 0, 1000, 'any');
  for (const name of ['degree', 'composition', 'path', 'fragmentation', 'bottleneck', 'size', 'shape']) numberField($('scoring-fields'), `${name}_tolerance`, `${name[0].toUpperCase() + name.slice(1)} tolerance`, .000001, 10000, 'any');
}
function applyParameters(parameters) {
  state.parameters = {...state.defaults, ...parameters};
  const preset = state.presets[state.parameters.terrain_style];
  for (const [key, display] of controls) display(['land_fraction', 'landmass_scale', 'roughness'].includes(key) && state.parameters[key] === -1 ? preset[key] : state.parameters[key]);
  document.querySelectorAll('[data-preset]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.preset === state.parameters.terrain_style)));
  $('wrap_x').checked = state.parameters.wrap_x;
  $('exact-count').checked = state.parameters.province_count > 0;
  $('province_count').disabled = !$('exact-count').checked;
  $('province_count').value = state.parameters.province_count || 99;
  for (const key of ['seed', 'division_seed']) $(key).value = state.parameters[key] ?? '';
  refreshTargets();
}
function parameters() {
  const values = {...state.parameters};
  for (const key of ['seed', 'division_seed']) {
    const text = $(key).value.trim();
    if (text && (!/^[+-]?\d+$/.test(text) || !Number.isSafeInteger(Number(text)))) throw new Error(`${key === 'seed' ? 'Terrain' : 'Province'} seed must be a whole number, or blank for random.`);
    values[key] = text ? Number(text) : null;
  }
  return values;
}
let targetTimer;
function refreshTargets() {
  clearTimeout(targetTimer); const request = ++state.targetRequest;
  targetTimer = setTimeout(async () => {
    try {
      const target = await api('/api/targets', parameters());
      if (request !== state.targetRequest) return;
      $('target-summary').textContent = `Target: ${target.province_count} provinces · ${(target.inland_target * 100).toFixed(1)}% inland · ${target.mean_degree_target.toFixed(2)} neighbors`;
      if (!$('exact-count').checked) $('province_count').value = target.province_count;
    } catch (error) { if (request === state.targetRequest) $('target-summary').textContent = error.message; }
  }, 160);
}
function busy(value) {
  state.busy = value; $('settings-fields').disabled = value;
  for (const id of ['generate', 'load-settings', 'save-settings']) $(id).disabled = value;
  $('generate').textContent = value ? 'Generating…' : 'Generate map'; $('progress').hidden = !value;
}
function layoutImage() {
  const img = $('map-image'), viewport = $('map-viewport');
  if (!state.result || !img.naturalWidth) return;
  const w = viewport.clientWidth, h = viewport.clientHeight;
  const fit = Math.min(w / img.naturalWidth, h / img.naturalHeight);
  const width = img.naturalWidth * fit * state.zoom, height = img.naturalHeight * fit * state.zoom;
  img.style.width = `${width}px`; img.style.height = `${height}px`;
  $('map-content').style.width = `${Math.max(w, width)}px`; $('map-content').style.height = `${Math.max(h, height)}px`;
  $('zoom-value').textContent = `${Math.round(state.zoom * 100)}%`;
  $('zoom-in').disabled = state.zoom >= 4; $('zoom-out').disabled = state.zoom <= .5;
}
function setStage(stage) {
  state.stage = stage;
  document.querySelectorAll('[data-stage]').forEach(button => { const selected = button.dataset.stage === stage; button.setAttribute('aria-selected', String(selected)); button.tabIndex = selected ? 0 : -1; });
  if (!state.result) return;
  const img = $('map-image'); img.src = state.result.urls[stage]; img.alt = `Generated ${stage === '03_provinces.svg' ? 'province map' : stage === '02_cleaned.svg' ? 'cleaned terrain' : 'elevation map'}`;
  $('download-svg').href = img.src; $('download-svg').download = stage;
}
function showResult(result) {
  state.result = result; state.zoom = 1;
  $('empty-state').hidden = true; $('map-image').hidden = false;
  document.querySelectorAll('[data-stage]').forEach(button => { button.disabled = false; });
  for (const id of ['fit', 'zoom-out', 'zoom-in', 'details-button']) $(id).disabled = false;
  $('download-svg').classList.remove('disabled'); $('download-svg').setAttribute('aria-disabled', 'false');
  const counts = result.categories;
  $('map-stats').replaceChildren(...[`${result.province_count} provinces`, `${counts.inland + counts.coastal} land`, `${counts.sea} sea`, `Score ${result.scoring.total.toFixed(1)}`].map(text => { const span = document.createElement('span'); span.textContent = text; return span; }));
  $('seed-status').textContent = `Terrain seed ${result.parameters.seed} · Province seed ${result.parameters.division_seed}`;
  $('status').textContent = `Map ready · ${result.elapsed_seconds.toFixed(1)} seconds`;
  setStage(state.stage);
}
async function generateMap() {
  if (state.busy) return;
  showError('');
  try {
    // Native validity also catches empty numeric inputs in collapsed advanced sections.
    const invalid = $('settings-form').querySelector('input:invalid, select:invalid');
    if (invalid) {
      for (let ancestor = invalid.parentElement; ancestor; ancestor = ancestor.parentElement) if (ancestor.tagName === 'DETAILS') ancestor.open = true;
      invalid.reportValidity(); return;
    }
    const config = parameters();
    await api('/api/targets', config);
    busy(true); $('status').textContent = 'Starting map generation'; $('progress').value = 0;
    const {id} = await api('/api/generate', config);
    let failures = 0;
    for (;;) {
      await new Promise(resolve => setTimeout(resolve, 450));
      let job;
      try { job = await api(`/api/jobs/${id}`); failures = 0; }
      catch (error) { if (++failures >= 5) throw error; continue; }
      $('status').textContent = job.message; $('progress').value = job.progress;
      if (job.state === 'error') throw new Error(job.message);
      if (job.state === 'complete') { showResult(job); break; }
    }
  } catch (error) { showError(error.message); $('status').textContent = state.result ? 'Generation failed. Previous map retained.' : 'Generation could not finish.'; }
  finally { busy(false); }
}
function downloadJSON(value, name) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type: 'application/json'}));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function showDetails() {
  const r = state.result; if (!r) return;
  const container = $('details-content'); container.replaceChildren();
  const table = document.createElement('table'); table.innerHTML = '<thead><tr><th>Component</th><th>Score</th><th>Weight</th></tr></thead><tbody></tbody>';
  for (const [name, part] of Object.entries(r.scoring.components)) {
    const row = document.createElement('tr');
    for (const value of [name[0].toUpperCase() + name.slice(1), part.score.toFixed(1), `${Math.round(part.normalized_weight * 100)}%`]) { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); }
    table.tBodies[0].append(row);
  }
  container.append(table);
  const shape = r.scoring.shape;
  for (const text of [`${r.categories.inland} inland, ${r.categories.coastal} coastal, ${r.categories.sea} sea provinces. Mean neighbors: ${r.degree.mean.toFixed(2)}.`, `Perimeter efficiency: ${shape.mean_perimeter_efficiency.toFixed(2)} average, ${shape.min_perimeter_efficiency.toFixed(2)} minimum. Shape-review provinces: ${shape.flagged_province_ids.join(', ') || 'none'}.`, 'Scores describe map structure, not gameplay balance.', ...r.scoring.warnings]) { const p = document.createElement('p'); p.textContent = text; container.append(p); }
  const links = document.createElement('p'); links.className = 'download-links';
  for (const [file, title] of [['parameters.json', 'Exact parameters'], ['report.json', 'Full statistics'], ['map.json', 'Map data']]) { const a = document.createElement('a'); a.href = r.urls[file]; a.download = file; a.textContent = title; links.append(a); }
  container.append(links); $('details-dialog').showModal();
}
async function init() {
  try {
    const config = await api('/api/config'); state.defaults = config.defaults; state.presets = config.presets; state.token = config.token;
    buildControls(); applyParameters(state.defaults);
    $('settings-fields').disabled = false; $('generate').disabled = false; $('status').textContent = 'Ready to generate';
    document.querySelectorAll('[data-preset]').forEach(button => button.addEventListener('click', () => { try { applyParameters({...parameters(), terrain_style: button.dataset.preset, land_fraction: -1, landmass_scale: -1, roughness: -1}); changed(); } catch (error) { showError(error.message); } }));
    $('wrap_x').addEventListener('change', () => { state.parameters.wrap_x = $('wrap_x').checked; changed(); });
    $('exact-count').addEventListener('change', () => { $('province_count').disabled = !$('exact-count').checked; state.parameters.province_count = $('exact-count').checked ? Number($('province_count').value) : 0; changed(); });
    $('province_count').addEventListener('input', () => { state.parameters.province_count = $('province_count').value === '' ? null : Number($('province_count').value); changed(); });
    for (const key of ['seed', 'division_seed']) $(key).addEventListener('input', changed);
    $('generate').addEventListener('click', generateMap); $('settings-form').addEventListener('submit', event => { event.preventDefault(); generateMap(); });
    $('reset').addEventListener('click', () => { applyParameters(state.defaults); changed(); });
    document.querySelectorAll('[data-stage]').forEach(button => {
      button.addEventListener('click', () => setStage(button.dataset.stage));
      button.addEventListener('keydown', event => {
        const tabs = [...document.querySelectorAll('[data-stage]')];
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const index = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (tabs.indexOf(button) + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length;
        tabs[index].focus(); setStage(tabs[index].dataset.stage);
      });
    });
    $('map-image').addEventListener('load', layoutImage);
    $('map-image').addEventListener('error', () => showError('The preview could not load. Try another stage or generate again.'));
    new ResizeObserver(layoutImage).observe($('map-viewport'));
    $('fit').addEventListener('click', () => { state.zoom = 1; layoutImage(); $('map-viewport').scrollTo(0, 0); });
    $('zoom-in').addEventListener('click', () => { state.zoom = Math.min(4, state.zoom + .25); layoutImage(); });
    $('zoom-out').addEventListener('click', () => { state.zoom = Math.max(.5, state.zoom - .25); layoutImage(); });
    $('details-button').addEventListener('click', showDetails); $('close-details').addEventListener('click', () => $('details-dialog').close());
    $('load-settings').addEventListener('click', () => $('settings-file').click());
    $('save-settings').addEventListener('click', async () => { try { const values = parameters(); await api('/api/targets', values); downloadJSON(values, 'map-settings.json'); } catch (error) { showError(error.message); } });
    $('settings-file').addEventListener('change', async event => {
      const file = event.target.files[0]; if (!file) return;
      try { if (file.size > 65536) throw new Error('The parameter file is too large.'); const values = JSON.parse(await file.text()); await api('/api/targets', values); applyParameters(values); changed(); $('status').textContent = 'Settings loaded. Generate to preview them.'; }
      catch (error) { showError(`Cannot load settings: ${error.message}`); }
      finally { event.target.value = ''; }
    });
    const latest = await api('/api/latest');
    if (latest) { applyParameters(latest.parameters); showResult(latest); $('status').textContent = 'Previous map restored. Ready to generate.'; }
  } catch (error) { showError(error.message); $('status').textContent = 'Could not connect. Start the application with python app.py.'; }
}
init();
