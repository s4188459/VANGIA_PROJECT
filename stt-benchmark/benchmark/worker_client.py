"""Keep conflicting optional ML stacks in separate Python environments."""
import json
from pathlib import Path
import subprocess
import tempfile
import queue
import threading


class WorkerAdapter:
    def __init__(self, config):
        self.config, self.process, self.log = config, None, None

    def request(self, message):
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()
        replies = queue.Queue(maxsize=1)
        threading.Thread(target=lambda: replies.put(self.process.stdout.readline()), daemon=True).start()
        try:
            line = replies.get(timeout=1800 if message['action'] == 'load' else 600)
        except queue.Empty:
            self.process.kill()
            raise TimeoutError('Backend quá thời gian: tối đa 30 phút nạp model / 10 phút mỗi lần nhận dạng.')
        if not line:
            raise RuntimeError('Backend worker đã dừng. Kiểm tra thư viện/GPU của môi trường Python đã chọn.')
        result = json.loads(line)
        if not result['ok']:
            raise RuntimeError(result['error'])
        return result.get('result')

    def load(self):
        self.log = tempfile.TemporaryFile()
        self.process = subprocess.Popen([self.config['python_executable'], '-u',
                     str(Path(__file__).resolve().parents[1] / 'backend_worker.py')],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                     text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return self.request({'action': 'load', 'config': self.config})

    def transcribe(self, audio_path, language):
        return self.request({'action': 'transcribe', 'audio': str(Path(audio_path).resolve()), 'language': language})

    def close(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=10)
            self.process.stdin.close()
            self.process.stdout.close()
        if self.log:
            self.log.close()
