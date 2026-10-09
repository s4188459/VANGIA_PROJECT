import copy
import csv
import hashlib
import importlib.metadata
import io
import json
import platform
import threading
import time
import uuid
from pathlib import Path

from .adapters import ADAPTERS, validate_config
from .datasets import utc_now, write_json
from .scoring import NORMALIZATION, score
from .catalog import supported_languages
from .replay import validate_options, replay, percentile


def aggregate(rows):
    ok = [r for r in rows if r["status"] == "ok"]
    words = sum(r["reference_words"] for r in ok)
    duration = sum(r["duration_s"] for r in ok)
    elapsed = sum(r["elapsed_s"] for r in ok)
    chars = sum(r.get('reference_characters', 0) for r in ok)
    chunks = [c for r in ok for c in r.get('chunks', [])]
    return {"completed": len(ok), "failed": sum(r["status"] == "error" for r in rows),
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
                run.update(status="interrupted", message="Tiến trình đã dừng trước khi hoàn tất.")
                for model in run["models"]:
                    if model["status"] in ("running", "loading", "queued"):
                        model["status"] = "interrupted"
                summarize(run)
                write_json(path, run)

    def start(self, dataset_id, configs, options=None):
        options = validate_options(options)
        if not isinstance(dataset_id, str) or len(dataset_id) != 32 or any(c not in "0123456789abcdef" for c in dataset_id):
            raise ValueError("Dataset ID không hợp lệ.")
        if not isinstance(configs, list) or not 1 <= len(configs) <= 50:
            raise ValueError("Chọn từ 1 đến 50 cấu hình model.")
        configs = [validate_config(c) for c in configs]
        if len({c["label"] for c in configs}) != len(configs):
            raise ValueError("Tên các cấu hình trong một lần chạy phải khác nhau.")
        dataset = json.loads((self.root / "datasets" / dataset_id / "manifest.json").read_text(encoding="utf-8"))
        for config in configs:
            if dataset['language'] not in supported_languages(config):
                raise ValueError(f"{config['label']} không hỗ trợ dataset {dataset['language']}; chọn model đa ngôn ngữ hoặc chuyên ngôn ngữ này.")
            if config['backend'] in ('elevenlabs', 'google-chirp') and not options['allow_cloud']:
                raise ValueError('Chọn cho phép gửi audio lên dịch vụ cloud trước khi chạy model API.')
        if dataset["language"] != "en":
            for config in configs:
                name = config["model"].replace("\\", "/").rstrip("/").split("/")[-1]
                if name.endswith((".en", "-en")):
                    raise ValueError("Dataset tiếng Việt cần model đa ngôn ngữ, không dùng model .en.")
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError("Đang có một lần chạy. Chờ hoàn tất hoặc dừng trước khi chạy tiếp.")
            run_id = uuid.uuid4().hex
            versions = {}
            for package in ("faster-whisper", "ctranslate2", "av", "torch", "transformers", "qwen-asr", "nemo_toolkit", "funasr", "vosk", "google-cloud-speech", "requests"):
                try:
                    versions[package] = importlib.metadata.version(package)
                except importlib.metadata.PackageNotFoundError:
                    versions[package] = "not installed"
            run = {"id": run_id, "created_at": utc_now(), "status": "running", "message": "Đang chuẩn bị",
                   'options': options, 'cer_normalization': 'same-as-wer-without-whitespace-v1',
                   "dataset": dataset, "normalization": NORMALIZATION,
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

    def _save(self, run):
        summarize(run)
        write_json(self.root / "runs" / run["id"] / "run.json", run)

    def get(self, run_id):
        if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
            raise ValueError("Run ID không hợp lệ.")
        with self.lock:
            if self.active and self.active["id"] == run_id:
                return copy.deepcopy(self.active)
            return json.loads((self.root / "runs" / run_id / "run.json").read_text(encoding="utf-8"))

    def cancel(self, run_id):
        with self.lock:
            if not self.active or self.active["id"] != run_id or not self.thread.is_alive():
                raise ValueError("Lần chạy này không còn hoạt động.")
            self.cancel_event.set()
            self.active.update(status="cancelling", message="Sẽ dừng sau tác vụ nạp model hoặc mẫu hiện tại.")
            self._save(self.active)

    def _execute(self, run):
        dataset = run["dataset"]
        folder = self.root / "datasets" / dataset["id"]
        try:
            for model in run["models"]:
                if self.cancel_event.is_set():
                    break
                adapter = None
                try:
                    with self.lock:
                        model["status"] = "loading"
                        run["message"] = f"Đang nạp {model['config']['label']}"
                        self._save(run)
                    config = model['config']
                    if config.get('python_executable'):
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
                        model["status"] = "running"
                    for sample in dataset["samples"]:
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
                                raise ValueError("Dữ liệu đã thay đổi sau khi import; hãy import phiên bản mới.")
                            started = time.perf_counter()
                            if run['options']['mode'] == 'live_replay':
                                prediction = replay(adapter, audio, dataset['language'],
                                                    run['options']['chunk_seconds'], self.cancel_event.is_set)
                            else:
                                prediction = adapter.transcribe(audio, dataset["language"])
                            elapsed = time.perf_counter() - started
                            row.update(status="ok", reference=text, hypothesis=prediction["text"],
                                       segments=prediction.get("segments", []), elapsed_s=elapsed,
                                       detected_language=prediction.get("detected_language"),
                                       rtf=elapsed / sample["duration_s"], **score(text, prediction["text"]))
                            if 'chunks' in prediction:
                                row.update(chunks=prediction['chunks'], replay_metrics=prediction['replay_metrics'])
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
                run.update(status="cancelled" if cancelled else ("completed_with_errors" if errors else "completed"),
                           message="Đã dừng" if cancelled else "Đã hoàn tất", finished_at=utc_now())
                self._save(run)
        except Exception as exc:
            with self.lock:
                run.update(status="error", message=str(exc), finished_at=utc_now())
                self._save(run)


def export_csv(run):
    out = io.StringIO(newline="")
    fields = ["model", "sample_id", "status", "wer", "cer", "character_errors", "reference_characters", "substitutions", "deletions", "insertions",
              "mode", "chunk_seconds", "chunk_p95_s", "lag_p95_s", "first_text_s",
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
            for key in ('chunk_p95_s', 'lag_p95_s', 'first_text_s'):
                value[key] = row.get('replay_metrics', {}).get(key, '')
            writer.writerow(value)
    return out.getvalue().encode("utf-8-sig")


def export_summary_csv(run):
    out = io.StringIO(newline='')
    fields = ['model', 'backend', 'language', 'mode', 'status', 'completed', 'failed',
              'wer', 'cer', 'inference_s', 'rtf', 'load_s', 'common_sample_count',
              'common_wer', 'common_cer', 'chunk_p95_s', 'lag_p95_s', 'first_text_p95_s', 'error']
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
