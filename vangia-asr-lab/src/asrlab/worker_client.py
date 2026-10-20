"""Persistent isolated process with bounded timeout, cancellation and measured resource sampling."""
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
import psutil


class ProcessTreeProbe:
    """Include Windows venv launcher's actual interpreter and backend children."""
    def __init__(self, pid):
        self.root = psutil.Process(pid)
        self.probes = {}

    def processes(self):
        try: return [self.root] + self.root.children(recursive=True)
        except psutil.NoSuchProcess: return []

    def sample(self):
        row = {'monotonic_ns': time.monotonic_ns(), 'pid': self.root.pid,
               'cpu_percent': 0., 'rss_bytes': 0, 'read_bytes': 0, 'write_bytes': 0,
               'process_count': 0, 'resource_scope': 'worker_process_tree', 'partial': False}
        for proc in self.processes():
            try:
                key = (proc.pid, proc.create_time())
                probe = self.probes.setdefault(key, proc)
                io = probe.io_counters()
                row['rss_bytes'] += probe.memory_info().rss
                row['cpu_percent'] += probe.cpu_percent()
                row['read_bytes'] += io.read_bytes
                row['write_bytes'] += io.write_bytes
                row['process_count'] += 1
            except psutil.Error:
                row['partial'] = True
        return row

    def terminate(self):
        processes = {p.pid:p for p in self.processes()}
        processes.update({p.pid:p for p in self.probes.values() if p.is_running()})
        processes = list(processes.values())
        for proc in reversed(processes):
            try: proc.terminate()
            except psutil.NoSuchProcess: pass
        _, alive = psutil.wait_procs(processes, timeout=3)
        for proc in alive:
            try: proc.kill()
            except psutil.NoSuchProcess: pass
        psutil.wait_procs(alive, timeout=2)


class WorkerClient:
    def __init__(self,python,run_dir,cancel=lambda:False):
        self.cancel=cancel;self.responses=queue.Queue();self.resources=[]
        self.log=(Path(run_dir)/'worker.stderr.log').open('a',encoding='utf-8')
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]),'PYTHONUTF8':'1',
             'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1'}
        self.process=subprocess.Popen([python or sys.executable,'-m','asrlab.worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=self.log,text=True,encoding='utf-8',env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        threading.Thread(target=self._reader,daemon=True).start()
        self.probe=ProcessTreeProbe(self.process.pid);self.probe.sample()

    def _reader(self):
        try:
            for line in self.process.stdout:
                try:self.responses.put(json.loads(line))
                except ValueError:self.responses.put({'ok':False,'error':'Invalid worker JSON'})
        finally:self.responses.put({'ok':False,'error':'worker_crash: process exited'})

    def request(self,op,timeout=600,**payload):
        if timeout<=0:raise ValueError('Timeout must be positive')
        ident=uuid.uuid4().hex;started=time.monotonic()
        self.process.stdin.write(json.dumps({'id':ident,'op':op,**payload})+'\n');self.process.stdin.flush()
        while True:
            if self.cancel():self.close();raise InterruptedError('cancelled')
            if time.monotonic()-started>timeout:self.close();raise TimeoutError(f'worker timeout during {op}')
            try:
                result=self.responses.get(timeout=.1)
                if not result['ok']:raise RuntimeError(result['error'])
                if result.get('id')!=ident:raise RuntimeError('Worker response ID mismatch')
                self.resources.append(self.probe.sample())
                return result
            except queue.Empty:
                try:
                    self.resources.append(self.probe.sample())
                except psutil.Error:pass

    def close(self):
        self.probe.terminate()
        if self.process.poll() is None:
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        for pipe in (self.process.stdin,self.process.stdout):
            if pipe:pipe.close()
        self.log.close()
