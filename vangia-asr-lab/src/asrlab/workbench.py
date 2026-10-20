"""Desktop experiment, dataset, trace, review and decision workflows."""
import json
import queue
import threading
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import ttk,filedialog,messagebox,simpledialog
from .common import ROOT,registry,read_json
from .storage import read_jsonl,audit


class Workbench:
    def __init__(self,root,run_dir=None):
        self.ready=False
        super().__init__(root,run_dir)
        root.geometry('1380x900');root.minsize(1080,760)
        self.messages=queue.Queue();self.running=False;self.references=[];self.predictions=[];self.selected_sample=None
        self.candidate_ids={m['canonical_model_id'] for m in registry()['models']}
        self.frames={}
        for key,title in [('datasets','Datasets & Splits'),('runner','Experiment Runner'),('trace','Real-time Trace'),('review','Accuracy & Review'),('resources','Latency & Reliability'),('decision','Decision & Report')]:
            frame=ttk.Frame(self.tabs,padding=10);self.tabs.add(frame,text=title);self.frames[key]=frame
        self.build_datasets();self.build_runner();self.build_trace();self.build_review();self.build_resources();self.build_decision()
        self.ready=True;self.load_evidence();root.protocol('WM_DELETE_WINDOW',self.close);root.after(300,self.poll)

    def guard(self,fn):
        try:return fn()
        except Exception as exc:messagebox.showerror('Action could not complete',str(exc),parent=self.root)

    def textview(self,parent,height=15):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True)
        text=tk.Text(frame,wrap='word',font=('Consolas',10),height=height)
        scroll=ttk.Scrollbar(frame,command=text.yview);text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True);return text

    def tree(self,parent,columns,height=10):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True)
        tree=ttk.Treeview(frame,columns=[c[0] for c in columns],show='headings',height=height)
        for key,label,width in columns:tree.heading(key,text=label);tree.column(key,width=width,minwidth=60)
        sy=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);sx=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        sy.pack(side='right',fill='y');sx.pack(side='bottom',fill='x');tree.pack(fill='both',expand=True);return tree

    def buttons(self,parent,items):
        bar=ttk.Frame(parent);bar.pack(fill='x',pady=8)
        for text,fn in items:ttk.Button(bar,text=text,command=lambda f=fn:self.guard(f)).pack(side='left',padx=3)
        return bar

    def build_datasets(self):
        f=self.frames['datasets'];self.dataset_path=tk.StringVar(value=str(ROOT/'runs/datasets'))
        ttk.Label(f,text='Local registry folder').pack(anchor='w');ttk.Entry(f,textvariable=self.dataset_path).pack(fill='x')
        self.buttons(f,[('Import sample',self.add_sample),('Lock split',self.lock_split),('Refresh',self.load_datasets)])
        ttk.Label(f,text='Consented English PCM WAV. Speaker/session/PCM hashes prevent split leakage. Corrections create new revisions.').pack(anchor='w',pady=10)
        self.dataset_tree=self.tree(f,[('id','Sample',100),('split','Split',130),('speaker','Speaker',110),('session','Session',110),('quality','Reference quality',130),('duration','Seconds',90),('hash','PCM SHA256',360)])

    def build_runner(self):
        f=self.frames['runner']
        self.buttons(f,[('Load config',self.load_config),('Check prerequisites',self.check_run),('Start',self.start_run),('Resume',lambda:self.start_run(True)),('Cancel',self.cancel_run),('Experiment plan',self.show_plan)])
        ttk.Label(f,text='Explicit JSON configuration • no hidden download • isolated model worker • failures saved').pack(anchor='w',pady=8)
        self.config_text=self.textview(f,15)
        self.config_text.insert('1.0',json.dumps({'mode':'synthetic_fixture','out':str(ROOT/'runs'/('fixture-'+uuid.uuid4().hex[:8])),'random_seed':42},indent=2))
        self.runner_status=tk.StringVar(value='Ready for a clearly labeled simulated plumbing fixture. No model inference is implied.')
        ttk.Label(f,textvariable=self.runner_status,wraplength=1100).pack(anchor='w',pady=12)

    def build_trace(self):
        f=self.frames['trace'];ttk.Label(f,text='UI redraw requests do not measure physical screen presentation. Word lag stays null without reviewed alignment.').pack(anchor='w')
        self.waveform=tk.Canvas(f,height=90,bg='#102537',highlightthickness=0);self.waveform.pack(fill='x',pady=10)
        self.caption=tk.StringVar(value='No current caption. Select a run or start a fixture.')
        ttk.Label(f,textvariable=self.caption,font=('Segoe UI',20),wraplength=1100).pack(fill='x',pady=10)
        self.trace_tree=self.tree(f,[('time','Monotonic ns',160),('type','Event',220),('chunk','Chunk',180),('quality','Measurement basis',130),('text','Caption / payload',520)])

    def build_review(self):
        f=self.frames['review'];self.buttons(f,[('Play original audio',self.play_audio),('Add annotation',self.add_annotation),('Correct reference',self.correct_reference)])
        self.review_tree=self.tree(f,[('id','Sample',100),('model','Configuration',230),('status','Status',100),('wer','Normalized WER',120),('errors','S / D / I',100),('text','Hypothesis',440)],height=8)
        self.review_tree.bind('<<TreeviewSelect>>',lambda e:self.guard(self.select_review))
        self.review_text=self.textview(f,8)

    def build_resources(self):
        f=self.frames['resources'];ttk.Label(f,text='Valid-match percentiles need coverage. Whole-file RTF is throughput, not caption lag.').pack(anchor='w',pady=8)
        self.resource_text=self.textview(f)

    def build_decision(self):
        f=self.frames['decision'];self.buttons(f,[('Reviewer sign-off',self.signoff),('Paired comparison',self.compare),('Export reports',self.export),('Redacted summary',self.redacted_export),('Archived configs',self.archived_configs)])
        self.decision_text=self.textview(f)

    def set_text(self,widget,text):widget.delete('1.0','end');widget.insert('1.0',text)

    def refresh(self):
        super().refresh()
        if self.ready:self.load_evidence()

    def load_evidence(self):
        if not self.run_dir:return
        path=self.run_dir
        try:
            manifest=read_json(path/'manifest.json');metrics=read_json(path/'metrics.json') if (path/'metrics.json').exists() else {}
            self.references=read_jsonl(path/'reference.jsonl');self.predictions=read_jsonl(path/'predictions.jsonl')
            for tree in (self.review_tree,self.trace_tree):tree.delete(*tree.get_children())
            for i,p in enumerate(self.predictions):
                self.review_tree.insert('','end',iid=str(i),values=(p['sample_id'],p.get('config_id',manifest.get('model_id') or 'fixture'),p.get('status','historical'),
                    p.get('wer','see score'),f"{p.get('substitutions','-')} / {p.get('deletions','-')} / {p.get('insertions','-')}",p.get('text',p.get('hypothesis',''))))
            events=[]
            for file in [path/'events.jsonl']+sorted(path.glob('events.jsonl.part-*')):
                try:events+=read_jsonl(file)
                except (OSError,ValueError):pass
            for e in events[-300:]:self.trace_tree.insert('','end',values=(e['monotonic_ns'],e['event_type'],e.get('chunk_id'),e.get('trace_quality','not presentation'),e.get('caption_text') or json.dumps(e['payload'])[:400]))
            captions=[e.get('caption_text') for e in events if e.get('caption_text')]
            if captions:self.caption.set(('SIMULATED FIXTURE: ' if manifest['input_mode']=='synthetic_fixture' else '')+captions[-1])
            visible={k:v for k,v in metrics.items() if k not in ('configurations','candidates','raw','normalized','conditional_success')}
            self.set_text(self.resource_text,json.dumps(visible,indent=2,ensure_ascii=False))
            from .review import decision
            self.set_text(self.decision_text,json.dumps(decision(manifest,metrics),indent=2)+'\n\n'+((path/'report.md').read_text(encoding='utf-8') if (path/'report.md').exists() else 'Report pending.'))
        except (OSError,ValueError):pass

    def background(self,fn):
        if self.running:raise ValueError('A task is already running; cancel or wait')
        self.running=True;self.runner_status.set('Running locally. Cancellation remains available.')
        def work():
            try:self.messages.put(('done',fn()))
            except Exception as exc:self.messages.put(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='caption':
                    text,ack=value
                    self.caption.set(text)
                    self.root.update_idletasks()
                    # Unmapped/hidden caption view has no usable presentation proxy.
                    if self.tabs.select()==str(self.frames['trace']) and self.root.state()=='normal':ack()
                    continue
                self.running=False;self.runner_status.set(str(value)[:1000]);self.refresh()
                if kind=='error':messagebox.showerror('Task failed',value,parent=self.root)
        except queue.Empty:pass
        if self.running:self.refresh()
        self.root.after(500,self.poll)

    def load_config(self):
        path=filedialog.askopenfilename(filetypes=[('JSON','*.json')])
        if path:self.set_text(self.config_text,json.dumps(read_json(path),indent=2))

    def check_run(self):
        cfg=json.loads(self.config_text.get('1.0','end'))
        if cfg['mode']=='synthetic_fixture':result={'status':'READY','notice':'Synthetic fixture only; no inference evidence'}
        else:
            from .adapters import preflight
            result=preflight(cfg)
        self.runner_status.set(json.dumps(result,ensure_ascii=False));return result

    def start_run(self,resume=False):
        cfg=json.loads(self.config_text.get('1.0','end'));cfg['resume']=resume
        from .runner import run
        self.run_dir=Path(cfg['out']);self.tabs.select(self.frames['trace'])
        self.background(lambda:run(cfg,presenter=lambda text,ack:self.messages.put(('caption',(text,ack)))))

    def cancel_run(self):
        if self.run_dir and self.run_dir.is_dir():(self.run_dir/'CANCEL').touch();self.runner_status.set('Cancellation requested; waiting for worker shutdown.')

    def close(self):
        if self.running:self.cancel_run();self.root.after(300,self.close)
        else:self.root.destroy()

    def export(self):
        if not self.run_dir:raise ValueError('Open a run first')
        from .reports import report
        from .storage import seal
        if not audit(self.run_dir)['ok']:raise ValueError('Integrity failed; export stopped')
        report(self.run_dir);seal(self.run_dir);messagebox.showinfo('Reports saved',str(self.run_dir))

    def json_dialog(self,title,value,readonly=False):
        dialog=tk.Toplevel(self.root);dialog.title(title);dialog.geometry('900x650');result=[]
        text=self.textview(dialog);text.insert('1.0',json.dumps(value,indent=2,ensure_ascii=False))
        if readonly:text.configure(state='disabled')
        else:
            def save():
                try:result.append(json.loads(text.get('1.0','end')));dialog.destroy()
                except ValueError as exc:messagebox.showerror('Invalid JSON',str(exc),parent=dialog)
            ttk.Button(dialog,text='Save',command=save).pack(pady=10)
        dialog.transient(self.root);dialog.grab_set();self.root.wait_window(dialog)
        return result[0] if result else None

    def add_sample(self):
        audio=filedialog.askopenfilename(title='Consented mono PCM16 16 kHz WAV',filetypes=[('Audio WAV','*.wav')])
        if not audio:return
        item=self.json_dialog('Sample metadata — consent required',dict(sample_id=Path(audio).stem,audio=audio,text='',language='en',speaker_id='',session_id='',domain='classroom',consent_record_id='',provenance_type='real_measurement',reference_quality='unverified',split='development'))
        if item:
            from .datasets import DatasetRegistry
            DatasetRegistry(self.dataset_path.get()).add(item);self.load_datasets()

    def load_datasets(self):
        from .datasets import DatasetRegistry
        self.dataset_tree.delete(*self.dataset_tree.get_children())
        for r in DatasetRegistry(self.dataset_path.get()).samples():self.dataset_tree.insert('','end',values=(r['sample_id'],r['split'],r['speaker_id'],r['session_id'],r['reference_quality'],r['duration_s'],r['pcm_sha256']))

    def lock_split(self):
        split=simpledialog.askstring('Lock immutable split','development or holdout:',parent=self.root)
        if split:
            from .datasets import DatasetRegistry
            result=DatasetRegistry(self.dataset_path.get()).lock(split);messagebox.showinfo('Split locked',result['sha256'])

    def select_review(self):
        selected=self.review_tree.selection()
        if not selected:return
        pred=self.predictions[int(selected[0])];ref=next((r for r in self.references if r['sample_id']==pred['sample_id']),{})
        self.selected_sample=(ref,pred)
        from .metrics import score
        text=pred.get('text',pred.get('hypothesis','')) or ''
        self.set_text(self.review_text,json.dumps({'reference':ref,'prediction':pred,'raw':score(ref.get('text',''),text,False),'normalized':score(ref.get('text',''),text)},indent=2,ensure_ascii=False))
        audio=ref.get('audio')
        if audio and Path(audio).exists():
            from .audio import read_pcm
            from array import array
            pcm,_=read_pcm(audio);samples=array('h',pcm);self.waveform.delete('all');width=max(1,self.waveform.winfo_width());step=max(1,len(samples)//width)
            for x,start in enumerate(range(0,len(samples),step)):
                peak=max((abs(v) for v in samples[start:start+step]),default=0)/32768*40
                self.waveform.create_line(x,45-peak,x,45+peak,fill='#72dccc')

    def play_audio(self):
        if not self.selected_sample:raise ValueError('Select a sample first')
        audio=self.selected_sample[0].get('audio')
        if not audio or not Path(audio).is_file():raise ValueError('BLOCKED: original waveform missing')
        import winsound
        winsound.PlaySound(audio,winsound.SND_FILENAME|winsound.SND_ASYNC)

    def add_annotation(self):
        if not self.selected_sample:raise ValueError('Select a sample first')
        ref,pred=self.selected_sample;manifest=read_json(self.run_dir/'manifest.json')
        value=self.json_dialog('Reviewer annotation',dict(annotation_id=uuid.uuid4().hex,run_id=manifest['run_id'],sample_id=pred['sample_id'],reference_revision=ref.get('reference_revision',''),reviewer_id='',category='other',severity='uncertain',review_status='proposed',notes=''))
        if value:
            from .review import annotate
            annotate(self.run_dir,value)

    def correct_reference(self):
        if not self.selected_sample:raise ValueError('Select a sample first')
        ref,_=self.selected_sample;text=simpledialog.askstring('Reference correction','Corrected text:',initialvalue=ref.get('text',''),parent=self.root)
        if text is None:return
        reviewer=simpledialog.askstring('Reviewer','Reviewer ID:',parent=self.root)
        from .datasets import DatasetRegistry
        DatasetRegistry(self.dataset_path.get()).correct_reference(ref['sample_id'],text,reviewer)

    def signoff(self):
        if not self.run_dir:raise ValueError('Open run first')
        reviewer=simpledialog.askstring('Review sign-off','Reviewer ID:',parent=self.root)
        if not reviewer:return
        notes=simpledialog.askstring('Review rationale','Evidence and use-case scope:',parent=self.root)
        if not notes:return
        from .review import sign_off
        result=sign_off(self.run_dir,reviewer,notes);messagebox.showinfo('Sign-off saved',json.dumps(result['decision'],indent=2))

    def compare(self):
        a=filedialog.askopenfilename(title='Candidate A paired score JSONL',filetypes=[('JSONL','*.jsonl')])
        if not a:return
        b=filedialog.askopenfilename(title='Candidate B paired score JSONL',filetypes=[('JSONL','*.jsonl')])
        if not b:return
        from .experiments import paired_bootstrap
        self.set_text(self.decision_text,json.dumps(paired_bootstrap(read_jsonl(a),read_jsonl(b)),indent=2))

    def show_plan(self):
        from .experiments import plan
        self.json_dialog('Progressive plan — not run evidence',plan(ROOT/'config/experiment_matrix.json'),readonly=True)

    def archived_configs(self):
        if not self.run_dir:raise ValueError('Open historical run first')
        self.json_dialog('Archived configurations',read_json(self.run_dir/'metrics.json').get('configurations',[]),readonly=True)

    def redacted_export(self):
        if not self.run_dir:raise ValueError('Open run first')
        from .privacy import export_redacted
        out=filedialog.asksaveasfilename(title='Redacted aggregate summary',defaultextension='.json')
        if out:export_redacted(self.run_dir,out)
