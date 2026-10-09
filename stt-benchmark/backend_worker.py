"""Private line-JSON worker; stdout reserved for protocol, library logs to stderr."""
import json
import sys
import importlib.metadata
from contextlib import redirect_stdout
from benchmark.adapters import ADAPTERS, validate_config


def main():
    adapter = None
    for line in sys.stdin:
        try:
            value = json.loads(line)
            with redirect_stdout(sys.stderr):
                if value['action'] == 'load':
                    config = validate_config(value['config'])
                    adapter = ADAPTERS[config['backend']](config)
                    adapter.load()
                    versions = {}
                    for package in ('faster-whisper', 'torch', 'transformers', 'qwen-asr', 'nemo_toolkit', 'funasr', 'vosk', 'requests', 'google-cloud-speech'):
                        try:
                            versions[package] = importlib.metadata.version(package)
                        except importlib.metadata.PackageNotFoundError:
                            pass
                    result = {'python': sys.version, 'executable': sys.executable, 'packages': versions}
                elif value['action'] == 'transcribe' and adapter is not None:
                    result = adapter.transcribe(value['audio'], value['language'])
                else:
                    raise ValueError('Invalid worker request.')
            reply = {'ok': True, 'result': result}
        except Exception as exc:
            reply = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
        sys.stdout.write(json.dumps(reply, ensure_ascii=True) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
