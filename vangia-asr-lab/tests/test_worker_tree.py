import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest


def test_probe_includes_descendant_memory_and_close_stops_descendants(tmp_path):
    from asrlab import worker_client
    assert hasattr(worker_client, 'ProcessTreeProbe')
    child_code = 'import time; data=bytearray(32*1024*1024); time.sleep(30)'
    parent_code = ('import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-c",'
                   + repr(child_code) + ']); print(p.pid,flush=True); time.sleep(30)')
    parent = subprocess.Popen([sys.executable, '-c', parent_code], stdout=subprocess.PIPE, text=True)
    child_pid = int(parent.stdout.readline())
    probe = worker_client.ProcessTreeProbe(parent.pid)
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            row = probe.sample()
            if row['rss_bytes'] > 32*1024*1024 and row['process_count'] >= 2:
                break
            time.sleep(.05)
        assert row['process_count'] >= 2
        assert row['rss_bytes'] > 32*1024*1024
        assert row['resource_scope'] == 'worker_process_tree'
        probe.terminate()
        parent.wait(timeout=5)
        assert not psutil.pid_exists(child_pid) or psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE
    finally:
        for pid in (child_pid, parent.pid):
            try: psutil.Process(pid).kill()
            except psutil.NoSuchProcess: pass
        parent.wait(timeout=5)
        parent.stdout.close()
