"""Local-only benchmark UI. Run with Python 3.10+; no web framework required."""
import argparse
import json
import re
import socket
import tempfile
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from benchmark.adapters import validate_config
from benchmark.datasets import MAX_UPLOAD, import_zip, write_json
from benchmark.runner import Runner, export_csv, export_summary_csv
from benchmark.catalog import catalog, backend_status

ROOT = Path(__file__).resolve().parent
HEX = re.compile(r"[0-9a-f]{32}\Z")


class LocalServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def default_models():
    models = []
    existing = ROOT.parent / "facial-cue-prototype" / "models"
    for name in ("base.en", "small.en"):
        path = existing / ("faster-whisper-" + name.replace(".", "-"))
        if (path / "model.bin").is_file():
            models.append(validate_config({"label": name, "model": str(path), "backend": "faster-whisper"}))
    return models


def make_server(data_root, port=8766):
    data_root = Path(data_root).resolve()
    models_path = data_root / "models.json"
    config_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def reply(self, status, body, content_type="application/json; charset=utf-8", attachment=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            if attachment:
                self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def trusted(self):
            port = self.server.server_port
            allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in allowed:
                raise ValueError("Chỉ hỗ trợ truy cập localhost.")
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + host for host in allowed}:
                raise ValueError("Nguồn yêu cầu không hợp lệ.")

        def json_body(self):
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Cần Content-Type application/json.")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 512 * 1024:
                raise ValueError("JSON quá lớn hoặc rỗng.")
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict):
                raise ValueError("JSON phải là object.")
            return value

        def do_GET(self):
            try:
                self.trusted()
                route = urlsplit(self.path).path
                static = {"/": ("index.html", "text/html; charset=utf-8"),
                          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                          "/style.css": ("style.css", "text/css; charset=utf-8")}
                if route in static:
                    name, mime = static[route]
                    return self.reply(200, (ROOT / "web" / name).read_bytes(), mime)
                if route == "/api/state":
                    datasets = [json.loads(p.read_text(encoding="utf-8")) for p in (data_root / "datasets").glob("*/manifest.json")]
                    runs = []
                    for path in (data_root / "runs").glob("*/run.json"):
                        run = runner.get(path.parent.name)
                        runs.append({"id": run["id"], "created_at": run["created_at"], "status": run["status"],
                                     "dataset_name": run["dataset"]["name"]})
                    with config_lock:
                        models = json.loads(models_path.read_text(encoding="utf-8"))
                    return self.reply(200, {"datasets": sorted(datasets, key=lambda d: d["created_at"], reverse=True),
                                           "models": models, "catalog": catalog(), "backends": backend_status(),
                                           "runs": sorted(runs, key=lambda r: r["created_at"], reverse=True)})
                parts = route.strip("/").split("/")
                if len(parts) in (3, 4) and parts[:2] == ["api", "runs"] and HEX.fullmatch(parts[2]):
                    run = runner.get(parts[2])
                    if len(parts) == 3:
                        return self.reply(200, run)
                    if parts[3] == "csv":
                        return self.reply(200, export_csv(run), "text/csv; charset=utf-8", f"{run['id']}.csv")
                    if parts[3] == 'summary.csv':
                        return self.reply(200, export_summary_csv(run), 'text/csv; charset=utf-8', f"{run['id']}-summary.csv")
                    if parts[3] == "json":
                        return self.reply(200, run, attachment=f"{run['id']}.json")
                if len(parts) == 5 and parts[:2] == ["api", "datasets"] and HEX.fullmatch(parts[2]):
                    manifest = json.loads((data_root / "datasets" / parts[2] / "manifest.json").read_text(encoding="utf-8"))
                    if parts[3] not in {s["id"] for s in manifest["samples"]}:
                        raise ValueError("Không có mẫu này trong dataset.")
                    folder = data_root / "datasets" / parts[2]
                    if parts[4] == "audio":
                        return self.reply(200, (folder / "audio" / f"{parts[3]}.wav").read_bytes(), "audio/wav")
                    if parts[4] == "reference":
                        return self.reply(200, {"text": (folder / "transcripts" / f"{parts[3]}.txt").read_text(encoding="utf-8")})
                self.reply(404, {"error": "Không tìm thấy."})
            except FileNotFoundError:
                self.reply(404, {"error": "Không tìm thấy dữ liệu."})
            except (ValueError, KeyError) as exc:
                self.reply(400, {"error": str(exc)})
            except Exception as exc:
                self.reply(500, {"error": str(exc)})

        def do_POST(self):
            try:
                self.trusted()
                route = urlsplit(self.path)
                if route.path == "/api/datasets":
                    if self.headers.get_content_type() != "application/zip":
                        raise ValueError("Upload file ZIP.")
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= MAX_UPLOAD:
                        raise ValueError("ZIP phải nhỏ hơn hoặc bằng 512 MB.")
                    query = parse_qs(route.query)
                    with tempfile.TemporaryFile() as archive:
                        remaining = size
                        while remaining:
                            chunk = self.rfile.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise ValueError("Upload bị ngắt trước khi hoàn tất.")
                            archive.write(chunk)
                            remaining -= len(chunk)
                        archive.seek(0)
                        dataset = import_zip(archive, data_root / "datasets", query.get("name", ["Dataset"])[0],
                                             query.get("language", ["en"])[0])
                    return self.reply(201, dataset)
                value = self.json_body()
                if route.path == "/api/models":
                    config = validate_config(value)
                    with config_lock:
                        models = json.loads(models_path.read_text(encoding="utf-8"))
                        models = [m for m in models if m["label"] != config["label"]]
                        if len(models) >= 50:
                            raise ValueError("Tối đa 50 cấu hình đã lưu.")
                        models.append(config)
                        write_json(models_path, models)
                    return self.reply(201, config)
                if route.path == "/api/runs":
                    if value.get("references_reviewed") is not True:
                        raise ValueError("Cần xác nhận transcript đã được nghe kiểm tra.")
                    return self.reply(201, runner.start(value.get("dataset_id"), value.get("models"), value.get('options')))
                if route.path == "/api/cancel":
                    runner.cancel(value.get("run_id"))
                    return self.reply(200, {"ok": True})
                self.reply(404, {"error": "Không tìm thấy."})
            except FileNotFoundError:
                self.reply(404, {"error": "Không tìm thấy dữ liệu."})
            except Exception as exc:
                self.reply(400, {"error": str(exc)})

    # Reserve the port before touching persisted run status. A second launch
    # must not mark the first server's running benchmark as interrupted.
    server = LocalServer(("127.0.0.1", port), Handler)
    try:
        data_root.mkdir(parents=True, exist_ok=True)
        if not models_path.exists():
            write_json(models_path, default_models())
        runner = Runner(data_root)
    except Exception:
        server.server_close()
        raise
    server.runner = runner
    return server


def main():
    parser = argparse.ArgumentParser(description="Independent local STT benchmark")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = make_server(args.data_dir, args.port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"STT Bench: {url}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
