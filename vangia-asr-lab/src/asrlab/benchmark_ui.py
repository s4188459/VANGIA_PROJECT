"""Guided ZIP input, model forms, serial execution and analysis export for Tk."""
import json
import os
import queue
import threading
import time
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import ttk,filedialog,messagebox,simpledialog

from .common import ROOT,read_json,write_json,registry,sha256
from .benchmark import local_presets,create_benchmark,run_benchmark,cancel_benchmark,load_benchmark
from .zip_dataset import preview_zip,import_zip
from .analysis_export import collect_results,export_analysis
from .progress import snapshot, TERMINAL


class BenchmarkWizard:
    def __init__(self,app,source=None):
        self.app=app;self.window=tk.Toplevel(app.root);self.window.title('Vangia — New benchmark / Analysis')
        self.window.geometry('1120x780');self.window.minsize(960,680)
        self.busy=False;self.queue=queue.Queue();self.dataset=None;self.mapping=None;self.silence_ids=set();self.source=None
        self.presets=local_presets();self.preview=None;self.results=None;self.input_identity=None
        self.monitor_busy=False;self.monitor_next=0;self.monitor_source=None;self.monitor_data=None
        self.monitor_started=time.monotonic();self.sealed_results={};self.running_campaign=False
        self.results_busy=False;self.current_progress=None
        token=uuid.uuid4().hex[:8]
        self.archive_path=tk.StringVar();self.metadata_path=tk.StringVar();self.consent=tk.StringVar()
        self.dataset_path=tk.StringVar(value=str(ROOT/'runs'/('dataset-'+token)))
        self.benchmark_path=tk.StringVar(value=str(ROOT/'runs'/('benchmark-'+token)))
        self.status=tk.StringVar(value='1. Select ZIP → inspect pairs → enter consent → import. Original ZIP is unchanged.')
        ttk.Label(self.window,text='New benchmark',font=('Segoe UI',19,'bold')).pack(anchor='w',padx=15,pady=10)
        panel=ttk.LabelFrame(self.window,text='Live process tracking',padding=8);panel.pack(fill='x',padx=12,pady=4)
        self.live_title=tk.StringVar(value='Ready — import a dataset or open a saved benchmark.')
        self.live_detail=tk.StringVar(value='Progress updates every second. No benchmark is running in this window.')
        ttk.Label(panel,textvariable=self.live_title,font=('Segoe UI',11,'bold'),wraplength=1150).pack(anchor='w')
        ttk.Label(panel,textvariable=self.live_detail,wraplength=1150).pack(anchor='w')
        self.live_progress=ttk.Progressbar(panel,mode='determinate');self.live_progress.pack(fill='x',pady=3)
        self.stop_button=ttk.Button(panel,text='Cancel benchmark',command=lambda:self.guarded(self.cancel),state='disabled');self.stop_button.pack(anchor='e')
        self.tabs=ttk.Notebook(self.window);self.tabs.pack(fill='both',expand=True,padx=12)
        self.input_frame=ttk.Frame(self.tabs,padding=10);self.models_frame=ttk.Frame(self.tabs,padding=10);self.results_frame=ttk.Frame(self.tabs,padding=10)
        for frame,title in ((self.input_frame,'1 · Input ZIP'),(self.models_frame,'2 · Models & Run'),(self.results_frame,'3 · Results & Export')):self.tabs.add(frame,text=title)
        self.build_input();self.build_models();self.build_results()
        ttk.Label(self.window,textvariable=self.status,wraplength=1200).pack(fill='x',padx=15,pady=10)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.timer=self.window.after(200,self.poll)
        if source:self.open_source(source)

    def guarded(self,fn):
        try:return fn()
        except Exception as exc:
            self.status.set(str(exc));messagebox.showerror('Benchmark action',str(exc),parent=self.window)

    def buttons(self,parent,items):
        bar=ttk.Frame(parent);bar.pack(fill='x',pady=7)
        for label,fn in items:ttk.Button(bar,text=label,command=lambda f=fn:self.guarded(f)).pack(side='left',padx=3)
        return bar

    def entry(self,parent,label,variable,browse=None):
        bar=ttk.Frame(parent);bar.pack(fill='x',pady=3)
        ttk.Label(bar,text=label,width=23).pack(side='left');ttk.Entry(bar,textvariable=variable).pack(side='left',fill='x',expand=True)
        if browse:ttk.Button(bar,text='Browse…',command=browse).pack(side='right',padx=3)

    def tree(self,parent,columns,height=8):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True)
        tree=ttk.Treeview(frame,columns=[k for k,_ in columns],show='headings',height=height,selectmode='extended')
        for key,label in columns:tree.heading(key,text=label);tree.column(key,width=140,minwidth=75)
        y=ttk.Scrollbar(frame,command=tree.yview);x=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=y.set,xscrollcommand=x.set);y.pack(side='right',fill='y');x.pack(side='bottom',fill='x');tree.pack(fill='both',expand=True)
        return tree

    def advanced_section(self,parent,label='Advanced settings'):
        container=ttk.Frame(parent);container.pack(fill='x',pady=3)
        body=ttk.Frame(container,padding=5)
        def toggle():
            if body.winfo_manager():body.pack_forget()
            else:body.pack(fill='x')
        ttk.Button(container,text=label,command=toggle).pack(anchor='w')
        return body

    def choose_group(self,role):
        self.mode.set('paced_replay' if role=='live' else 'batch_file')
        ids=[m['canonical_model_id'] for m in registry()['models'] if role in m['roles']]
        self.select_models(ids)
        self.status.set(f'{len(ids)} {role} candidates selected. Check setup, then start. You can adjust the selection.')

    def build_input(self):
        self.entry(self.input_frame,'ZIP audio + TXT',self.archive_path,lambda:self.choose_file(self.archive_path,[('ZIP','*.zip')]))
        self.entry(self.input_frame,'Consent record ID',self.consent)
        self.buttons(self.input_frame,[('1. Check ZIP',self.inspect_archive),('2. Use this dataset',lambda:self.background(self.import_data))])
        extra=self.advanced_section(self.input_frame,'Pairing and storage options')
        self.entry(extra,'Metadata CSV (optional)',self.metadata_path,lambda:self.choose_file(self.metadata_path,[('CSV','*.csv')]))
        self.entry(extra,'Dataset folder',self.dataset_path)
        self.buttons(extra,[('Edit selected pairing',self.edit_pairing),('Confirm selected silence',self.confirm_silence)])
        ttk.Label(self.input_frame,text='Choose a ZIP with matching audio and TXT files. Check the pairs, then continue.').pack(anchor='w',pady=5)
        self.preview_tree=self.tree(self.input_frame,[('id','Sample'),('audio','Audio path'),('reference','Reference path'),('duration','Seconds'),
            ('language','Language'),('domain','Domain'),('speaker','Speaker'),('session','Session'),('split','Split'),('errors','Errors / warnings')])

        self.preview_tree.configure(displaycolumns=('id','audio','reference','errors'))

    def choose_file(self,var,types):
        path=filedialog.askopenfilename(parent=self.window,filetypes=types)
        if path:var.set(path)

    def inspect_archive(self):
        if self.busy:raise ValueError('Wait for the current operation')
        self.preview=preview_zip(self.archive_path.get(),self.metadata_path.get() or None)
        identity=(self.preview['archive_sha256'],sha256(self.metadata_path.get()) if self.metadata_path.get() else None)
        if self.input_identity!=identity:self.silence_ids.clear();self.dataset=None
        self.input_identity=identity
        self.mapping=[{k:r[k] for k in ('sample_id','audio_path','reference_path','domain','speaker_id','session_id','split','language','reference_quality')} for r in self.preview['samples']]
        self.show_preview(self.preview);self.status.set(f"{len(self.preview['samples'])} planned audio samples. Check pairing, then import to decode/validate duration.")

    def show_preview(self,data):
        self.preview_tree.delete(*self.preview_tree.get_children())
        for i,r in enumerate(data['samples']):
            self.preview_tree.insert('','end',iid=str(i),values=(r['sample_id'],r['audio_path'],r.get('reference_path') or 'MISSING',
                f"{r['duration_s']:.3f}" if r.get('duration_s') is not None else 'pending decode',r['language'],r['domain'],r['speaker_id'],r['session_id'],r['split'],
                '; '.join(r['input_errors']+r.get('warnings',[]))))

    def edit_pairing(self):
        selected=self.preview_tree.selection()
        if len(selected)!=1:raise ValueError('Select one sample to edit its mapping')
        index=int(selected[0]);value=dict(self.mapping[index])
        dialog=tk.Toplevel(self.window);dialog.title('Sample mapping');variables={}
        for key in ('sample_id','audio_path','reference_path','domain','speaker_id','session_id','split','language'):
            variables[key]=tk.StringVar(value=value.get(key) or '');self.entry(dialog,key,variables[key])
        def save():
            self.mapping[index]={k:v.get() for k,v in variables.items()}
            self.preview=preview_zip(self.archive_path.get(),self.mapping);self.show_preview(self.preview);self.dataset=None;dialog.destroy()
        ttk.Button(dialog,text='Apply mapping',command=lambda:self.guarded(save)).pack(pady=8)

    def confirm_silence(self):
        selected=self.preview_tree.selection()
        if not selected:raise ValueError('Select explicitly verified nonspeech samples')
        if messagebox.askyesno('Confirm nonspeech','Confirm these selected recordings genuinely have an empty reference (verified silence/nonspeech)?',parent=self.window):
            self.silence_ids.update(self.preview['samples'][int(i)]['sample_id'] for i in selected)
            self.status.set('Silence confirmation recorded for selected IDs; import again into a new dataset folder.')

    def import_data(self):
        # GUI variables are read before launching the worker in background().
        args=getattr(self,'import_arguments',None) or (self.archive_path.get(),self.dataset_path.get(),self.consent.get(),self.mapping or self.metadata_path.get() or None,list(self.silence_ids))
        if self.input_identity and sha256(args[0])!=self.input_identity[0]:raise ValueError('Archive changed; inspect ZIP again before importing or confirming silence')
        self.dataset=import_zip(*args)
        if threading.current_thread() is threading.main_thread():self.import_finished()
        else:self.queue.put(('imported',None))
        return self.dataset

    def import_finished(self):
        self.show_preview(self.dataset)
        self.status.set(f"{self.dataset['status']}: {len(self.dataset['samples'])} samples. "+('Choose models in step 2.' if self.dataset['status']=='READY' else 'Fix listed errors and import to a new folder.'))
        if self.dataset['status']=='READY':self.tabs.select(self.models_frame)

    def build_models(self):
        self.mode=tk.StringVar(value='batch_file');self.repeats=tk.IntVar(value=1);self.seed=tk.IntVar(value=42)
        self.chunk=tk.DoubleVar(value=2);self.overlap=tk.DoubleVar(value=0)
        self.deferred=tk.BooleanVar(value=False)
        self.buttons(self.models_frame,[('Offline group (6)',lambda:self.choose_group('offline')),('Live group (5)',lambda:self.choose_group('live'))])
        extra=self.advanced_section(self.models_frame,'Advanced run settings')
        controls=ttk.Frame(extra);controls.pack(fill='x')
        for label,var,values in [('Mode',self.mode,['batch_file','paced_replay'])]:
            ttk.Label(controls,text=label).pack(side='left');ttk.Combobox(controls,textvariable=var,values=values,state='readonly',width=18).pack(side='left',padx=5)
        for label,var in [('Repeats',self.repeats),('Seed',self.seed),('Chunk seconds',self.chunk),('Overlap',self.overlap)]:
            ttk.Label(controls,text=label).pack(side='left',padx=4);ttk.Entry(controls,textvariable=var,width=6).pack(side='left')
        ttk.Checkbutton(extra,text='Show diagnostic models (MMS)',variable=self.deferred,command=self.populate_models).pack(anchor='w',pady=5)
        ttk.Label(self.models_frame,text='Choose a group above, or click model rows to select them. Setup status is checked before inference.').pack(anchor='w')
        self.model_tree=self.tree(self.models_frame,[('model','Checkpoint'),('backend','Backend'),('precision','Precision'),('device','Device'),('weights','Local weights'),('status','Preflight')],height=7)
        self.model_tree.column('model',width=270);self.model_tree.column('weights',width=300)
        self.model_tree.configure(displaycolumns=('model','status'),selectmode='extended')
        self.model_tree.bind('<Button-1>',self.toggle_model)
        self.buttons(self.models_frame,[('Check setup',self.check_models),('Configure model',self.configure_model)])
        self.buttons(extra,[('Edit config JSON',self.advanced),('Save config files',self.save_configs)])
        self.entry(extra,'Benchmark folder',self.benchmark_path)
        actions=self.buttons(self.models_frame,[('Start benchmark',self.start_benchmark),('Resume saved benchmark',self.resume_dialog)])
        self.run_buttons=list(actions.winfo_children())[:2]
        self.progress=ttk.Progressbar(self.models_frame,mode='determinate');self.progress.pack(fill='x',pady=4)
        self.populate_models()
        self.choose_group('offline')

    def toggle_model(self,event):
        key=self.model_tree.identify_row(event.y)
        if key:
            if key in self.model_tree.selection():self.model_tree.selection_remove(key)
            else:self.model_tree.selection_add(key)
            return 'break'

    def populate_models(self):
        self.model_tree.delete(*self.model_tree.get_children())
        for m in registry()['models']:
            if 'diagnostic_retry' in m['roles'] and not self.deferred.get():continue
            key=m['canonical_model_id'];c=self.presets[key]
            self.model_tree.insert('','end',iid=key,values=(key,c['backend'],c['precision'],c['device'],c.get('weights_path') or 'Not configured','Configured - check setup' if c.get('weights_path') and c.get('artifact_provenance') else 'Setup needed'))

    def select_models(self,ids):self.model_tree.selection_set(ids)

    def configs(self):
        ids=self.model_tree.selection()
        if not ids:raise ValueError('Select one or more models')
        return [{**self.presets[key],'mode':self.mode.get(),'chunk_seconds':self.chunk.get(),
                 'overlap_seconds':self.overlap.get(),'diagnostic_retry':self.deferred.get()} for key in ids]

    def configure_model(self):
        ids=self.model_tree.selection()
        if len(ids)!=1:raise ValueError('Select one model to configure')
        key=ids[0];c=self.presets[key];dialog=tk.Toplevel(self.window);dialog.title(key);dialog.geometry('900x500');variables={}
        for field in ('backend','device','precision','threads','beam_size','weights_path','artifact_provenance','worker_python'):
            var=tk.StringVar(value=str(c.get(field,'')));variables[field]=var
            browse=None
            if field=='weights_path':
                def folder(v=var):
                    p=filedialog.askdirectory(parent=dialog)
                    if p:v.set(p)
                browse=folder
            elif field in ('artifact_provenance','worker_python'):browse=lambda v=var:self.choose_file(v,[('All files','*.*')])
            self.entry(dialog,field,var,browse)
        vad=tk.BooleanVar(value=c['vad_filter']);ttk.Checkbutton(dialog,text='Decoder VAD filter (if supported)',variable=vad).pack(anchor='w')
        def save():
            for field,var in variables.items():c[field]=int(var.get()) if field in ('threads','beam_size') else var.get()
            c['vad_filter']=vad.get();self.populate_models();self.select_models([key]);dialog.destroy()
        ttk.Button(dialog,text='Save configuration',command=lambda:self.guarded(save)).pack(pady=10)

    def advanced(self):
        configs=self.configs();dialog=tk.Toplevel(self.window);dialog.title('Advanced model settings');dialog.geometry('900x600')
        text=tk.Text(dialog);text.pack(fill='both',expand=True);text.insert('1.0',json.dumps(configs,indent=2))
        def save():
            from .common import model_record
            values=json.loads(text.get('1.0','end'))
            for c in values:model_record(c['model_id'])
            for c in values:self.presets[c['model_id']]=c
            self.populate_models();self.select_models([c['model_id'] for c in values]);dialog.destroy()
        ttk.Button(dialog,text='Apply',command=lambda:self.guarded(save)).pack(pady=5)

    def save_configs(self):
        folder=filedialog.askdirectory(parent=self.window,title='Save model configs')
        if not folder:return
        for i,c in enumerate(self.configs()):write_json(Path(folder)/f'config-{uuid.uuid4().hex[:8]}-{i}.json',c,exclusive=True)
        self.status.set('Configuration files saved.')

    def check_models(self):
        configs=self.configs()
        def work():
            from .adapters import preflight
            for c in configs:
                try:r=preflight(c)
                except Exception as e:r={'status':'BLOCKED','reasons':[str(e)]}
                self.queue.put(('preflight',(c['model_id'],r)))
        self.background(work)

    def start_benchmark(self):
        if self.busy:raise ValueError('A task is already running')
        if not self.dataset:raise ValueError('Import a dataset first')
        if self.dataset['status']!='READY':raise ValueError('Fix input errors before starting; no invalid rows are silently dropped')
        configs=self.configs();source=Path(self.benchmark_path.get()).resolve()
        create_benchmark(Path(self.dataset_path.get())/'dataset.json',configs,source,self.repeats.get(),self.seed.get())
        self.source=source;self.tabs.select(self.results_frame)
        self.begin_tracking()
        self.background(lambda:run_benchmark(source,progress=lambda p:self.queue.put(('progress',p)),
            presenter=lambda text,ack:self.queue.put(('caption',(text,ack)))))

    def resume_dialog(self):
        if self.busy:raise ValueError('A task is already running; see Live process tracking.')
        path=filedialog.askdirectory(parent=self.window,title='Existing benchmark folder')
        if not path:return
        self.source=Path(path);load_benchmark(path);self.tabs.select(self.results_frame)
        self.begin_tracking()
        self.background(lambda:run_benchmark(path,resume=True,progress=lambda p:self.queue.put(('progress',p)),
            presenter=lambda text,ack:self.queue.put(('caption',(text,ack)))))

    def cancel(self):
        if self.source and (self.source/'benchmark.json').exists():
            cancel_benchmark(self.source);self.status.set('Cancellation requested; preserving all planned samples.')
            self.live_title.set('STOPPING — waiting for the worker to exit and save results.')
            self.stop_button.configure(state='disabled');self.monitor_next=0

    def background(self,fn):
        if self.busy:raise ValueError('Wait for the active task')
        if getattr(fn,'__name__','')=='import_data':
            current=(sha256(self.archive_path.get()),sha256(self.metadata_path.get()) if self.metadata_path.get() else None)
            if current!=self.input_identity:raise ValueError('ZIP/metadata changed; inspect ZIP again')
            self.import_arguments=(self.archive_path.get(),self.dataset_path.get(),self.consent.get(),self.mapping or self.metadata_path.get() or None,list(self.silence_ids))
        self.busy=True;self.status.set('Working locally…')
        def work():
            try:result=fn();self.queue.put(('done',result))
            except Exception as exc:self.queue.put(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def build_results(self):
        self.buttons(self.results_frame,[('Open results',self.open_source_dialog),('Export results',self.export_dialog)])
        extra=self.advanced_section(self.results_frame,'More analysis options')
        self.buttons(extra,[('Refresh',self.refresh_results),('Compare 2 runs',self.compare_selected),('Open folder',self.open_folder),('Detailed review',self.review_run)])
        self.filters={k:tk.StringVar() for k in ('run','model','domain','status')}
        filters=ttk.Frame(extra);filters.pack(fill='x',pady=4)
        for k,var in self.filters.items():
            ttk.Label(filters,text=k.title()).pack(side='left',padx=3)
            entry=ttk.Entry(filters,textvariable=var,width=16);entry.pack(side='left');entry.bind('<KeyRelease>',lambda e:self.render_results())
        self.tracking_tree=self.tree(self.results_frame,[('model','Model / repeat'),('phase','Current stage'),('ok','Succeeded'),('failed','Failed'),('cancelled','Cancelled'),('pending','Remaining'),('error','Latest error')],height=4)
        self.caption=tk.StringVar(value='Batch-file mode: follow Live process tracking above. Replay captions appear only in paced replay.')
        ttk.Label(self.results_frame,textvariable=self.caption,wraplength=1150,font=('Segoe UI',13)).pack(fill='x',pady=8)
        self.result_tree=self.tree(self.results_frame,[('model','Model'),('config','Config / Repeat'),('mode','Mode'),('status','Status'),
            ('done','Completed/Total'),('wer','WER'),('cer','CER'),('rtf','RTF'),('turnaround','Turnaround s'),('ram','Peak RAM MiB'),('endpoint','Latency endpoint'),('coverage','Coverage')],height=5)
        self.result_tree.configure(displaycolumns=('model','status','done','wer','rtf'))
        self.result_tree.bind('<<TreeviewSelect>>',lambda e:self.show_samples())
        self.sample_tree=self.tree(self.results_frame,[('id','Sample'),('domain','Domain'),('status','Status'),('wer','WER'),('sdi','S / D / I'),('reason','Missing / failure reason')],height=5)
        self.sample_tree.bind('<<TreeviewSelect>>',lambda e:self.show_transcript())
        self.buttons(self.results_frame,[('Play selected audio',self.play_audio)])
        self.details=tk.Text(self.results_frame,height=6,wrap='word');self.details.pack(fill='both',expand=True)

    def open_source_dialog(self):
        if self.busy:raise ValueError('Cancel or finish the current task before opening another benchmark.')
        path=filedialog.askdirectory(parent=self.window,title='Benchmark campaign or existing run')
        if path:self.open_source(path)

    def open_source(self,path):
        self.source=Path(path);self.tabs.select(self.results_frame)
        if (self.source/'benchmark.json').exists():self.begin_tracking(running=False)
        else:self.refresh_results()

    def begin_tracking(self,running=True):
        self.monitor_source=self.source;self.monitor_started=time.monotonic();self.monitor_next=0
        self.sealed_results={};self.monitor_data=None;self.running_campaign=running
        self.results_fingerprint=None;self.current_progress=None
        self.tracking_tree.delete(*self.tracking_tree.get_children())
        self.results=None;self.result_tree.delete(*self.result_tree.get_children())
        self.sample_tree.delete(*self.sample_tree.get_children())
        self.live_title.set('Preparing benchmark — verifying dataset and model files…')
        self.live_detail.set('This can take time for large weights. Progress will update automatically.')
        self.stop_button.configure(state='normal' if running else 'disabled')
        for button in self.run_buttons:button.configure(state='disabled' if running else 'normal')

    def request_tracking(self):
        if not self.monitor_source or self.monitor_busy or time.monotonic()<self.monitor_next:return
        self.monitor_busy=True;source=self.monitor_source;cached=dict(self.sealed_results)
        def work():
            try:
                data=snapshot(source)
                self.queue.put(('tracking',(source,data,cached)))
            except Exception as exc:self.queue.put(('tracking_error',(source,str(exc))))
        threading.Thread(target=work,daemon=True).start()

    def request_sealed_results(self,data):
        if self.results_busy:return
        self.results_busy=True;source=self.monitor_source;cached=dict(self.sealed_results)
        def work():
            try:
                # Only sealed terminal runs are scored; unfinished observations are progress only.
                for row in data['rows']:
                    folder=Path(row['run_path']);stamp=folder/'checksums.json'
                    if row['status'] in TERMINAL and stamp.exists():
                        key=(row['job_id'],stamp.stat().st_mtime_ns)
                        if key not in cached:
                            try:cached[key]=collect_results(source,sealed_job_id=row['job_id'])
                            except (ValueError,OSError,KeyError):pass  # sealing may still be in progress
                self.queue.put(('sealed',(source,cached)))
            except Exception as exc:self.queue.put(('sealed_error',(source,str(exc))))
        threading.Thread(target=work,daemon=True).start()

    def render_tracking(self,data,cached):
        self.monitor_data=data;self.sealed_results=cached
        active=data['active'];phase=data['status'].upper()
        hint=self.current_progress
        if not active and data['alive'] and hint and hint['status']=='running':
            phase+=f" | Model {hint['index']+1}/{hint['total']}: {hint['job']['config']['model_id']} | Checking weights / inputs"
        if active:
            phase+=f" | Model {active['index']}/{len(data['rows'])}: {active['model']} | {active['phase']}"
            if active['sample'] and active['status']=='running':phase+=f" | Audio: {active['sample']}"
        elif self.running_campaign and self.busy and not data['alive']:
            phase='Preparing / saving benchmark — please wait'
        self.live_title.set(phase)
        age=active['event_age_s'] if active else data['last_event_age_s']
        age_text=f'{age:.0f}s ago' if age is not None else 'waiting for first event'
        elapsed=int(time.monotonic()-self.monitor_started)
        model_time=f" | Current model elapsed: {active['elapsed_s']:.0f}s" if active and active.get('elapsed_s') is not None else ''
        warning=' | No recent event: check stage / worker; this alone does not mean frozen.' if age is not None and age>60 and data['alive'] else ''
        self.live_detail.set(f"Succeeded {data['completed']}/{data['total']} | Failed {data['failed']} | Cancelled {data['cancelled']} | Remaining {data['pending']} | Monitoring {elapsed//60:02d}:{elapsed%60:02d}{model_time}\nLast event: {age_text} | Worker processes: {len(data['workers'])} | Worker RAM: {data['worker_rss_mib']:.0f} MiB{warning}")
        self.live_progress.configure(maximum=max(1,data['total']),value=data['completed']+data['failed'])
        self.stop_button.configure(state='normal' if data['alive'] and data['status']!='stopping' else 'disabled')
        for button in self.run_buttons:button.configure(state='disabled' if self.busy or data['alive'] else 'normal')
        for row in data['rows']:
            values=(f"{row['model']} / {row['repeat']}",row['phase'],f"{row['completed']}/{row['total']}",row['failed'],row['cancelled'],row['pending'],row['error'])
            if self.tracking_tree.exists(row['job_id']):self.tracking_tree.item(row['job_id'],values=values)
            else:self.tracking_tree.insert('','end',iid=row['job_id'],values=values)
        if cached:
            # Keep only the newest sealed revision per job (e.g. after Resume).
            newest={}
            for key,value in sorted(cached.items(),key=lambda item:item[0][1]):newest[key[0]]=value
            fingerprint=tuple(sorted(cached))
            if fingerprint!=getattr(self,'results_fingerprint',None):
                combined={k:[] for k in ('runs','samples','transcripts','provenance')}
                for value in newest.values():
                    for k in combined:combined[k].extend(value[k])
                self.results=combined;self.render_results();self.results_fingerprint=fingerprint

    def refresh_results(self):
        if not self.source:return
        if (self.source/'benchmark.json').exists():
            self.monitor_next=0;self.request_tracking();return
        if self.busy:return
        self.results=collect_results(self.source);self.render_results()

    def render_results(self):
        if not self.results:return
        self.result_tree.delete(*self.result_tree.get_children());self.sample_tree.delete(*self.sample_tree.get_children())
        fmt=lambda value,scale=1: '—' if value is None else f'{value*scale:.4f}'
        for i,r in enumerate(self.results['runs']):
            if any(self.filters[k].get().casefold() not in str(r.get(field,'')).casefold() for k,field in [('run','run_id'),('model','model_id'),('status','status')]):continue
            if self.filters['domain'].get() and not any(self.filters['domain'].get().casefold() in s['domain'].casefold() for s in self.results['samples'] if s['run_id']==r['run_id'] and s['model_config_id']==r['model_config_id']):continue
            endpoint='paint proxy' if r.get('ui_request_to_paint_proxy_s_coverage',0)>0 else 'word/display not measured'
            self.result_tree.insert('','end',iid=str(i),values=(r['model_id'] or r.get('archived_label') or 'SYNTHETIC fixture',
                r['model_config_id'][:10]+f" / {r['repeat_id']}",r['mode'],r['status'],f"{r['completed']}/{r['planned']}",fmt(r['normalized_wer_micro']),fmt(r['normalized_cer']),
                fmt(r['rtf']),fmt(r['turnaround_s']),fmt(r['peak_worker_rss_bytes'],1/1048576),endpoint,fmt(r.get('ui_request_to_paint_proxy_s_coverage',0))))
        self.status.set('WER/CER are ratios (0.15 = 15%). Full-run totals shown; domain filter limits listed runs/samples, not the total scores. Export contains all observations.')

    def show_samples(self):
        selected=self.result_tree.selection();self.sample_tree.delete(*self.sample_tree.get_children())
        if not selected:return
        r=self.results['runs'][int(selected[0])]
        for i,s in enumerate(self.results['samples']):
            if s['run_id']!=r['run_id'] or s['model_config_id']!=r['model_config_id']:continue
            if self.filters['domain'].get().casefold() not in s['domain'].casefold():continue
            self.sample_tree.insert('','end',iid=str(i),values=(s['sample_id'],s['domain'],s['status'],s['normalized_wer'] if s['normalized_wer'] is not None else '—',
                ' / '.join(str(s['normalized_'+k]) if s['normalized_'+k] is not None else '—' for k in ('S','D','I')),s['missing_reason'] or ''))

    def selected_transcript(self):
        selected=self.sample_tree.selection()
        if not selected:raise ValueError('Select a sample first')
        return self.results['transcripts'][int(selected[0])]

    def show_transcript(self):
        if not self.sample_tree.selection():return
        r=self.selected_transcript();self.details.delete('1.0','end')
        self.details.insert('1.0',f"REFERENCE\n{r['reference']}\n\nHYPOTHESIS\n{r['hypothesis']}\n\nNORMALIZED ALIGNMENT\n"+json.dumps(r['normalized_alignment'],ensure_ascii=False))

    def play_audio(self):
        r=self.selected_transcript();path=r.get('audio')
        if not path or not Path(path).is_file():raise ValueError('This evidence has no linked local waveform. Imported ZIP runs retain playable WAVs.')
        import winsound
        winsound.PlaySound(path,winsound.SND_FILENAME|winsound.SND_ASYNC)

    def review_run(self):
        selected=self.result_tree.selection()
        if not selected:raise ValueError('Select a run')
        self.app.run_dir=Path(self.results['provenance'][int(selected[0])]['source_path'])
        if not (self.app.run_dir/'manifest.json').exists():raise ValueError('Job has not produced a run; its planned/cancelled rows remain exportable')
        if getattr(self.app,'simple_mode',False):
            from .ui import LabApp
            review=LabApp(tk.Toplevel(self.window),self.app.run_dir)
            review.tabs.select(review.frames['review'])
        else:
            self.app.refresh();self.app.tabs.select(self.app.frames['review']);self.app.root.lift()

    def compare_selected(self):
        selected=self.result_tree.selection()
        if len(selected)!=2:raise ValueError('Ctrl-select exactly two run rows (A then B in table order)')
        from .analysis_export import compare_runs
        a,b=[self.results['runs'][int(i)] for i in selected]
        result=compare_runs(self.source,a['run_id'],a['model_config_id'],self.source,b['run_id'],b['model_config_id'])
        self.details.delete('1.0','end');self.details.insert('1.0',json.dumps({'candidate_a':a['model_id'],'candidate_b':b['model_id'],**result},indent=2))

    def open_folder(self):
        if self.source and self.source.is_dir():os.startfile(str(self.source.resolve()))

    def export_bundle(self,out):
        if self.busy:raise ValueError('Wait for completion/cancellation before exporting sealed evidence')
        if not self.source:raise ValueError('Open or run a benchmark first')
        result=export_analysis(self.source,out);self.status.set('Analysis bundle saved: '+str(out));return result

    def export_dialog(self):
        path=filedialog.asksaveasfilename(parent=self.window,title='New analysis ZIP (do not overwrite)',defaultextension='.zip',filetypes=[('ZIP','*.zip')])
        if path:self.export_bundle(path)

    def poll(self):
        try:
            while True:
                kind,value=self.queue.get_nowait()
                if kind=='tracking':
                    source,data,cached=value;self.monitor_busy=False;self.monitor_next=time.monotonic()+1
                    if source==self.monitor_source:
                        self.render_tracking(data,self.sealed_results);self.request_sealed_results(data)
                elif kind=='sealed':
                    source,cached=value;self.results_busy=False
                    if source==self.monitor_source and self.monitor_data:self.render_tracking(self.monitor_data,cached)
                elif kind=='sealed_error':
                    self.results_busy=False
                    self.status.set('Could not refresh sealed results: '+value[1])
                elif kind=='tracking_error':
                    source,error=value;self.monitor_busy=False;self.monitor_next=time.monotonic()+1
                    if source==self.monitor_source:self.live_detail.set('Waiting for a consistent progress snapshot: '+error)
                elif kind=='caption':
                    text,ack=value;self.caption.set(text);self.window.update_idletasks()
                    if self.tabs.select()==str(self.results_frame) and self.window.state()=='normal':ack()
                elif kind=='progress':
                    self.current_progress=value;self.monitor_next=0
                    self.progress['maximum']=value['total'];self.progress['value']=value['index']
                    self.status.set(f"{value['index']}/{value['total']} jobs · {value['job']['config']['model_id']} · {value['status']}")
                elif kind=='preflight':
                    key,r=value;self.model_tree.set(key,'status',r['status']+': '+'; '.join(r['reasons']))
                elif kind=='imported':self.import_finished()
                elif kind=='error':
                    self.busy=False;self.running_campaign=False;self.monitor_next=0;self.status.set(value);messagebox.showerror('Benchmark failed',value,parent=self.window)
                else:
                    self.busy=False
                    if self.running_campaign:
                        self.running_campaign=False;self.monitor_next=0
                        label=value.get('status','finished') if isinstance(value,dict) else 'finished'
                        self.live_title.set('Benchmark '+label);self.status.set('Benchmark '+label+' — see per-model results and errors below.');self.window.bell()
                    if self.source:self.refresh_results()
        except queue.Empty:pass
        self.request_tracking()
        self.timer=self.window.after(200,self.poll)

    def close(self):
        if self.busy:
            self.cancel();self.window.after(300,self.close)
        else:
            self.window.after_cancel(self.timer);self.window.destroy()
            if getattr(self.app,'simple_mode',False):self.app.root.destroy()
