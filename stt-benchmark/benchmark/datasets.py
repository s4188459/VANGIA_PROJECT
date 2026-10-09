import hashlib
import io
import json
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .scoring import normalize
from .audio import AUDIO_EXTENSIONS, PREPROCESSING, SAMPLE_RATE, canonical_audio

MAX_UPLOAD = 512 * 1024 * 1024
MAX_EXPANDED = 1024 * 1024 * 1024
MAX_AUDIO = 128 * 1024 * 1024
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_json(path):
    return Path(path).read_text(encoding="utf-8")


def import_zip(archive, destination, name, language):
    if language not in ("en", "vi"):
        raise ValueError("Chọn ngôn ngữ en hoặc vi cho mỗi dataset.")
    destination = Path(destination)
    dataset_id = uuid.uuid4().hex
    folder = destination / dataset_id
    audio_entries, reference_entries, seen = {}, {}, set()
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        if len(infos) > 2500 or sum(x.file_size for x in infos) > MAX_EXPANDED:
            raise ValueError("ZIP quá lớn: tối đa 2.500 mục và 1 GB sau giải nén.")
        for entry in infos:
            path = PurePosixPath(entry.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or any(":" in p for p in path.parts):
                raise ValueError("ZIP chứa đường dẫn không hợp lệ.")
            if entry.is_dir() or "__MACOSX" in path.parts or path.name.startswith("."):
                continue
            suffix = path.suffix.lower()
            if suffix not in AUDIO_EXTENSIONS and suffix != '.txt':
                continue
            sample_id = path.stem
            if not ID_PATTERN.fullmatch(sample_id):
                raise ValueError(f"Tên mẫu không hợp lệ: {path.name}. Dùng chữ, số, _ hoặc -.")
            key = (sample_id.casefold(), 'audio' if suffix in AUDIO_EXTENSIONS else 'text')
            if key in seen:
                raise ValueError(f"Trùng ID/file trong ZIP: {path.name}")
            seen.add(key)
            if (suffix in AUDIO_EXTENSIONS and entry.file_size > MAX_AUDIO) or (suffix == ".txt" and entry.file_size > 100000):
                raise ValueError(f"File quá lớn: {path.name}")
            (audio_entries if suffix in AUDIO_EXTENSIONS else reference_entries)[sample_id] = entry
        missing_text = sorted(audio_entries.keys() - reference_entries.keys())
        missing_audio = sorted(reference_entries.keys() - audio_entries.keys())
        if missing_text or missing_audio:
            raise ValueError(f"Thiếu TXT: {', '.join(missing_text[:12]) or 'không'}. "
                             f"Thiếu audio được hỗ trợ: {', '.join(missing_audio[:12]) or 'không'}. ID phải giống cả chữ hoa/thường.")
        if not audio_entries or len(audio_entries) > 1000:
            raise ValueError("Dataset phải có từ 1 đến 1.000 cặp audio–TXT.")
        samples = []
        digest = hashlib.sha256()
        digest.update(language.encode())
        digest.update(PREPROCESSING.encode())
        try:
            (folder / "audio").mkdir(parents=True)
            (folder / "transcripts").mkdir()
            (folder / "originals").mkdir()
            normalized_size = 0
            for sample_id in sorted(audio_entries):
                original = bundle.read(audio_entries[sample_id])
                raw_reference = bundle.read(reference_entries[sample_id])
                reference = raw_reference.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").strip()
                words = normalize(reference).split()
                if not words or len(words) > 3000:
                    raise ValueError(f"{sample_id}: transcript cần 1–3.000 từ, mã hóa UTF-8.")
                try:
                    audio, duration, original_metadata = canonical_audio(original)
                except Exception as exc:
                    raise ValueError(f"{sample_id}: {exc}") from exc
                normalized_size += len(audio)
                if normalized_size > MAX_EXPANDED:
                    raise ValueError('Tổng audio sau giải mã vượt 1 GB; chia dataset thành các phần nhỏ hơn.')
                audio_hash = hashlib.sha256(audio).hexdigest()
                original_hash = hashlib.sha256(original).hexdigest()
                reference_hash = hashlib.sha256(raw_reference).hexdigest()
                digest.update(json.dumps([sample_id, original_hash, audio_hash, reference_hash]).encode())
                extension = PurePosixPath(audio_entries[sample_id].filename).suffix.lower()
                (folder / 'originals' / f'{sample_id}{extension}').write_bytes(original)
                (folder / "audio" / f"{sample_id}.wav").write_bytes(audio)
                (folder / "transcripts" / f"{sample_id}.txt").write_bytes(reference.encode("utf-8"))
                samples.append({"id": sample_id, "duration_s": duration, "sample_rate": SAMPLE_RATE,
                                "channels": 1, "reference_words": len(words),
                                "original_filename": f'{sample_id}{extension}', 'original_sha256': original_hash,
                                'original_audio': original_metadata,
                                "audio_sha256": audio_hash, "reference_source_sha256": reference_hash,
                                "reference_sha256": hashlib.sha256(reference.encode()).hexdigest()})
            result = {"id": dataset_id, "name": str(name).strip()[:120] or "Dataset",
                      "language": language, "created_at": utc_now(), "sha256": digest.hexdigest(),
                      'audio_preprocessing': {'version':PREPROCESSING, 'sample_rate':SAMPLE_RATE,
                                              'channels':1, 'encoding':'pcm_s16le'},
                      "samples": samples, "duration_s": sum(s["duration_s"] for s in samples)}
            write_json(folder / "manifest.json", result)
            return result
        except Exception:
            # Only the newly generated import directory can be removed.
            if folder.parent.resolve() == destination.resolve() and folder.name == dataset_id:
                shutil.rmtree(folder, ignore_errors=True)
            raise
