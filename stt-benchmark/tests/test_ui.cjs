// Unit-test actual UI request coordination with a minimal DOM/network harness.
// This is not a browser layout test.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function harness() {
  const elements = new Map();
  const element = () => ({value:'',hidden:false,disabled:false,children:[],dataset:{},
    append(...items){this.children.push(...items)},replaceChildren(...items){this.children=items},
    removeAttribute(){},querySelectorAll(){return []}});
  const pending = new Map();
  const context = vm.createContext({document:{getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id)},createElement:element},
    URLSearchParams,console,setTimeout:()=>1,clearTimeout:()=>{},
    fetch(url){ if(url==='/api/state') return Promise.resolve({ok:true,json:async()=>({datasets:[],models:[],runs:[]})});
      return new Promise(resolve=>pending.set(url, value=>resolve({ok:true,json:async()=>value}))); }});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8'),context);
  return {context,elements,pending,run:code=>vm.runInContext(code,context)};
}
const result = (id,status='completed') => ({id,status,message:id,dataset:{name:id,language:'en',samples:[]},models:[],total_tasks:0,completed_tasks:0,common_sample_count:0});
const tick = () => new Promise(resolve=>setImmediate(resolve));

test('retired automatic model experiments cannot be submitted from the web UI', async()=>{
  for (const mode of ['experiment2','experiment3']) {
    const h=harness(); await tick();
    h.run(`state.datasets=[{id:'english',language:'en'}];
      $('dataset').value='english'; $('reviewed').checked=true;
      $('model-scope').value='manual'; $('benchmark-mode').value='${mode}';
      $('sample-limit').value='3';
      globalThis.sent=null;
      fetch=async(path,options)=>{globalThis.sent={path,body:JSON.parse(options.body)}; throw new Error('request captured');};`);
    await h.elements.get('run').onclick();
    assert.equal(h.run('sent'),null);
    assert.match(h.elements.get('notice').textContent,/retired/);
  }
});
test('Vietnamese sets use only members and CPU defaults, never unrelated saved models', async()=>{
  const h=harness(); await tick();
  h.run(`state.datasets=[{id:'vi',language:'vi'}];
    state.catalog=[{label:'small',model:'small',backend:'faster-whisper',languages:['en','vi'],sets:['vi-live']},
      {label:'large',model:'large-v3',backend:'faster-whisper',languages:['en','vi'],sets:['vi-video']}];
    state.models=[{label:'custom CUDA',model:'small',backend:'faster-whisper',device:'cuda',compute_type:'float16'},
      {label:'unrelated',model:'tiny',backend:'faster-whisper',languages:['en','vi']}];
    state.backends={'faster-whisper':{installed:true}};`);
  h.elements.get('dataset').value='vi'; h.elements.get('model-scope').value='vi-live';
  h.elements.get('model-scope').onchange();
  assert.equal(h.run('batchModels().models.length'),1);
  assert.equal(h.run('batchModels().models[0].model'),'small');
  assert.equal(h.run('batchModels().models[0].device'),'cpu');
  assert.equal(h.run('batchModels().models[0].compute_type'),'int8');
  assert.equal(h.run('batchModels().models[0].allow_download'),false);
  assert.equal(h.elements.get('benchmark-mode').value,'live_replay');
  assert.equal(h.elements.get('chunk-seconds').value,'1');
  h.elements.get('model-scope').value='vi-video'; h.elements.get('model-scope').onchange();
  assert.equal(h.run('batchModels().models[0].model'),'large-v3');
  assert.equal(h.elements.get('benchmark-mode').value,'final');
});

test('Vietnamese set refuses English datasets and shows missing backends',async()=>{
  const h=harness();await tick();
  h.run(`state.datasets=[{id:'ds',language:'en'}];
    state.catalog=[{label:'MLT',model:'FunAudioLLM/Fun-ASR-MLT-Nano-2512',backend:'fun-asr-mlt',languages:['en','vi'],sets:['vi-live']}];
    state.backends={'fun-asr-mlt':{installed:false}};`);
  h.elements.get('dataset').value='ds';h.elements.get('model-scope').value='vi-live';
  assert.equal(h.run('batchModels().models.length'),0);
  assert.match(h.run('batchModels().skipped.join()'),/Vietnamese/);
  h.run("state.datasets[0].language='vi'");
  assert.equal(h.run('batchModels().models.length'),0);
  assert.match(h.run('batchModels().skipped.join()'),/not installed/);
});
test('resume is shown only for interrupted runs and follows background activity',async()=>{
  const h=harness();await tick();
  for (const status of ['completed','running','cancelled','interrupted']) {
    const show=h.run("showRun('old')");
    h.pending.get('/api/runs/old')(result('old',status));await show;
    assert.equal(h.elements.get('resume').hidden,status!=='interrupted');
  }
  h.run("state.runs.push({id:'background',status:'running'}); updateRunButton()");
  assert.equal(h.elements.get('resume').disabled,true);
  h.run("state.runs.find(r=>r.id==='background').status='completed'; updateRunButton()");
  assert.equal(h.elements.get('resume').disabled,false);
});

test('resume button posts existing run and refreshes its progress',async()=>{
  const h=harness();await tick();
  const show=h.run("showRun('old')");
  h.pending.get('/api/runs/old')(result('old','interrupted'));await show;
  const click=h.elements.get('resume').onclick();
  assert.equal(h.elements.get('resume').disabled,true);
  assert.ok(h.pending.has('/api/resume'));
  h.pending.get('/api/resume')(result('old','running'));await tick();
  h.pending.get('/api/runs/old')(result('old','running'));await click;
  assert.equal(h.run('currentRun.id'),'old');
  assert.equal(h.elements.get('resume').hidden,true);
  assert.equal(h.elements.get('cancel').hidden,false);
});
test('late response from old report cannot replace newly selected report',async()=>{
  const h=harness();await tick();
  const old=h.run("showRun('old')");const next=h.run("showRun('new')");
  h.pending.get('/api/runs/new')(result('new'));await next;
  h.pending.get('/api/runs/old')(result('old'));await old;
  assert.equal(h.run('currentRun.id'),'new');
});
test('viewing old report keeps run disabled while another benchmark is active',async()=>{
  const h=harness();await tick();
  h.run("state.runs=[{id:'background',status:'running'}]");
  const show=h.run("showRun('old')");h.pending.get('/api/runs/old')(result('old'));await show;
  assert.equal(h.elements.get('run').disabled,true);
});
test('clearing report invalidates in-flight response',async()=>{
  const h=harness();await tick();
  const show=h.run("showRun('old')");await h.run("showRun('')");
  h.pending.get('/api/runs/old')(result('old'));await show;
  assert.equal(h.run('currentRun'),null);
  assert.equal(h.elements.get('report').hidden,true);
});

test('catalog preset selects backend defaults without enabling downloads',async()=>{
  const h=harness();await tick();
  h.run("state.catalog=[{backend:'vosk',model:'example',label:'Vosk',languages:['vi']}];state.backends={vosk:{installed:false,python_executable:'python-path'}}");
  h.elements.get('catalog').value='vosk|example';
  h.elements.get('use-preset').onclick();
  assert.equal(h.elements.get('backend').value,'vosk');
  assert.equal(h.elements.get('beam').value,'1');
  assert.equal(h.elements.get('vad').checked,false);
  assert.equal(h.elements.get('compute').value,'float32');
  assert.equal(h.elements.get('download').checked,false);
  assert.equal(h.elements.get('backend-python').value,'python-path');
  assert.equal(h.elements.get('model-languages').value,'vi');
});

test('all catalog filters language, deduplicates local models and respects cloud and download choices',async()=>{
  const h=harness();await tick();
  h.run(`state.datasets=[{id:'en',language:'en'}];
    state.models=[{label:'local',backend:'faster-whisper',model:'D:/models/faster-whisper-small-en'}];
    state.backends={'faster-whisper':{installed:true},nemo:{installed:false},elevenlabs:{installed:true}};
    state.catalog=[{label:'small.en',model:'small.en',backend:'faster-whisper',languages:['en']},
      {label:'tiny',model:'tiny',backend:'faster-whisper',languages:['en','vi']},
      {label:'vi',model:'vi',backend:'faster-whisper',languages:['vi']},
      {label:'nemo',model:'nemo',backend:'nemo',languages:['en']},
      {label:'cloud',model:'scribe_v2',backend:'elevenlabs',languages:['en']}];`);
  h.elements.get('dataset').value='en';h.elements.get('model-scope').value='catalog';
  assert.equal(h.run('batchModels().models.length'),2);
  assert.equal(h.run('batchModels().skipped.length'),2);
  assert.equal(h.run('batchModels().models[1].allow_download'),false);
  h.elements.get('cloud-consent').checked=true;
  h.elements.get('batch-download').checked=true;
  assert.equal(h.run('batchModels().models.length'),3);
  assert.equal(h.run('batchModels().models[1].allow_download'),true);
});
