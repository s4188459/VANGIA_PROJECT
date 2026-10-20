const $ = id => document.getElementById(id);
let state = {datasets: [], models: [], runs: []};
let currentRun = null, polling = null, selectedModels = new Set(), currentDatasetId = '';
let reportRequest = 0, backgroundPoll = null, resumePending = false;
const activeStatus = status => ['running', 'cancelling'].includes(status);
const pct = n => n == null ? '—' : `${(n * 100).toFixed(2)}%`;
const seconds = n => `${n.toFixed(1)} s`;
const statusText = s => ({running:'Running',cancelling:'Cancelling',loading:'Loading',queued:'Queued',completed:'Completed',completed_with_errors:'Completed with errors',cancelled:'Cancelled',error:'Error',interrupted:'Interrupted'})[s] || s;
function node(tag, text, cls) { const el = document.createElement(tag); if (text != null) el.textContent = text; if (cls) el.className = cls; return el; }
function notice(text, error = false) { $('notice').textContent = text; $('notice').className = error ? 'error' : ''; $('notice').hidden = !text; }
async function api(path, options) { const r = await fetch(path, options); const value = await r.json(); if (!r.ok) throw new Error(value.error || `HTTP ${r.status}`); return value; }
const post = (path, data) => api(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
function updateRunButton() {
  const busy = resumePending || state.runs.some(r => activeStatus(r.status));
  $('run').disabled = busy;
  $('resume').disabled = busy;
}
function watchBackgroundRun() {
  clearTimeout(backgroundPoll);
  const active = state.runs.find(r => activeStatus(r.status));
  if (!active || active.id === currentRun?.id) return;
  backgroundPoll = setTimeout(async () => {
    try {
      const run = await api(`/api/runs/${active.id}`);
      const saved = state.runs.find(r => r.id === run.id);
      if (saved) saved.status = run.status;
      updateRunButton();
    } catch (e) { notice(e.message, true); }
    watchBackgroundRun();
  }, 1500);
}
function option(value, text) { const el = node('option', text); el.value = value; return el; }
async function refresh() {
  state = await api('/api/state');
  const oldDataset = $('dataset').value;
  $('dataset').replaceChildren(option('', 'Select dataset'));
  state.datasets.forEach(d => $('dataset').append(option(d.id, `${d.name} · ${d.samples.length} samples`)));
  $('dataset').value = state.datasets.some(d => d.id === oldDataset) ? oldDataset : state.datasets[0]?.id || '';
  const oldRun = $('history').value;
  $('history').replaceChildren(option('', 'Select run'));
  state.runs.forEach(r => $('history').append(option(r.id, `${new Date(r.created_at).toLocaleString('en-US')} · ${r.dataset_name}`)));
  $('history').value = oldRun;
  renderModels();
  renderCatalog();
  backendControls(false);
  await renderDataset();
}
function renderModels() {
  $('model-list').replaceChildren();
  if (!state.models.length) $('model-list').append(node('p', 'Add a local model path to get started.', 'hint'));
  state.models.forEach(model => {
    const label = node('label', null, 'model-choice'); const input = node('input'); input.type = 'checkbox'; input.checked = selectedModels.has(model.label);
    input.onchange = () => { if (input.checked) selectedModels.add(model.label); else selectedModels.delete(model.label); };
    const body = node('span', model.label); body.append(node('small', `${model.backend} · ${model.device.toUpperCase()} ${model.compute_type} · ${(model.languages || (model.model.endsWith('.en') || model.model.endsWith('-en') ? ['en'] : ['en','vi'])).join('/')} ${model.python_executable ? '· Separate Python environment' : state.backends?.[model.backend]?.installed === false ? '· missing dependencies' : ''}`));
    label.title = model.model; label.append(input, body); $('model-list').append(label);
  });
}
function renderCatalog() {
  const old = $('catalog').value, lang = $('catalog-language').value || 'all';
  const rows = (state.catalog || []).filter(m => lang === 'all' || m.languages.includes(lang));
  $('catalog').replaceChildren(...rows.map(m => option(`${m.backend}|${m.model}`, `${m.label} · ${m.languages.join('/')} · ${m.backend}`)));
  if (rows.some(m => `${m.backend}|${m.model}` === old)) $('catalog').value = old;
  catalogNote();
}
function chosenPreset() { return (state.catalog || []).find(m => `${m.backend}|${m.model}` === $('catalog').value); }
function batchModels() {
  const dataset = state.datasets.find(d => d.id === $('dataset').value);
  const scope = $('model-scope').value || 'manual', skipped = [];
  if (scope === 'manual') return {models:state.models.filter(m=>selectedModels.has(m.label)), skipped};
  if (!dataset) return {models:[], skipped:['Select a dataset first.']};
  const curated = ['vi-video','vi-live'].includes(scope);
  if (curated && dataset.language !== 'vi') return {models:[], skipped:['Select a Vietnamese dataset containing reviewed Vietnamese-English speech.']};
  const language = m => {
    const known = (state.catalog || []).find(p=>p.backend===m.backend && p.model===m.model);
    const name = m.model.replaceAll('\\','/').split('/').pop();
    return known?.languages || m.languages || (name.endsWith('.en') || name.endsWith('-en') || name.startsWith('distil-') ? ['en'] : ['en','vi']);
  };
  const models = [];
  function add(m) {
    if (!language(m).includes(dataset.language)) return;
    if (state.backends?.[m.backend]?.import_checked === false) { skipped.push(`${m.label}: backend import failed; check configuration`); return; }
    if (['elevenlabs','google-chirp'].includes(m.backend) && state.backends?.[m.backend]?.credentials === false) { skipped.push(`${m.label}: cloud credentials not configured`); return; }
    if (['elevenlabs','google-chirp'].includes(m.backend) && !$('cloud-consent').checked) { skipped.push(`${m.label}: cloud uploads not authorized`); return; }
    if (!m.python_executable && state.backends?.[m.backend]?.installed === false) { skipped.push(`${m.label}: backend not installed`); return; }
    models.push(m);
  }
  if (curated) {
    (state.catalog || []).filter(p => p.sets?.includes(scope)).forEach(p => {
      const fw = p.backend === 'faster-whisper';
      add({...p, label:`${p.label} [${scope}]`, device:'cpu', compute_type:fw?'int8':'float32',
        beam_size:fw || p.backend==='transformers-whisper'?5:1, cpu_threads:4, vad_filter:fw,
        allow_download:$('batch-download').checked === true,
        python_executable:state.backends?.[p.backend]?.python_executable || ''});
    });
    return {models, skipped};
  }
  state.models.forEach(add);
  if (scope === 'catalog') (state.catalog || []).forEach(p => {
    // Prefer saved configurations, including local faster-whisper checkpoint paths.
    const equivalent = m => m.backend===p.backend && (m.model===p.model || (p.backend==='vosk' && m.model.replaceAll('\\','/').split('/').pop()===p.model) ||
      (p.backend==='faster-whisper' && m.model.replaceAll('\\','/').split('/').pop()===`faster-whisper-${p.model.replaceAll('.','-')}`));
    if (state.models.some(equivalent)) return;
    const fw = p.backend==='faster-whisper';
    let label = `${p.label} [catalog]`;
    while (models.some(m=>m.label===label)) label += '+';
    add({...p,label,device:'cpu',compute_type:fw?'int8':'float32',beam_size:fw || p.backend==='transformers-whisper'?5:1,
      cpu_threads:4,vad_filter:fw,allow_download:$('batch-download').checked === true,
      python_executable:state.backends?.[p.backend]?.python_executable || ''});
  });
  return {models,skipped};
}
function renderBatchPlan() {
  const scope = $('model-scope').value || 'manual';
  if (scope==='manual') { $('batch-plan').textContent=''; return; }
  const plan=batchModels();
  if (['vi-video','vi-live'].includes(scope)) {
    const members = (state.catalog || []).filter(p => p.sets?.includes(scope));
    $('batch-plan').textContent = `${scope==='vi-video'?'Video: whole-file evaluation.':'Live screening: run once at 1 second, then again at 2 seconds. This is a simulation, not microphone latency.'} ${plan.models.length}/${members.length} candidates ready for an attempt. One CPU baseline per model; saved configurations are not used. ` +
      members.map(p => `${p.label}: ${p.weight_status || 'Weights checked at load'}`).join('; ') +
      (plan.skipped.length ? ` Skipped: ${plan.skipped.join('; ')}.` : '');
    return;
  }
  $('batch-plan').textContent=`Will try ${plan.models.length} configurations matching the dataset language. Catalog presets use CPU defaults; saved configurations keep their settings. ${plan.skipped.length ? `Skipped ${plan.skipped.length}: ${plan.skipped.join('; ')}.` : ''}`;
}
$('model-scope').onchange = () => {
  const scope = $('model-scope').value;
  if (scope === 'vi-video') $('benchmark-mode').value = 'final';
  if (scope === 'vi-live') { $('benchmark-mode').value = 'live_replay'; $('chunk-seconds').value = '1'; }
  $('benchmark-mode').disabled = ['vi-video','vi-live'].includes(scope);
  renderBatchPlan();
};
$('batch-download').onchange = renderBatchPlan;
$('cloud-consent').onchange = renderBatchPlan;
function catalogNote() { $('catalog-note').textContent = chosenPreset()?.note || ''; }
function backendControls(reset = true) {
  const backend = $('backend').value || 'faster-whisper';
  const fw = backend === 'faster-whisper', beam = fw || backend === 'transformers-whisper';
  $('vad').disabled = !fw; $('beam').disabled = !beam;
  if (reset) { $('compute').value = fw ? 'int8' : 'float32'; $('vad').checked = fw; $('beam').value = beam ? '5' : '1'; }
  const info = state.backends?.[backend];
  if (reset) $('backend-python').value = info?.python_executable || '';
  $('backend-note').textContent = info ? (info.python_executable ? `Separate Python environment. ${info.note} See QA_REPORT for tested checkpoints.` : `${info.note} ${info.installed ? '' : `Run from the workspace: .\\stt-benchmark\\install-backend.ps1 -Backend ${backend}`}`) : '';
}
$('backend').onchange = () => backendControls();
$('catalog-language').onchange = renderCatalog;
$('catalog').onchange = catalogNote;
$('use-preset').onclick = () => {
  const preset = chosenPreset(); if (!preset) return;
  $('backend').value = preset.backend; backendControls();
  $('model-label').value = preset.label; $('model-path').value = preset.model;
  $('model-languages').value = preset.languages.join(',');
  $('download').checked = false; $('model-details').open = true;
  notice('Preset filled in. Review the device, model path and download permission, then save the configuration.');
};
async function renderDataset() {
  renderBatchPlan();
  const dataset = state.datasets.find(d => d.id === $('dataset').value);
  const changed = currentDatasetId !== (dataset?.id || '');
  currentDatasetId = dataset?.id || '';
  if (changed) $('reviewed').checked = false;
  $('preview').hidden = !dataset;
  $('dataset-meta').textContent = dataset ? `${dataset.language.toUpperCase()} · ${dataset.samples.length} valid pairs · ${(dataset.duration_s/60).toFixed(1)} min` : '';
  if (!dataset) { $('audio').removeAttribute('src'); return; }
  const oldSample = $('sample').value;
  $('sample').replaceChildren(...dataset.samples.map(s => option(s.id, `${s.id} · ${seconds(s.duration_s)}`)));
  if (!changed && dataset.samples.some(s => s.id === oldSample)) $('sample').value = oldSample;
  await preview();
}
async function preview() {
  const dataset = $('dataset').value, sample = $('sample').value;
  if (!dataset || !sample) return;
  const base = `/api/datasets/${dataset}/${sample}`;
  $('audio').src = `${base}/audio`;
  const reference = await api(`${base}/reference`);
  if ($('dataset').value === dataset && $('sample').value === sample) $('reference-preview').textContent = reference.text;
}
$('dataset').onchange = () => renderDataset().catch(e => notice(e.message, true));
$('sample').onchange = () => preview().catch(e => notice(e.message, true));
$('upload-form').onsubmit = async event => {
  event.preventDefault(); const file = $('zip').files[0]; if (!file) return;
  if (file.size > 512 * 1024 * 1024) return notice('Maximum ZIP size: 512 MB.', true);
  $('upload').disabled = true; $('upload').textContent = 'Importing & validating…'; notice('');
  try {
    const query = new URLSearchParams({name: $('dataset-name').value, language: $('language').value});
    const dataset = await api(`/api/datasets?${query}`, {method:'POST', headers:{'Content-Type':'application/zip'}, body:file});
    await refresh(); $('dataset').value = dataset.id; await renderDataset(); $('upload-details').open = false;
    notice(`Imported ${dataset.samples.length} valid pairs. Listen and review transcripts before running.`);
  } catch (e) { notice(e.message, true); }
  finally { $('upload').disabled = false; $('upload').textContent = 'Validate & import dataset'; }
};
$('model-form').onsubmit = async event => {
  event.preventDefault();
  try {
    const config = await post('/api/models', {label:$('model-label').value, model:$('model-path').value, backend:$('backend').value,
      device:$('device').value, compute_type:$('compute').value, beam_size:Number($('beam').value), cpu_threads:Number($('threads').value),
      languages:($('model-languages').value || 'en,vi').split(','),
      python_executable:$('backend-python').value || '',
      vad_filter:$('vad').checked, allow_download:$('download').checked});
    selectedModels.add(config.label); await refresh(); notice(`Saved configuration ${config.label}.`);
  } catch (e) { notice(e.message, true); }
};
$('run').onclick = async () => {
  if (!$('dataset').value) return notice('Import or select a dataset first.', true);
  if (!$('reviewed').checked) return notice('Confirm that you have listened to and reviewed the reference transcripts.', true);
  const scope = $('model-scope').value;
  if (['experiment2', 'experiment3'].includes($('benchmark-mode').value))
    return notice('This automatic model selection has been retired. Choose models explicitly.', true);
  if (scope === 'vi-live' && ![1,2].includes(Number($('chunk-seconds').value)))
    return notice('For the Vietnamese-English live baseline, choose 1 or 2 seconds and run each separately.', true);
  const {models} = batchModels();
  if (!models.length) return notice('Select at least one model configuration.', true);
  const missing = models.filter(m => !m.python_executable && state.backends?.[m.backend]?.installed === false);
  if (missing.length) return notice(`Backends not installed: ${[...new Set(missing.map(m=>m.backend))].join(', ')}. See the setup instructions in the configuration section.`, true);
  $('run').disabled = true; notice('');
  try {
    const run = await post('/api/runs', {dataset_id:$('dataset').value, models, references_reviewed:true,
      options:{mode:scope==='vi-video'?'final':scope==='vi-live'?'live_replay':$('benchmark-mode').value || 'final', sample_limit:Number($('sample-limit').value || 0), chunk_seconds:Number($('chunk-seconds').value || 3), allow_cloud:$('cloud-consent').checked === true}});
    await refresh(); $('history').value = run.id; await showRun(run.id);
  } catch (e) { notice(e.message, true); $('run').disabled = false; }
};
async function showRun(id) {
  const request = ++reportRequest;
  clearTimeout(polling);
  if (!id) { currentRun=null; $('report').hidden=true; $('empty').hidden=false; $('detail-card').hidden=true; updateRunButton(); watchBackgroundRun(); return; }
  const run = await api(`/api/runs/${id}`);
  if (request !== reportRequest) return;
  currentRun = run;
  const saved = state.runs.find(r => r.id === run.id);
  if (saved) saved.status = run.status;
  else state.runs.push({id:run.id,status:run.status});
  renderRun();
  watchBackgroundRun();
  if (activeStatus(currentRun.status)) polling = setTimeout(() => showRun(id).catch(e => notice(e.message,true)), 1500);
}
function renderRun() {
  const run = currentRun, active = activeStatus(run.status);
  $('empty').hidden = true; $('report').hidden = false; $('detail-card').hidden = false;
  updateRunButton();
  $('cancel').hidden = !active; $('cancel').disabled = run.status === 'cancelling';
  $('resume').hidden = run.status !== 'interrupted';
  $('run-message').textContent = ['completed', 'completed_with_errors', 'cancelled', 'interrupted'].includes(run.status) ? statusText(run.status) : run.message;
  $('progress').max = run.total_tasks; $('progress').value = run.completed_tasks;
  $('run-meta').textContent = `${statusText(run.status)} · ${run.dataset.name} · ${run.completed_tasks}/${run.total_tasks} tasks · ${run.dataset.language.toUpperCase()} · ${run.options?.mode === 'live_replay' ? `Chunks: ${run.options.chunk_seconds}s` : 'Whole file'}`;
  $('summary').replaceChildren();
  $('run-meta').textContent += ` | Protocol: ${run.options?.protocol || 'full-file-v1'}`;
  if (run.options?.mode === 'experiment2') $('run-meta').textContent = `${statusText(run.status)} | ${run.dataset.name} | ${run.completed_tasks}/${run.total_tasks} | Qwen real-time replay | ${run.options.protocol}`;
  run.models.forEach(model => {
    const row = node('tr'), first = node('td', model.config.label);
    first.append(node('small', `${statusText(model.status)}${model.load_s == null ? '' : ` · load ${seconds(model.load_s)}`}`));
    if (model.error) first.append(node('small', model.error, 'error-text'));
    if (run.options?.mode?.startsWith('experiment')) {
      for (const [key,label] of [['wall_s','File completion'],['first_text_from_vad_s','First text from VAD onset'],['finalization_from_eof_s','Finalization after EOF'],['max_queue_s','Per-file peak queue']]) {
        const s=model.summary;
        if (s[`${key}_p95`] != null) first.append(node('small', `${label}: median ${seconds(s[`${key}_median`])}, p95 ${seconds(s[`${key}_p95`])}, max ${seconds(s[`${key}_max`])}`));
      }
    }
    row.append(first, node('td', `${model.summary.completed}/${run.dataset.samples.length}`), node('td', model.summary.failed),
      node('td', pct(model.summary.wer)), node('td', pct(model.common_summary.wer)),
      node('td', pct(model.summary.cer)), node('td', pct(model.common_summary.cer)),
      node('td', model.summary.inference_s == null ? '—' : seconds(model.summary.inference_s)),
      node('td', model.summary.rtf == null ? '—' : `${model.summary.rtf.toFixed(3)}×`),
      ...['chunk_p95_s','lag_p95_s','first_text_p95_s'].map(key => node('td', model.summary[key] == null ? '—' : seconds(model.summary[key]))));
    $('summary').append(row);
  });
  $('comparison-note').textContent = `Common WER currently covers ${run.common_sample_count} samples that succeeded across all models. ${active ? 'Results are updating; wait for completion before comparing.' : 'Per-model WER includes successful samples only; always check failures and coverage.'}`;
  $('csv').href = `/api/runs/${run.id}/csv`; $('json').href = `/api/runs/${run.id}/json`;
  $('summary-csv').href = `/api/runs/${run.id}/summary.csv`;
  const choice = $('detail-model').value;
  const modelOptions = run.models.map((m,i) => option(String(i), m.config.label));
  $('detail-model').replaceChildren(...modelOptions);
  if (Number(choice) < run.models.length) $('detail-model').value = choice || '0';
  renderSamples();
}
function renderSamples() {
  const model = currentRun?.models[Number($('detail-model').value)]; if (!model) return;
  const open = new Set([...$('sample-results').querySelectorAll('details[open]')].map(e => e.dataset.id));
  $('sample-results').replaceChildren();
  if (!model.samples.length) $('sample-results').append(node('p', 'Sample results will appear here.', 'hint'));
  model.samples.forEach(row => {
    const detail = node('details', null, 'sample-row'); detail.dataset.id = row.id; detail.open = open.has(row.id);
    const title = node('summary'); title.append(node('span', row.id), node('span', row.status === 'ok' ? `WER ${pct(row.wer)} · ${seconds(row.elapsed_s)}` : 'Error'));
    detail.append(title);
    if (row.status !== 'ok') detail.append(node('p', row.error, 'error-text'));
    else {
      const pair = node('div', null, 'text-pair');
      for (const [label, text] of [['Reference transcript',row.reference],['Model prediction',row.hypothesis || '(No speech recognized)']]) {
        const side = node('div'); side.append(node('h4', label), node('p', text)); pair.append(side);
      }
      detail.append(pair, node('p', `Substitutions ${row.substitutions} · Deletions ${row.deletions} · Insertions ${row.insertions} · ${row.reference_words} reference words`, 'hint'));
      detail.append(node('p', `CER ${pct(row.cer)}${row.replay_metrics ? ` · ${row.replay_metrics.chunk_count} chunks · ${row.replay_metrics.deadline_misses} chunks took longer to process than their audio duration` : ''}`, 'hint'));
      if (row.chunks) row.chunks.forEach(c => detail.append(node('p', `${c.start_s.toFixed(1)}–${c.end_s.toFixed(1)}s · processing ${c.elapsed_s.toFixed(2)}s · lag ${c.lag_s.toFixed(2)}s: ${c.text}`, 'hint')));
    }
    $('sample-results').append(detail);
  });
}
$('detail-model').onchange = renderSamples;
$('history').onchange = () => showRun($('history').value).catch(e => notice(e.message,true));
$('cancel').onclick = async () => { try { await post('/api/cancel', {run_id:currentRun.id}); await showRun(currentRun.id); } catch(e) { notice(e.message,true); } };
$('resume').onclick = async () => {
  const id = currentRun?.id;
  if (!id || currentRun.status !== 'interrupted' || resumePending) return;
  resumePending = true;
  updateRunButton();
  notice('Checking dataset and backing up saved results before resuming...');
  try {
    await post('/api/resume', {run_id:id});
    await refresh(); $('history').value = id; await showRun(id);
    notice('Resumed. Saved results are preserved; only missing samples will run.');
  } catch(e) { notice(e.message,true); }
  finally { resumePending = false; updateRunButton(); if (currentRun) renderRun(); }
};
(async () => {
  try { await refresh(); if (state.models.length) { selectedModels.add(state.models[0].label); renderModels(); }
    const last = state.runs.find(r => activeStatus(r.status)) || state.runs[0];
    if (last) { $('history').value=last.id; await showRun(last.id); }
  } catch(e) { notice(`Cannot connect to the tool: ${e.message}`,true); }
})();
