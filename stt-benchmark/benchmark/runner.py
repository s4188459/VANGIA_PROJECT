import copy
import csv
import hashlib
import importlib.metadata
import io
import json
import platform
import statistics
import threading
import time
import uuid
from pathlib import Path

from .adapters import ADAPTERS, validate_config
from .datasets import utc_now, write_json
from .scoring import NORMALIZATION, score
from .catalog import supported_languages
from .replay import validate_options, replay, percentile


def timing_summary(rows):
    ok = [r for r in rows if r['status'] == 'ok']
    result = {}
    for metric in ('wall_s', 'first_text_s', 'first_text_from_vad_s', 'finalization_from_eof_s',
                   'finalization_from_vad_s', 'max_queue_s', 'chunk_processing_s', 'chunk_lag_s'):
        values = [r.get(metric, r.get('replay_metrics', {}).get(metric)) for r in ok]
        if metric in ('chunk_processing_s', 'chunk_lag_s'):
            key = 'elapsed_s' if metric == 'chunk_processing_s' else 'lag_s'
            values = [c[key] for r in ok for c in r.get('chunks', [])]
        values = [v for v in values if v is not None]
        for suffix, value in [('median', statistics.median(values) if values else None), ('p95', percentile(values)),
                              ('max', max(values) if values else None)]:
            result[f'{metric}_{suffix}'] = value
    return result


def aggregate(rows):
    ok = [r for r in rows if r["status"] == "ok"]
    words = sum(r["reference_words"] for r in ok)
    duration = sum(r["duration_s"] for r in ok)
    elapsed = sum(r["elapsed_s"] for r in ok)
    chars = sum(r.get('reference_characters', 0) for r in ok)
    chunks = [c for r in ok for c in r.get('chunks', [])]
    return {**timing_summary(rows), "completed": len(ok), "failed": sum(r["status"] == "error" for r in rows),
            'cer': sum(r.get('character_errors', 0) for r in ok) / chars if chars else None,
            'character_errors': sum(r.get('character_errors', 0) for r in ok), 'reference_characters': chars,
            'chunk_p95_s': percentile([c['elapsed_s'] for c in chunks]),
            'lag_p95_s': percentile([c['lag_s'] for c in chunks]),
            'first_text_p95_s': percentile([r['replay_metrics']['first_text_s'] for r in ok
                                            if r.get('replay_metrics', {}).get('first_text_s') is not None]),
            'deadline_misses': sum(r.get('replay_metrics', {}).get('deadline_misses', 0) for r in ok),
            "reference_words": words, "errors": sum(r["errors"] for r in ok),
            "wer": sum(r["errors"] for r in ok) / words if words else None,
            "inference_s": elapsed, "audio_s": duration, "rtf": elapsed / duration if duration else None}


def summarize(run):
    sets = [{r["id"] for r in m["samples"] if r["status"] == "ok"} for m in run["models"]]
    common = set.intersection(*sets) if sets else set()
    for model in run["models"]:
        model["summary"] = aggregate(model["samples"])
        model["common_summary"] = aggregate([r for r in model["samples"] if r["id"] in common])
    run["common_sample_count"] = len(common)


class Runner:
    def __init__(self, root, adapters=None):
        self.root = Path(root)
        self.adapters = adapters or ADAPTERS
        self.lock = threading.RLock()
        self.active = None
        self.cancel_event = threading.Event()
        self.thread = None
        # Mark runs interrupted by a prior shutdown; never pretend they completed.
        for path in (self.root / "runs").glob("*/run.json"):
            run = json.loads(path.read_text(encoding="utf-8"))
            if run["status"] in ("running", "cancelling"):
                run.update(status="interrupted", message="The process stopped before completion.")
                for model in run["models"]:
                    if model["status"] in ("running", "loading", "queued"):
                        model["status"] = "interrupted"
                summarize(run)
                write_json(path, run)

    def start(self, dataset_id, configs, options=None):
        options = validate_options(options)
        experiment = options['mode'] in ('experiment2', 'experiment3')
        if experiment:
            live = options['mode'] == 'experiment2'
            configs = [dict(backend='qwen-asr' if live else 'faster-whisper',
                model='Qwen/Qwen3-ASR-0.6B' if live else 'large-v3',
                label='Experiment 2 — Qwen live' if live else 'Experiment 3 — Whisper offline',
                device='cpu', compute_type='float32' if live else 'int8',
                cpu_threads=4, beam_size=1 if live else 5, vad_filter=not live,
                allow_download=False, languages=['en'])]
        if not isinstance(dataset_id, str) or len(dataset_id) != 32 or any(c not in "0123456789abcdef" for c in dataset_id):
            raise ValueError("Invalid dataset ID.")
        if not isinstance(configs, list) or not 1 <= len(configs) <= 50:
            raise ValueError("Select 1–50 model configurations.")
        configs = [validate_config(c) for c in configs]
        if len({c["label"] for c in configs}) != len(configs):
            raise ValueError("Configuration labels must be unique within a run.")
        dataset = json.loads((self.root / "datasets" / dataset_id / "manifest.json").read_text(encoding="utf-8"))
        source_dataset = copy.deepcopy(dataset)
        if experiment and dataset['language'] != 'en':
            raise ValueError('Experiments 2 and 3 require an English dataset.')
        if options['sample_limit']:
            dataset['samples'] = dataset['samples'][:options['sample_limit']]
        for config in configs:
            if dataset['language'] not in supported_languages(config):
                raise ValueError(f"{config['label']} does not support dataset {dataset['language']}; choose a multilingual model or one trained for this language.")
            if config['backend'] in ('elevenlabs', 'google-chirp') and not options['allow_cloud']:
                raise ValueError('Authorize cloud audio uploads before running API models.')
        if dataset["language"] != "en":
            for config in configs:
                name = config["model"].replace("\\", "/").rstrip("/").split("/")[-1]
                if name.endswith((".en", "-en")):
                    raise ValueError("Vietnamese datasets require a multilingual model, not an .en model.")
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError("A run is already active. Wait for completion or cancel it first.")
            run_id = uuid.uuid4().hex
            versions = {}
            for package in ("faster-whisper", "ctranslate2", "av", "torch", "transformers", "qwen-asr", "nemo_toolkit", "funasr", "vosk", "google-cloud-speech", "requests"):
                try:
                    versions[package] = importlib.metadata.version(package)
                except importlib.metadata.PackageNotFoundError:
                    versions[package] = "not installed"
            run = {"id": run_id, "created_at": utc_now(), "status": "running", "message": "Preparing",
                   'options': options, 'cer_normalization': 'same-as-wer-without-whitespace-v1',
                   "dataset": dataset, 'source_dataset': source_dataset, "normalization": NORMALIZATION,
                   "environment": {"platform": platform.platform(), "processor": platform.processor(),
                                   "python": platform.python_version(), "packages": versions},
                   "models": [{"config": c, "status": "queued", "samples": [], "load_s": None} for c in configs],
                   "completed_tasks": 0, "total_tasks": len(dataset["samples"]) * len(configs)}
            self.active = run
            self.cancel_event.clear()
            self._save(run)
            self.thread = threading.Thread(target=self._execute, args=(run,), daemon=True)
            self.thread.start()
            return copy.deepcopy(run)

    def resume(self, run_id):
        if not isinstance(run_id, str) or len(run_id) != 32 or any(c not in '0123456789abcdef' for c in run_id):
            raise ValueError('Invalid run ID.')
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError('A run is already active. Wait for completion or cancel it first.')
            path = self.root / 'runs' / run_id / 'run.json'
            original = path.read_bytes()
            run = json.loads(original)
            if run['status'] != 'interrupted':
                raise ValueError('Only interrupted runs can be resumed.')
            dataset = run['dataset']
            folder = self.root / 'datasets' / dataset['id']
            if json.loads((folder / 'manifest.json').read_text(encoding='utf-8')) != run.get('source_dataset', dataset):
                raise ValueError('Dataset changed after the original run; cannot resume.')
            # Validate all inputs, including already-scored samples, before writing.
            for sample in dataset['samples']:
                audio = folder / 'audio' / (sample['id'] + '.wav')
                reference = (folder / 'transcripts' / (sample['id'] + '.txt')).read_text(encoding='utf-8')
                if (hashlib.sha256(audio.read_bytes()).hexdigest() != sample['audio_sha256']
                        or hashlib.sha256(reference.encode()).hexdigest() != sample['reference_sha256']):
                    raise ValueError('Dataset changed after the original run; cannot resume.')
            ids = {s['id'] for s in dataset['samples']}
            for model in run['models']:
                saved = [s['id'] for s in model['samples']]
                if len(saved) != len(set(saved)) or not set(saved) <= ids:
                    raise ValueError('Saved sample IDs are inconsistent; cannot resume.')
            # Exclusive, byte-for-byte backup; failure aborts before the run is changed.
            backup = path.with_name(f'run.before-resume-{uuid.uuid4().hex}.json')
            with backup.open('xb') as output:
                output.write(original)
            run.setdefault('resumptions', []).append({'at': utc_now(), 'backup': backup.name})
            run.update(status='running', message='Resuming saved run',
                       completed_tasks=sum(len(m['samples']) for m in run['models']))
            run.pop('finished_at', None)
            for model in run['models']:
                if len(model['samples']) < len(ids):
                    model['status'] = 'queued'
            self._save(run)
            self.active = run
            self.cancel_event.clear()
            self.thread = threading.Thread(target=self._execute, args=(run,), daemon=True)
            self.thread.start()
            return copy.deepcopy(run)

    def _save(self, run):
        summarize(run)
        write_json(self.root / "runs" / run["id"] / "run.json", run)

    def get(self, run_id):
        if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
            raise ValueError("Invalid run ID.")
        with self.lock:
            if self.active and self.active["id"] == run_id:
                return copy.deepcopy(self.active)
            return json.loads((self.root / "runs" / run_id / "run.json").read_text(encoding="utf-8"))

    def cancel(self, run_id):
        with self.lock:
            if not self.active or self.active["id"] != run_id or not self.thread.is_alive():
                raise ValueError("This run is no longer active.")
            self.cancel_event.set()
            self.active.update(status="cancelling", message="Will stop after the current model load or sample.")
            self._save(self.active)

    def _execute(self, run):
        dataset = run["dataset"]
        folder = self.root / "datasets" / dataset["id"]
        try:
            for model in run["models"]:
                if self.cancel_event.is_set():
                    break
                done = {row['id'] for row in model['samples']}
                if all(sample['id'] in done for sample in dataset['samples']):
                    if model['status'] not in ('completed', 'error'):
                        model['status'] = 'completed'
                    continue
                adapter = None
                try:
                    with self.lock:
                        model["status"] = "loading"
                        run["message"] = f"Loading {model['config']['label']}"
                        self._save(run)
                    config = model['config']
                    if run['options']['mode'] in ('experiment2', 'experiment3'):
                        from .experiments import ExperimentAdapter
                        adapter = ExperimentAdapter(config, run['options']['mode'])
                    elif config.get('python_executable'):
                        from .worker_client import WorkerAdapter
                        adapter = WorkerAdapter(config)
                    else:
                        adapter = self.adapters[config['backend']](config)
                    started = time.perf_counter()
                    runtime = adapter.load()
                    with self.lock:
                        if isinstance(runtime, dict):
                            model['runtime'] = runtime
                        model["load_s"] = time.perf_counter() - started
                        model.setdefault('load_sessions', []).append(dict(at=utc_now(), seconds=model['load_s']))
                        model["status"] = "running"
                    for sample in dataset["samples"]:
                        if sample['id'] in done:
                            continue
                        if self.cancel_event.is_set():
                            break
                        row = {"id": sample["id"], "duration_s": sample["duration_s"]}
                        with self.lock:
                            run["message"] = f"{model['config']['label']} · {sample['id']}"
                            self._save(run)
                        try:
                            audio = folder / "audio" / (sample["id"] + ".wav")
                            text = (folder / "transcripts" / (sample["id"] + ".txt")).read_text(encoding="utf-8")
                            if hashlib.sha256(audio.read_bytes()).hexdigest() != sample["audio_sha256"] or hashlib.sha256(text.encode()).hexdigest() != sample["reference_sha256"]:
                                raise ValueError("Data changed after import; import a new version.")
                            started = time.perf_counter()
                            if run['options']['mode'] == 'experiment2':
                                from .experiments import realtime_replay
                                prediction = realtime_replay(adapter.decoder, audio, self.cancel_event.is_set)
                            elif run['options']['mode'] == 'live_replay':
                                prediction = replay(adapter, audio, dataset['language'],
                                                    run['options']['chunk_seconds'], self.cancel_event.is_set)
                            else:
                                prediction = adapter.transcribe(audio, dataset["language"])
                            elapsed = time.perf_counter() - started
                            row['wall_s'] = elapsed
                            row['first_after_load'] = not any(r.get('load_session') == len(model['load_sessions'])
                                                            for r in model['samples'])
                            row['load_session'] = len(model['load_sessions'])
                            if 'inference_s' in prediction:
                                elapsed = prediction['inference_s']
                            row.update(status="ok", reference=text, hypothesis=prediction["text"],
                                       segments=prediction.get("segments", []), elapsed_s=elapsed,
                                       detected_language=prediction.get("detected_language"),
                                       rtf=elapsed / sample["duration_s"], **score(text, prediction["text"]))
                            if 'chunks' in prediction:
                                row.update(chunks=prediction['chunks'], replay_metrics=prediction['replay_metrics'])
                            if 'queue_log' in prediction:
                                row['queue_log'] = prediction['queue_log']
                        except InterruptedError:
                            if self.cancel_event.is_set():
                                break
                            raise
                        except Exception as exc:
                            row.update(status="error", error=str(exc))
                        with self.lock:
                            model["samples"].append(row)
                            run["completed_tasks"] += 1
                            self._save(run)
                    with self.lock:
                        model["status"] = "cancelled" if self.cancel_event.is_set() else "completed"
                except Exception as exc:
                    with self.lock:
                        model.update(status="error", error=str(exc))
                        done = {r["id"] for r in model["samples"]}
                        for sample in dataset["samples"]:
                            if sample["id"] not in done:
                                model["samples"].append({"id": sample["id"], "status": "error",
                                                         "duration_s": sample["duration_s"], "error": str(exc)})
                                run["completed_tasks"] += 1
                finally:
                    if adapter is not None:
                        try:
                            adapter.close()
                        except Exception:
                            pass
                    with self.lock:
                        self._save(run)
            with self.lock:
                cancelled = self.cancel_event.is_set()
                for model in run["models"]:
                    if model["status"] == "queued":
                        model["status"] = "cancelled"
                errors = any(m["summary"]["failed"] or m["status"] == "error" for m in run["models"])
                interrupted = cancelled and run['options']['mode'] in ('experiment2', 'experiment3')
                run.update(status=("interrupted" if interrupted else "cancelled") if cancelled else ("completed_with_errors" if errors else "completed"),
                           message="Cancelled" if cancelled else "Completed", finished_at=utc_now())
                self._save(run)
        except Exception as exc:
            with self.lock:
                run.update(status="error", message=str(exc), finished_at=utc_now())
                self._save(run)


def export_csv(run):
    out = io.StringIO(newline="")
    fields = ["model", "sample_id", "status", "wer", "cer", "character_errors", "reference_characters", "substitutions", "deletions", "insertions",
              "mode", "chunk_seconds", "chunk_p95_s", "lag_p95_s", "first_text_s",
              "wall_s", "first_after_load", "load_session", "first_text_from_vad_s",
              "finalization_from_eof_s", "finalization_from_vad_s", "max_queue_s",
              "reference_words", "elapsed_s", "duration_s", "reference", "hypothesis", "error"]
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    def safe(value):
        return "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
    for model in run["models"]:
        for row in model["samples"]:
            value = {key: safe(row.get(key, "")) for key in fields}
            value.update(model=safe(model["config"]["label"]), sample_id=row["id"])
            value.update(mode=run.get('options', {}).get('mode', 'final'),
                         chunk_seconds=run.get('options', {}).get('chunk_seconds', ''))
            for key in ('chunk_p95_s', 'lag_p95_s', 'first_text_s', 'first_text_from_vad_s',
                        'finalization_from_eof_s', 'finalization_from_vad_s', 'max_queue_s'):
                value[key] = row.get('replay_metrics', {}).get(key, '')
            writer.writerow(value)
    return out.getvalue().encode("utf-8-sig")


def export_summary_csv(run):
    out = io.StringIO(newline='')
    fields = ['model', 'backend', 'language', 'mode', 'status', 'completed', 'failed',
              'wer', 'cer', 'inference_s', 'rtf', 'load_s', 'common_sample_count',
              'common_wer', 'common_cer', 'chunk_p95_s', 'lag_p95_s', 'first_text_p95_s', 'error']
    fields += list(timing_summary([]))
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for model in run['models']:
        row = {k: model['summary'].get(k, '') for k in fields}
        row.update(model=model['config']['label'], backend=model['config']['backend'],
                   language=run['dataset']['language'], mode=run.get('options', {}).get('mode', 'final'),
                   status=model['status'], load_s=model.get('load_s'),
                   common_sample_count=run['common_sample_count'],
                   common_wer=model['common_summary']['wer'], common_cer=model['common_summary'].get('cer'),
                   error=model.get('error', ''))
        writer.writerow({k: "'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for k,v in row.items()})
    return out.getvalue().encode('utf-8-sig')
