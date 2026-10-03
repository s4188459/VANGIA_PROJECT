from __future__ import annotations

from pathlib import Path
from functools import partial
from dataclasses import asdict, is_dataclass

from .audio_devices import discover_default_devices, open_input_stream
from .audio_quality import analyze_level
from .audio_recorder import AudioCaptureWorker, AudioSource
from .session_types import ComponentState, ComponentStatus
from .stereo_audio import StereoAudioWriter
from .transcription import LocalEnglishTranscriber, TranscriptionWorker, speech_has_ended, LIVE_ENDPOINT_PAUSE_S, LIVE_MAX_WINDOW_S
from .transcript_writer import TranscriptStore
from .live_inference_process import ProcessEnglishTranscriber
from .video_recorder import VideoRecorder


MODEL_ROOT = Path(__file__).resolve().parents[1] / "models"
DEFAULT_WHISPER_MODEL = MODEL_ROOT / "faster-whisper-small-en"
FALLBACK_WHISPER_MODEL = MODEL_ROOT / "faster-whisper-base-en"


class SessionOrchestrator:
    def __init__(self, dataset, options, region, clock, *, transcript_callback=lambda _s: None,
                 status_callback=lambda _s: None, audio_level_callback=lambda _source, _metrics: None,
                 transcript_metrics_callback=lambda _metrics: None,
                 video_factory=VideoRecorder, audio_factory=AudioCaptureWorker,
                 stereo_factory=StereoAudioWriter, device_discovery=discover_default_devices,
                 transcriber_factory=ProcessEnglishTranscriber,
                 transcription_worker_factory=TranscriptionWorker) -> None:
        self.dataset, self.options, self.region, self.clock = dataset, options, region, clock
        self._transcript_callback, self._status_callback = transcript_callback, status_callback
        self._audio_level_callback = audio_level_callback
        self._transcript_metrics_callback = transcript_metrics_callback
        self._video_factory, self._audio_factory, self._stereo_factory = video_factory, audio_factory, stereo_factory
        self._device_discovery, self._transcriber_factory = device_discovery, transcriber_factory
        self._transcription_worker_factory = transcription_worker_factory
        self._video = None; self._audio = []; self._stereo = None
        self._transcription = None; self._transcript_writer = None; self._closed = False
        self._component_errors = {}
        self._stop_requested = False
        self._stopped_at = None

    def _transcript_error(self, error) -> None:
        message = f"{error.get('stage', 'worker')}: {error['message']}"
        if "source" in error:
            message += f" ({error['source']}, {error['start_s']:.3f}-{error['end_s']:.3f}s)"
        self.dataset.add_error("transcript", message)
        self._status("transcript", ComponentState.ERROR, message)

    def _transcript_drop(self, chunk, reason) -> None:
        self.dataset.mark_drop(f"transcript.{chunk.source.value}", start_s=chunk.start_s,
                               end_s=chunk.end_s, reason=reason)

    def _status(self, component: str, state: ComponentState, message: str = "") -> None:
        if state is ComponentState.ERROR:
            self._component_errors[component] = message
        elif component in self._component_errors:
            return
        value = ComponentStatus(component, state, message)
        self.dataset.update_component(value); self._status_callback(value)

    def start(self) -> None:
        if self.options.video:
            try:
                self._video = self._video_factory(self.dataset.directory / "video.mp4",
                                                  (self.region.width, self.region.height),
                                                  mapping_callback=self.dataset.record_video_mapping)
                self._video.start(); self._status("video", ComponentState.RECORDING)
            except Exception as exc:
                self._video = None; self.dataset.add_error("video", str(exc))
                self._status("video", ComponentState.UNAVAILABLE, str(exc))

        if self.options.transcript:
            try:
                self._transcript_writer = TranscriptStore(self.dataset.directory / "transcript.jsonl")
                model = DEFAULT_WHISPER_MODEL if DEFAULT_WHISPER_MODEL.is_dir() else FALLBACK_WHISPER_MODEL
                transcriber = self._transcriber_factory(model)
                self.dataset.set_transcription_metadata({"live": {
                    **getattr(transcriber, "configuration", {"model": model.name}),
                    "window_s": 1.2, "max_window_s": LIVE_MAX_WINDOW_S, "endpoint_pause_s": LIVE_ENDPOINT_PAUSE_S, "overlap_s": .75, "queue_size": 4096,
                }})
                def publish(segment):
                    if self._stop_requested: return
                    self._transcript_writer.append_live(segment); self._transcript_callback(segment)
                self._transcription = self._transcription_worker_factory(
                    transcriber,
                    publish,
                    window_s=1.2,
                    max_window_s=LIVE_MAX_WINDOW_S,
                    speech_boundary=partial(getattr(transcriber, "speech_boundary", speech_has_ended), pause_s=LIVE_ENDPOINT_PAUSE_S),
                    overlap_s=0.75,
                    clock=self.clock.elapsed_s,
                    metrics_callback=self._transcript_metrics_callback,
                    error_callback=self._transcript_error,
                    drop_callback=self._transcript_drop,
                )
                self._transcription.start(); self._status("transcript", ComponentState.RECORDING)
            except Exception as exc:
                if self._transcription is not None:
                    self._transcription.request_stop(); self._transcription.stop()
                elif "transcriber" in locals() and hasattr(transcriber, "close"):
                    transcriber.close()
                if self._transcript_writer: self._transcript_writer.close()
                self._transcript_writer = None; self._transcription = None
                self.dataset.add_error("transcript", str(exc))
                self._status("transcript", ComponentState.UNAVAILABLE, str(exc))

        if self.options.system_audio or self.options.microphone:
            def level(source, samples):
                self._audio_level_callback(source, analyze_level(samples))
            self._stereo = self._stereo_factory(
                self.dataset.directory / "audio.wav",
                interval_callback=self.dataset.record_audio_interval,
                level_callback=level,
            )
            self._stereo.start()
            self.dataset.set_audio_metadata({
                "file": "audio.wav", "sample_rate": 48000,
                "channels": {"left": "microphone/You", "right": "system_audio/Student"},
            })
            try: devices = self._device_discovery()
            except Exception as exc:
                devices = {}; self.dataset.add_error("audio", str(exc))
            self.dataset.set_audio_metadata({
                "file": "audio.wav", "sample_rate": 48000,
                "channels": {"left": "microphone/You", "right": "system_audio/Student"},
                "packet_timing": "sample_count_with_pause_reanchor",
                "devices": {
                    source.value: {key: getattr(device, key, None)
                                   for key in ("name", "sample_rate", "channels")}
                    for source, device in devices.items()
                    if (source is AudioSource.SYSTEM_AUDIO and self.options.system_audio)
                    or (source is AudioSource.MICROPHONE and self.options.microphone)
                },
            })
            for source, enabled in ((AudioSource.SYSTEM_AUDIO, self.options.system_audio),
                                    (AudioSource.MICROPHONE, self.options.microphone)):
                if not enabled: continue
                device = devices.get(source)
                if device is None:
                    self._status(source.value, ComponentState.UNAVAILABLE, "Default audio device unavailable")
                    continue
                def accept(chunk):
                    if self._stop_requested: return
                    if not self._stereo.submit(chunk):
                        self.dataset.mark_drop(f"audio.{chunk.source.value}", start_s=chunk.start_s,
                                               end_s=chunk.end_s, reason="writer_rejected")
                    if self._transcription and not self._transcription.submit(chunk):
                        self._transcript_drop(chunk, "worker_not_accepting")
                def audio_status(component, _state, message):
                    self.dataset.add_error(component, message)
                    self._status(component, ComponentState.ERROR, message)
                worker = self._audio_factory(source, device, accept, audio_status, self.clock,
                                             stream_factory=open_input_stream)
                try:
                    worker.start(); self._audio.append(worker)
                    self._status(source.value, ComponentState.RECORDING, device.name)
                except Exception as exc:
                    self.dataset.add_error(source.value, str(exc))
                    self._status(source.value, ComponentState.UNAVAILABLE, str(exc))

    def submit_video(self, frame) -> int | None:
        if self._stop_requested: return None
        return self._video.submit(frame) if self._video else None

    def pause(self) -> None:
        now = self.clock.elapsed_s()
        if self._video: self._video.pause(now)
        for worker in self._audio: worker.pause(now)
        if self._stereo: self._stereo.pause(now)

    def resume(self) -> None:
        now = self.clock.elapsed_s()
        if self._video: self._video.resume(now)
        if self._stereo: self._stereo.resume(now)
        for worker in self._audio: worker.resume(now)

    def request_stop(self) -> None:
        if self._stop_requested: return
        self._stop_requested = True
        self._stopped_at = self.clock.elapsed_s()
        for worker in self._audio:
            if hasattr(worker, "request_stop"): worker.request_stop()
        if self._transcription and hasattr(self._transcription, "request_stop"):
            self._transcription.request_stop()

    def stop(self) -> None:
        if self._closed: return
        self.request_stop()
        self._closed = True; errors = []
        stopped_at = self._stopped_at
        operations = [(worker.source.value if hasattr(worker, "source") else "audio_capture", worker.stop)
                      for worker in self._audio]
        if self._stereo: operations.append(("audio", lambda: self._stereo.stop(stopped_at)))
        if self._video: operations.append(("video", lambda: self._video.stop(timestamp_s=stopped_at)))
        if self._transcription: operations.append(("transcript", self._transcription.stop))
        if self._transcript_writer: operations.append(("transcript_store", self._transcript_writer.close))
        for component, operation in operations:
            try:
                stats = operation()
                if stats is not None:
                    if isinstance(stats, dict):
                        stats = {key: asdict(value) if is_dataclass(value) else value for key, value in stats.items()}
                    self.dataset.record_media_stats(component, stats)
                    failure = stats.get("failure") if isinstance(stats, dict) else getattr(stats, "failure", None)
                    if failure: raise RuntimeError(failure)
                self._status(component, ComponentState.STOPPED)
            except Exception as exc:
                errors.append(str(exc))
                try:
                    self.dataset.add_error(component, str(exc))
                    self._status(component, ComponentState.ERROR, str(exc))
                except Exception: pass
        errors.extend(f"{name}: {message}" for name, message in self._component_errors.items())
        self.dataset.close(status="incomplete" if errors else "closed")
        return "; ".join(errors) or None
