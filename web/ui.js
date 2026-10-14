'use strict';
const $ = id => document.getElementById(id);
const state = {defaults: null, presets: null, parameters: {}, token: '', result: null, stage: '03_provinces.svg', zoom: 1, busy: false, targetRequest: 0};
const controls = new Map();
const terrainKeys = ['land_fraction', 'landmass_scale', 'roughness'];
const help = {
  sc_enabled: 'Place supply centers on passable land. Symmetric power assignment follows automatically. Disable for province-only generation.',
  sc_richness: 'Scales the full supply-center budget: fixed base 5.2 × players × actual province-count ratio × richness. Rounded once to the nearest integer, with halves rounded up. Defaults to 1.0; range 0.8–1.2. The base cannot be edited.',
  sc_coastal_preference: 'Multiplies the eligible coastal-land share to set a soft coastal-center target. 1.0 is proportional placement, 0 favors inland, 2 favors coasts. Feasibility limits are applied.',
  sc_distribution: '0 favors clusters of nearby centers; 1 favors greater separation. Uses shortest paths through passable land, with sea access evaluated separately. Adjacent centers remain allowed.',
  global_seed: 'Master seed for all stages. Terrain, province and SC seeds are derived automatically. Blank creates a random master seed for Generate map. Rerun generates fresh seeds for the selected stage and all later stages, preserving earlier stages. The actual stage seeds are saved with settings so a rerun result can be reproduced.',
  sc_iterations: 'Number of SC placements compared using spacing (40%), regional distribution (30%), coastal mix (20%) and accessibility (10%). This does not measure balance between players yet.',
  impassable_enabled: 'Mark the highest land provinces as black impassable areas. Ranking uses average elevation across each province. Impassable areas cannot be entered, occupied, or crossed. Layouts with disconnected playable regions or dead ends are rejected.',
  impassable_ratio: 'Share of land provinces made impassable, rounded down. Default 2% means one per 50 land provinces: 74 gives one, 100 gives two, fewer than 50 gives none. Zero also disables placement.',
  land_fraction: 'Fraction of the initial map area assigned to land. Cleanup can slightly change the final percentage. This is different from the number of land provinces.',
  landmass_scale: 'Size of elevation features. Increase for broader landmasses and seas; decrease for smaller features. Changing this slider selects Custom terrain.',
  roughness: 'Strength of fine elevation detail. Higher values generally make coastlines more irregular and introduce smaller features. Changing this slider selects Custom terrain.',
  topology: 'Flat has open edges. Horizontal wrap connects left to right. Sphere closes the globe and shortens routes around the poles. All previews remain rectangular; polar regions look stretched on Sphere.',
  hex_count: 'Number of starting cells, not provinces. More cells give finer boundaries and take longer. Minimum land and water areas scale automatically with this resolution. Sphere uses equal-area cells rather than regular hexagons.',
  aspect_ratio: 'Map width divided by height. On flat and wrapped maps this changes the grid shape. On Sphere it changes only the rectangular display, not terrain or province connections.',
  min_land_fraction: 'Minimum connected land area as a percentage of the entire map. Smaller islands are converted to water. The default 3.6% equals 180 cells at resolution 5,000, or 1,800 at 50,000. This does not constrain province size or peninsula width. Zero disables this cleanup.',
  min_water_fraction: 'Minimum connected water area as a percentage of the entire map. Smaller lakes or seas are converted to land. The default 3.6% equals 180 cells at resolution 5,000, or 1,800 at 50,000. Zero disables this cleanup.',
  asymmetric: 'Multiplies the player-based province capacity by 1.5 before province division; supply centers scale with the resulting province count. Power assignment for asymmetric games is not implemented yet. Rerun from Provinces or earlier to apply this change.',
  players: 'Sets the base province count using the automatic regional reference: about 14.1 provinces per player. Changing players preserves your province-count multiplier. Symmetric mode assigns three starting home centers per player.',
  province_count: 'Exact number of provinces to generate. The slider and number box allow 0.5 to 1.5 times the player-based count, rounded inward to whole provinces and limited by available cells. Numbers outside that range are clamped when entered.',
  land_province_fraction: 'Fraction of provinces assigned to land, not land area. The default 0.75 requests about three land provinces for each sea province. Counts are rounded; incompatible terrain components can make a requested allocation impossible.',
  inland_ratio: 'Multiplier for the target share of land provinces with no sea neighbor. At 1.00 the automatic reference targets about 26.6% landlocked land provinces. It affects province seed placement and selection, not terrain. This is a soft target.',
  connectivity_ratio: 'Multiplier for reference neighbor-count distributions. Higher values favor layouts with more neighbors per province. This selects among iterations; it does not create artificial connections. Any province with exactly one distinct neighbor makes the layout illegal. Two-neighbor provinces are allowed but reduce the final score.',
  shape_regularity: 'Strength of growth and repair penalties against long extensions and excessive borders. Higher values favor more compact provinces. Natural coastlines can still impose narrow shapes.',
  size_flexibility: 'How much province size can deviate before repair penalizes it. At 0.30, target size divided by 1.3 through target size multiplied by 1.3 is unpenalized. Higher values give shape improvement more freedom. This is not a hard size limit.',
  candidates: 'Number of alternative province divisions to try over the same terrain. The fixed internal scoring system keeps the best one. More iterations take longer; they do not generate different terrain.',
  size_variation: 'Spread of sampled province-size targets. Zero requests similar sizes within each terrain component. Larger values produce a wider mixture of small and large targets. Actual sizes may differ.',
  compactness: 'Controls small random variations in growth cost. Higher values reduce growth noise. Shape regularity is the stronger control for avoiding long extensions.',
  repair_passes: 'Maximum rounds of boundary adjustments after growth. Repair balances size and shape while preserving connectivity. It stops early if there are no useful changes. Zero skips repair.',

};
const formats = {percent: v => `${Math.round(v * 100)}%`, ratio: v => `${Number(v).toFixed(2)}x`, decimal: v => Number(v).toFixed(2), scale: v => Number(v).toFixed(3)};

async function api(path, data) {
  if (window.workshopBrowser) return window.workshopBrowser.api(path, data);
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
function selectCustom() {
  for (const key of terrainKeys) if (state.parameters[key] === -1) state.parameters[key] = state.presets[state.parameters.terrain_style][key];
  state.parameters.terrain_style = 'custom';
  updatePresetButtons();
}
function updatePresetButtons() {
  document.querySelectorAll('[data-preset]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.preset === state.parameters.terrain_style)));
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
  input.addEventListener('input', () => { if (terrainKeys.includes(key)) selectCustom(); state.parameters[key] = Number(input.value); display(Number(input.value)); changed(); });
  controls.set(key, display);
}
function numberField(parent, key, label, min, max, step = 1) {
  const field = document.createElement('div'); field.className = 'compact-field';
  field.innerHTML = `<label for="${key}">${label}</label><input type="number" id="${key}" min="${min}" max="${max}" step="${step}" required>`;
  parent.append(field); const input = $(key);
  input.addEventListener('input', () => { state.parameters[key] = input.value === '' ? null : Number(input.value); if (key === 'players' || key === 'hex_count') syncProvinceCount(); changed(); });
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
  controls.set('asymmetric', value => { $('asymmetric').checked = value; });
  $('asymmetric').addEventListener('change', () => { state.parameters.asymmetric = $('asymmetric').checked; syncProvinceCount(); changed(); });
  rangeField($('terrain-sliders'), 'land_fraction', 'Land coverage', 0, 1, .01, 'percent');
  rangeField($('terrain-sliders'), 'landmass_scale', 'Feature scale', .01, .5, .001, 'scale');
  rangeField($('terrain-sliders'), 'roughness', 'Elevation detail', 0, 1, .01, 'decimal');
  numberField($('terrain-advanced'), 'hex_count', 'Hex resolution', 1, 500000);
  numberField($('terrain-advanced'), 'aspect_ratio', 'Aspect ratio', .2, 5, .1);
  for (const kind of ['land', 'water']) {
    const key = `min_${kind}_fraction`;
    const field = document.createElement('div'); field.className = 'compact-field';
    field.innerHTML = `<label for="${key}">Minimum ${kind} area (%)</label><input id="${key}" type="number" min="0" max="100" step="any" required>`;
    $('terrain-advanced').append(field);
    controls.set(key, value => { $(key).value = Number((value * 100).toFixed(6)); });
    $(key).addEventListener('input', () => { state.parameters[key] = $(key).value === '' ? null : Number($(key).value) / 100; changed(); });
  }
  numberField($('province-sliders'), 'players', 'Number of players', 1, 100);
  const count = document.createElement('div'); count.className = 'range-field';
  count.innerHTML = '<label for="province_count">Province count</label><div class="count-input"><input id="province-count-slider" type="range" aria-label="Province count slider" step="1"><input id="province_count" type="number" step="1" required></div><p id="count-range" class="hint"></p>';
  $('province-sliders').append(count);
  $('province-count-slider').addEventListener('input', () => { syncProvinceCount(Number($('province-count-slider').value)); changed(); });
  $('province_count').addEventListener('change', () => { syncProvinceCount(Number($('province_count').value)); changed(); });
  $('province_count').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); syncProvinceCount(Number($('province_count').value)); changed(); } });
  numberField($('province-sliders'), 'land_province_fraction', 'Land province share', 0, 1, .01);
  rangeField($('province-sliders'), 'inland_ratio', 'Landlocked rate', .8, 1.2, .01, 'ratio', true);
  rangeField($('province-sliders'), 'connectivity_ratio', 'Connectivity', .8, 1.2, .01, 'ratio', true);
  rangeField($('province-advanced'), 'shape_regularity', 'Shape regularity', 0, 1, .01, 'decimal', true);
  rangeField($('province-advanced'), 'size_flexibility', 'Size flexibility', 0, 1, .01, 'decimal', true);
  numberField($('province-advanced'), 'candidates', 'Iterations', 1, 100);
  numberField($('province-advanced'), 'size_variation', 'Size variation', 0, 2, .05);
  numberField($('province-advanced'), 'compactness', 'Compactness', 0, 1, .05);
  numberField($('province-advanced'), 'repair_passes', 'Repair passes', 0, 30);
  const blocked = document.createElement('div'); blocked.className = 'compact-field';
  blocked.innerHTML = '<label for="impassable_enabled">Impassable highlands</label><input id="impassable_enabled" type="checkbox" style="width:auto;justify-self:start">';
  $('province-advanced').append(blocked);
  controls.set('impassable_enabled', value => { $('impassable_enabled').checked = value; });
  $('impassable_enabled').addEventListener('change', () => { state.parameters.impassable_enabled = $('impassable_enabled').checked; changed(); });
  rangeField($('province-advanced'), 'impassable_ratio', 'Impassable land share', 0, 1, .01, 'percent');
  const scToggle = document.createElement('div'); scToggle.className = 'compact-field';
  scToggle.innerHTML = '<label for="sc_enabled">Place supply centers</label><input id="sc_enabled" type="checkbox" style="width:auto;justify-self:start">';
  $('sc-controls').append(scToggle);
  controls.set('sc_enabled', value => { $('sc_enabled').checked = value; });
  $('sc_enabled').addEventListener('change', () => { state.parameters.sc_enabled = $('sc_enabled').checked; changed(); });
  rangeField($('sc-controls'), 'sc_richness', 'Richness', .8, 1.2, .01, 'ratio');
  rangeField($('sc-controls'), 'sc_coastal_preference', 'Coastal preference', 0, 2, .05, 'ratio');
  rangeField($('sc-controls'), 'sc_distribution', 'Distribution', 0, 1, .05, 'decimal');
  numberField($('sc-controls'), 'sc_iterations', 'Placement iterations', 1, 100);
  installHelp();
}
function syncProvinceCount(explicit) {
  const p = state.parameters;
  const base = state.bases[p.players] * (p.asymmetric ? 1.5 : 1);
  if (!base || !Number.isInteger(p.hex_count) || p.hex_count < 1) return;
  const min = Math.min(p.hex_count, Math.ceil(base * .5)), max = Math.min(p.hex_count, Math.floor(base * 1.5));
  const value = Math.max(min, Math.min(max, Math.round(Number.isFinite(explicit) ? explicit : base * p.size_ratio)));
  p.province_count = value;
  if (explicit !== undefined) p.size_ratio = Math.max(.5, Math.min(1.5, value / base));
  for (const id of ['province_count', 'province-count-slider']) { $(id).min = min; $(id).max = max; $(id).value = value; }
  $('province-count-slider').style.setProperty('--fill', `${max === min ? 100 : 100 * (value - min) / (max - min)}%`);
  $('count-range').textContent = `Base ${base} · Range ${min}–${max} provinces`;
}
function installHelp() {
  const tooltip = $('parameter-tooltip');
  for (const [key, text] of Object.entries(help)) {
    const label = document.querySelector(`label[for="${key}"]`); if (!label) continue;
    label.classList.add('has-help'); label.tabIndex = 0;
    const show = () => {
      tooltip.textContent = text; tooltip.hidden = false; label.setAttribute('aria-describedby', 'parameter-tooltip');
      const rect = label.getBoundingClientRect(), box = tooltip.getBoundingClientRect();
      tooltip.style.left = `${Math.max(8, Math.min(rect.left, innerWidth - box.width - 8))}px`;
      tooltip.style.top = `${Math.max(8, rect.bottom + box.height + 10 < innerHeight ? rect.bottom + 6 : rect.top - box.height - 6)}px`;
    };
    const hide = () => { tooltip.hidden = true; label.removeAttribute('aria-describedby'); };
    label.addEventListener('mouseenter', show); label.addEventListener('mouseleave', hide);
    label.addEventListener('focus', show); label.addEventListener('blur', hide);
    label.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); });
  }
  document.addEventListener('scroll', () => { tooltip.hidden = true; }, true);
}
function applyParameters(parameters) {
  state.parameters = {...state.defaults, ...parameters};
  delete state.parameters.sc_starting_per_player;
  delete state.parameters.sc_neutral_per_player;
  for (const key of Object.keys(state.defaults)) if (key.startsWith('weight_') || key.endsWith('_tolerance') || ['province_style', 'reference_profile'].includes(key)) state.parameters[key] = state.defaults[key];
  for (const kind of ['land', 'water']) {
    if (parameters[`min_${kind}_component`] >= 0) state.parameters[`min_${kind}_fraction`] = Math.min(1, parameters[`min_${kind}_component`] / state.parameters.hex_count);
    state.parameters[`min_${kind}_component`] = -1;
  }
  if (state.parameters.land_province_fraction === -1) state.parameters.land_province_fraction = .75;
  const preset = state.presets[state.parameters.terrain_style];
  if (state.parameters.terrain_style !== 'custom' && terrainKeys.some(key => state.parameters[key] !== -1 && Math.abs(state.parameters[key] - preset[key]) > 1e-9)) selectCustom();
  for (const [key, display] of controls) display(['land_fraction', 'landmass_scale', 'roughness'].includes(key) && state.parameters[key] === -1 ? preset[key] : state.parameters[key]);
  updatePresetButtons();
  $('topology').value = state.parameters.topology === 'auto' ? (state.parameters.wrap_x ? 'cylinder' : 'flat') : state.parameters.topology;
  topologyHint();
  syncProvinceCount(state.parameters.province_count > 0 ? state.parameters.province_count : undefined);
  $('global_seed').value = state.parameters.global_seed ?? '';
  refreshTargets();
}
function parameters() {
  const values = {...state.parameters};
  const text = $('global_seed').value.trim();
  if (text && (!/^[+-]?\d+$/.test(text) || !Number.isSafeInteger(Number(text)))) throw new Error('Global seed must be a whole number, or blank for random.');
  values.global_seed = text ? Number(text) : null;
  if (values.global_seed !== state.parameters.global_seed) for (const key of ['terrain_seed_override', 'province_seed_override', 'sc_seed_override', 'power_seed_override']) values[key] = null;
  return values;
}
function topologyHint() {
  $('topology-hint').textContent = {flat: 'Rectangular map with open edges.', cylinder: 'Left and right edges connect. North and south stay open.', sphere: 'Closed globe, rectangular preview. Polar areas look stretched; connections and areas are measured on the sphere.'}[$('topology').value];
}
let targetTimer;
function refreshTargets() {
  clearTimeout(targetTimer); const request = ++state.targetRequest;
  targetTimer = setTimeout(async () => {
    try {
      const target = await api('/api/targets', parameters());
      if (request !== state.targetRequest) return;
      const budget = target.supply_center_budget;
      $('sc-budget').textContent = state.parameters.sc_enabled ? `${budget.count} centers: 5.2 × ${budget.players} players × ${budget.province_ratio.toFixed(3)} province ratio × ${budget.richness.toFixed(2)} richness` : 'Supply-center placement disabled';
      $('target-summary').textContent = `Target: ${(target.inland_target * 100).toFixed(1)}% landlocked land provinces · ${target.mean_degree_target.toFixed(2)} neighbors`;
    } catch (error) { if (request === state.targetRequest) $('target-summary').textContent = error.message; }
  }, 160);
}
function busy(value) {
  state.busy = value; $('settings-fields').disabled = value;
  for (const id of ['generate', 'load-settings', 'save-settings']) $(id).disabled = value;
  $('rerun').disabled = $('rerun-stage').disabled = value || !state.result || state.result.parameters.global_seed == null;
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
  const img = $('map-image'); img.src = state.result.urls[stage]; img.alt = `Generated ${stage === '04_powers.svg' ? 'power map' : stage === '03_provinces.svg' ? 'province map' : stage === '02_cleaned.svg' ? 'cleaned terrain' : 'elevation map'}`;
  $('download-svg').href = img.src; $('download-svg').download = stage;
}
function showResult(result) {
  state.result = result; state.zoom = 1;
  $('empty-state').hidden = true; $('map-image').hidden = false;
  document.querySelectorAll('[data-stage]').forEach(button => { button.disabled = !result.urls[button.dataset.stage]; });
  for (const id of ['fit', 'zoom-out', 'zoom-in', 'details-button']) $(id).disabled = false;
  $('download-svg').classList.remove('disabled'); $('download-svg').setAttribute('aria-disabled', 'false');
  const counts = result.categories;
  $('map-stats').replaceChildren(...[`${result.province_count} source provinces`, `${result.playable_location_count ?? result.province_count} playable`, `${result.supply_centers?.count ?? 0} SCs`, `${result.impassable_count ?? 0} impassable`, `${counts.inland + counts.coastal} land`, `${counts.sea} sea`, `Score ${result.scoring.total.toFixed(1)}`].map(text => { const span = document.createElement('span'); span.textContent = text; return span; }));
  const powers = result.powers;
  $('power-summary').replaceChildren();
  const message = document.createElement('p'); message.textContent = powers?.message ?? 'Regenerate to assign powers.'; $('power-summary').append(message);
  for (const power of powers?.players ?? []) { const row = document.createElement('p'); row.textContent = `${power.id}: centers ${power.starting_centers.map(id => result.province_names?.[id] ?? id).join(', ')} ? victory ${power.vscc}`; row.style.borderLeft = `12px solid ${power.color}`; row.style.paddingLeft = '8px'; $('power-summary').append(row); }
  $('seed-status').textContent = `Global seed ${result.parameters.global_seed ?? 'legacy'}`;
  $('rerun').disabled = $('rerun-stage').disabled = state.busy || result.parameters.global_seed == null;
  $('status').textContent = `Map ready · ${result.elapsed_seconds.toFixed(1)} seconds`;
  setStage(result.urls[state.stage] ? state.stage : '03_provinces.svg');
}
async function generateMap(rerun = false) {
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
    const seedInput = $('global_seed').value;
    busy(true);
    if (!rerun) await api('/api/targets', config); $('status').textContent = 'Starting map generation'; $('progress').value = 0;
    const {id} = rerun ? await api('/api/rerun', {parameters: config, source_id: state.result.id, stage: $('rerun-stage').value}) : await api('/api/generate', config);
    let failures = 0;
    for (;;) {
      await new Promise(resolve => setTimeout(resolve, 450));
      let job;
      try { job = await api(`/api/jobs/${id}`); failures = 0; }
      catch (error) { if (++failures >= 5) throw error; continue; }
      $('status').textContent = job.message; $('progress').value = job.progress;
      if (job.state === 'error') throw new Error(job.message);
      if (job.state === 'complete') {
        if (rerun) {
          applyParameters(job.parameters);
          $('global_seed').value = seedInput;
        }
        showResult(job); break;
      }
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
  if (r.scoring.connectivity_policy) {
    const policy = r.scoring.connectivity_policy, note = document.createElement('p');
    note.textContent = `Weighted subtotal ${r.scoring.weighted_total.toFixed(2)} − two-neighbor penalty ${policy.penalty_points.toFixed(2)} = final score ${r.scoring.total.toFixed(2)}. Two-neighbor provinces: ${policy.two_neighbor_province_ids.map(id => r.province_names?.[id] ?? id).join(', ') || 'none'}. One-neighbor layouts are illegal and rejected.`;
    container.append(note);
  }
  if (r.supply_centers) { const sc = r.supply_centers, p = document.createElement('p'); const budget = sc.budget ? `Fixed base 5.2 × ${sc.budget.players} players × ${sc.budget.province_ratio.toFixed(3)} province ratio × ${sc.budget.richness.toFixed(2)} richness.` : 'Historical placement; regenerate to use the fixed 5.2 base.'; p.textContent = `${sc.count} supply centers. ${budget} Placement score: ${sc.score === null ? 'disabled / empty' : sc.score.toFixed(1)}. ${sc.note}`; container.append(p); }
  const shape = r.scoring.shape;
  for (const text of [`${r.categories.inland} inland, ${r.categories.coastal} coastal, ${r.categories.sea} sea provinces. Mean neighbors: ${r.degree.mean.toFixed(2)}.`, `Perimeter efficiency: ${shape.mean_perimeter_efficiency.toFixed(2)} average, ${shape.min_perimeter_efficiency.toFixed(2)} minimum. Shape-review provinces: ${shape.flagged_province_ids.map(id => r.province_names?.[id] ?? id).join(', ') || 'none'}.`, 'Scores describe map structure, not gameplay balance.', ...r.scoring.warnings]) { const p = document.createElement('p'); p.textContent = text; container.append(p); }
  const links = document.createElement('p'); links.className = 'download-links';
  for (const [file, title] of [['parameters.json', 'Exact parameters'], ['report.json', 'Full statistics'], ['map.json', 'Map data']]) { const a = document.createElement('a'); a.href = r.urls[file]; a.download = file; a.textContent = title; links.append(a); }
  container.append(links); $('details-dialog').showModal();
}
async function init() {
  try {
    const config = await api('/api/config'); state.defaults = config.defaults; state.presets = config.presets; state.token = config.token; state.bases = config.province_bases;
    buildControls(); applyParameters(state.defaults);
    $('status').textContent = 'Ready to generate';
    document.querySelectorAll('[data-preset]').forEach(button => button.addEventListener('click', () => { try { if (button.dataset.preset === 'custom') selectCustom(); else applyParameters({...parameters(), terrain_style: button.dataset.preset, land_fraction: -1, landmass_scale: -1, roughness: -1}); changed(); } catch (error) { showError(error.message); } }));
    $('topology').addEventListener('change', () => { state.parameters.topology = $('topology').value; state.parameters.wrap_x = $('topology').value !== 'flat'; topologyHint(); changed(); });
    $('global_seed').addEventListener('input', changed);
    $('generate').addEventListener('click', () => generateMap()); $('rerun').addEventListener('click', () => generateMap(true)); $('settings-form').addEventListener('submit', event => { event.preventDefault(); generateMap(); });
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
    $('save-settings').addEventListener('click', async () => { try { const values = parameters(); if (values.global_seed === null && state.result?.parameters.global_seed != null) { values.global_seed = state.result.parameters.global_seed; for (const key of ['terrain_seed_override', 'province_seed_override', 'sc_seed_override', 'power_seed_override']) values[key] = state.result.parameters[key] ?? null; } await api('/api/targets', values); downloadJSON(values, 'map-settings.json'); } catch (error) { showError(error.message); } });
    $('settings-file').addEventListener('change', async event => {
      const file = event.target.files[0]; if (!file) return;
      try { if (file.size > 65536) throw new Error('The parameter file is too large.'); const values = JSON.parse(await file.text()); await api('/api/targets', values); applyParameters(values); changed(); $('status').textContent = 'Settings loaded. Generate to preview them.'; }
      catch (error) { showError(`Cannot load settings: ${error.message}`); }
      finally { event.target.value = ''; }
    });
    const latest = await api('/api/latest');
    if (latest) { applyParameters(latest.parameters); showResult(latest); $('status').textContent = 'Previous map restored. Ready to generate.'; }
    $('settings-fields').disabled = false; $('generate').disabled = false;
  } catch (error) { showError(error.message); $('status').textContent = window.workshopBrowser ? 'Could not load the browser engine. Check your connection and reload.' : 'Could not connect. Start the application with python -m mapgen.app.'; }
}
init();
