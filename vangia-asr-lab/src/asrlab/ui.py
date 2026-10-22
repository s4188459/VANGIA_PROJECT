"""Local Tk desktop. Model execution never runs in the UI event loop."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from .common import registry, read_json


class BaseLabApp:
    def __init__(self, root, run_dir=None):
        self.root, self.run_dir = root, Path(run_dir) if run_dir else None
        root.title('Vangia | English ASR Selection & Validation Lab')
        root.geometry('1280x820')
        style = ttk.Style(root); style.theme_use('clam')
        style.configure('Treeview', rowheight=29)
        ttk.Label(root, text='VANGIA  /  English ASR Lab', font=('Segoe UI', 23, 'bold')).pack(anchor='w', padx=24, pady=(20,8))
        ttk.Label(root, text='[P] 15% WER / 3 s P95 are PROVISIONAL • [G] Historical RTF is not live caption lag', foreground='#875000').pack(anchor='w', padx=24)
        bar = ttk.Frame(root); bar.pack(fill='x', padx=24, pady=14)
        ttk.Button(bar, text='New benchmark (ZIP)', command=self.new_benchmark).pack(side='left',padx=(0,8))
        ttk.Button(bar, text='Analysis / CSV export', command=self.analysis_window).pack(side='left',padx=(0,8))
        ttk.Button(bar, text='Open run', command=self.open_run).pack(side='left')
        ttk.Button(bar, text='Import historical JSON + CSV', command=self.import_legacy).pack(side='left', padx=8)
        ttk.Button(bar, text='Audit evidence', command=self.audit).pack(side='left')
        self.tabs = ttk.Notebook(root); self.tabs.pack(fill='both', expand=True, padx=24, pady=10)
        self.registry_tab = ttk.Frame(self.tabs); self.tabs.add(self.registry_tab, text='Model Lab / Registry')
        self.build_registry()
        self.summary = tk.Text(root, height=4, wrap='word', font=('Consolas',10)); self.summary.pack(fill='x', padx=24,pady=8)
        self.refresh()

    def build_registry(self):
        for role in ('live','offline','diagnostic_retry'):
            ttk.Label(self.registry_tab, text=role.upper(), font=('Segoe UI',11,'bold')).pack(anchor='w', pady=6)
            tree = ttk.Treeview(self.registry_tab, columns=('id','wer','rtf','backend','identity'), show='headings', height=5 if role!='diagnostic_retry' else 2)
            for key, title, width in [('id','Checkpoint',320),('wer','Historical WER',115),('rtf','Whole-file RTF',110),('backend','Backend',140),('identity','Provenance gap',250)]:
                tree.heading(key,text=title); tree.column(key,width=width)
            for m in registry()['models']:
                if role in m['roles']:
                    tree.insert('', 'end', values=(m['canonical_model_id'], 'null / failed' if m['legacy_wer'] is None else f"{m['legacy_wer']:.2%}",
                        'null' if m['legacy_rtf'] is None else f"{m['legacy_rtf']:.4f}",m['legacy_backend'],m['checkpoint_resolution_status']))
            tree.pack(fill='x')

    def refresh(self):
        text = 'Local storage • English only • No automatic downloads. New experiments: NOT MEASURED.'
        if self.run_dir:
            try:
                m=read_json(self.run_dir/'manifest.json')
                text += f"\nRun {m['run_id']} | {m['input_mode']} | {m['dataset_split']} | {m['status']}"
            except (ValueError,OSError) as exc:
                text += '\n'+str(exc)
        self.summary.delete('1.0','end'); self.summary.insert('1.0',text)

    def open_run(self):
        path=filedialog.askdirectory(title='Open evidence run')
        if path: self.run_dir=Path(path); self.refresh()

    def import_legacy(self):
        j=filedialog.askopenfilename(title='Original historical JSON',filetypes=[('JSON','*.json')])
        if not j: return
        c=filedialog.askopenfilename(title='Original summary CSV',filetypes=[('CSV','*.csv')])
        if not c: return
        parent=filedialog.askdirectory(title='Parent directory for new historical run')
        if not parent: return
        from .legacy import import_legacy
        from .common import utcnow
        try:
            self.run_dir=Path(parent)/('legacy-'+utcnow().replace(':','-'))
            import_legacy(j,c,self.run_dir); self.refresh()
        except (ValueError,OSError) as exc: messagebox.showerror('Import failed',str(exc))

    def audit(self):
        if not self.run_dir: return
        from .storage import audit
        messagebox.showinfo('Evidence integrity',str(audit(self.run_dir)))

    def new_benchmark(self):
        from .benchmark_ui import BenchmarkWizard
        return BenchmarkWizard(self)

    def analysis_window(self):
        from .benchmark_ui import BenchmarkWizard
        return BenchmarkWizard(self,self.run_dir)


from .workbench import Workbench


class LabApp(Workbench, BaseLabApp):
    pass


def launch(run_dir=None, smoke=False):
    from types import SimpleNamespace
    from .benchmark_ui import BenchmarkWizard
    root=tk.Tk(); root.withdraw()
    app=SimpleNamespace(root=root,simple_mode=True)
    wizard=BenchmarkWizard(app)
    menu=tk.Menu(wizard.window)
    tools=tk.Menu(menu,tearoff=False)
    def open_advanced():
        advanced=tk.Toplevel(wizard.window)
        LabApp(advanced,run_dir)
    tools.add_command(label='Advanced laboratory',command=open_advanced)
    menu.add_cascade(label='Tools',menu=tools)
    wizard.window.configure(menu=menu)
    if smoke:
        root.update(); assert len(wizard.tabs.tabs()) == 3
        root.after(100,wizard.close)
    root.mainloop()
