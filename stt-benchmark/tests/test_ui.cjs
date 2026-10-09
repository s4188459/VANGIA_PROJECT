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
