"""Probe imports in isolated environments. No weights downloads or audio uploads."""
import json
from pathlib import Path
import subprocess
import sys
from benchmark.catalog import BACKENDS, backend_status
from benchmark.datasets import write_json

root = Path(__file__).resolve().parent
results = {}
available = backend_status()
for name, (module, _) in BACKENDS.items():
    python = Path(available[name]['python_executable'] or sys.executable)
    try:
        p = subprocess.run([str(python), '-c', 'import ' + module], capture_output=True,
                           text=True, encoding='utf-8', errors='replace', timeout=120)
        results[name] = {'python_executable': str(python), 'import_ok': p.returncode == 0,
                         'error': p.stderr[-2500:] if p.returncode else ''}
    except Exception as exc:
        results[name] = {'python_executable': str(python), 'import_ok': False, 'error': str(exc)}
    print(name, 'OK' if results[name]['import_ok'] else results[name]['error'], flush=True)
    write_json(root / 'data' / 'backend-checks.json', results)
