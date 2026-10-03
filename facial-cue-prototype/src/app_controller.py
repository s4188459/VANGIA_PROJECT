from __future__ import annotations

from pathlib import Path
from typing import Callable
import json

from .capture_types import AppState, CaptureRegion
from .meeting_tracker import MeetingTracker, TrackerEvent, TrackerEventKind
from .region_selector import select_screen_region
from .recording_session import RecordingSession
from .session_recorder import next_session_name
from .dataset_session import DatasetSession
from .session_clock import SessionClock
from .session_orchestrator import SessionOrchestrator
from .session_types import SessionOptions
from .final_transcription import FinalTranscriptionJob, resolve_final_model, update_final_status
from .stereo_audio import AudioInterval


class AppController:
    def __init__(
        self,
        view,
        *,
        selector: Callable[[], CaptureRegion | None] | None = None,
        tracker_factory: Callable[..., object] = MeetingTracker,
        recorder_factory: Callable[[Path], object] | None = None,
        next_name_func: Callable[[Path], str] = next_session_name,
        orchestrator_factory=SessionOrchestrator,
        final_job_factory=FinalTranscriptionJob,
    ) -> None:
        self.view = view
        self._selector = selector or (lambda: select_screen_region(view.root))
        self._tracker_factory = tracker_factory
        self._recorder_factory = recorder_factory
        self._orchestrator_factory = orchestrator_factory
        self._final_job_factory = final_job_factory
        self._next_name = next_name_func
        self.state = AppState.NO_REGION
        self.region: CaptureRegion | None = None
        self.save_folder: Path | None = None
        self._tracker = None
        self._recorder = None
        self._orchestrator = None
        self._session_clock = None
        self._options = SessionOptions(consent_confirmed=False)
        self._generation = 0
        self._worker_failed = False
        self._overlay_active = False
        self._closed = False
        self._last_session_directory: Path | None = None
        self._final_job = None
        self._quit_after_stop = False
        self._set_state(AppState.NO_REGION, "No region selected")

    def _set_state(self, state: AppState, status: str) -> None:
        self.state = state
        self.view.render(state, status)

    def _close_recorder(self, *, remove_if_empty: bool = False) -> str | None:
        recorder = self._recorder
        self._recorder = None
        if recorder is None:
            return None
        try:
            recorder.close(remove_if_empty=remove_if_empty)
        except Exception as exc:
            return str(exc)
        return None

    def _stop_worker(self, *, remove_empty_recording: bool = False, on_complete=None) -> str | None:
        tracker = self._tracker
        recorder = self._recorder
        had_session = tracker is not None or recorder is not None or self._orchestrator is not None
        orchestrator = self._orchestrator
        if self._session_clock is not None and hasattr(self._session_clock, "stop"):
            self._session_clock.stop()
        if orchestrator is not None and hasattr(orchestrator, "request_stop"):
            orchestrator.request_stop()
        if tracker is not None and hasattr(tracker, "request_stop"):
            tracker.request_stop()
        # Hide immediately. File closure never calls Tk.
        self._hide_overlay()
        if had_session and hasattr(self.view, "hide_transcript_panel"):
            self.view.hide_transcript_panel()
        if had_session:
            self.view.clear_features()

        def cleanup():
            errors = []
            if tracker is not None:
                try: tracker.stop()
                except Exception as exc: errors.append(str(exc))
            self._tracker = None
            self._generation += 1
            self._orchestrator = None
            if orchestrator is not None:
                try:
                    error = orchestrator.stop()
                    if error: errors.append(str(error))
                except Exception as exc: errors.append(str(exc))
                finally: self._recorder = None
            else:
                error = self._close_recorder(remove_if_empty=remove_empty_recording)
                if error: errors.append(error)
            if recorder is not None and hasattr(recorder, "directory") and recorder.directory.is_dir():
                self._last_session_directory = recorder.directory
            return "; ".join(errors) or None

        if on_complete is not None and hasattr(self.view, "run_background"):
            self.view.run_background(cleanup, on_complete)
            return None
        result = cleanup()
        if on_complete is not None: on_complete(result)
        return result

    def _hide_overlay(self) -> None:
        if not self._overlay_active:
            return
        self._overlay_active = False
        self.view.hide_overlay()

    def choose_save_folder(self) -> None:
        if self.state in {AppState.RUNNING, AppState.PAUSED, AppState.SHUTTING_DOWN, AppState.FINALIZING, AppState.STOPPING}:
            return
        selected = self.view.ask_save_folder()
        if not selected:
            return
        folder = Path(selected)
        try:
            name = self._next_name(folder)
        except Exception as exc:
            self._set_state(self.state, str(exc))
            return
        self.save_folder = folder
        self.view.show_save_folder(folder, name)
        if self.region is not None:
            self._set_state(AppState.READY, "Ready")

    def _schedule_session(self, callback, generation):
        def publish():
            if generation == self._generation and self.state not in {AppState.STOPPING, AppState.SHUTTING_DOWN}:
                callback()
        self.view.schedule(publish)

    def _start_worker(self, *, paused: bool = False) -> None:
        if self.region is None or self.save_folder is None:
            return
        self._generation += 1
        generation = self._generation
        self._worker_failed = False
        event_callback = lambda event: self.handle_tracker_event(event, generation)
        feature_callback = lambda frame: self._publish_feature(frame, generation)
        action_event_callback = lambda event: self._publish_action_event(event, generation)

        try:
            options = self.view.get_session_options() if hasattr(self.view, "get_session_options") else SessionOptions(consent_confirmed=True)
            error = options.validation_error()
            if error:
                self._set_state(AppState.READY, f"Ready - {error}")
                return
            self._options = options
            self._session_clock = SessionClock(); self._session_clock.start()
            if self._recorder_factory is None:
                self._recorder = DatasetSession.create(self.save_folder, options, self.region, self._session_clock)
            else:
                self._recorder = self._recorder_factory(self.save_folder)
        except Exception as exc:
            self._set_state(AppState.READY, f"Ready - {exc}")
            return

        try:
            self.view.show_save_folder(self.save_folder, self._recorder.path.name)
            optional = options.video or options.system_audio or options.microphone or options.transcript
            if optional:
                self._orchestrator = self._orchestrator_factory(
                    self._recorder, options, self.region, self._session_clock,
                    transcript_callback=lambda segment: self._schedule_session(lambda: self.view.publish_transcript(segment), generation),
                    status_callback=lambda status: self._schedule_session(lambda: self.view.publish_component_status(status), generation),
                    transcript_metrics_callback=lambda metrics: self._schedule_session(
                        lambda: self.view.publish_transcript_metrics(metrics), generation
                    ) if hasattr(self.view, "publish_transcript_metrics") else None,
                    audio_level_callback=lambda source, metrics: self._schedule_session(
                        lambda: self.view.publish_audio_level(source, metrics), generation
                    ) if hasattr(self.view, "publish_audio_level") else None,
                )
                self._orchestrator.start()
                if options.transcript:
                    self.view.show_transcript_panel(self.region)
            self._overlay_active = True
            self.view.show_overlay(self.region)
            tracker_args = (self.region, event_callback, self.view.publish_overlay, feature_callback, action_event_callback)
            try:
                self._tracker = self._tracker_factory(
                    *tracker_args,
                    frame_callback=self._orchestrator.submit_video if self._orchestrator and options.video else None,
                    session_clock=self._session_clock,
                    timing_recorder=getattr(self._recorder, "landmark_timing", None),
                )
            except TypeError as exc:
                if "unexpected keyword" not in str(exc): raise
                self._tracker = self._tracker_factory(*tracker_args)
            self._tracker.start()
        except Exception as exc:
            cleanup_error = self._stop_worker(remove_empty_recording=True)
            detail = f"{exc}; cleanup: {cleanup_error}" if cleanup_error else str(exc)
            self._set_state(AppState.READY, f"Ready - {detail}")
            return

        if paused:
            self._set_state(AppState.PAUSED, "Paused")
            self._tracker.pause()
            self.view.pause_overlay()
        else:
            self._set_state(AppState.RUNNING, "Running - Face not detected")

    def _publish_feature(self, frame, generation: int) -> None:
        if generation != self._generation or self.state is AppState.STOPPING:
            return
        recorder = self._recorder
        if recorder is None:
            return
        recorder.write_feature(frame)
        self.view.publish_features(
            frame, recorder.raw_row_count, recorder.raw_path.name
        )

    def _publish_action_event(self, event, generation: int) -> None:
        if generation != self._generation:
            return
        recorder = self._recorder
        if recorder is not None:
            recorder.write_event(event)

    def select_region(self) -> None:
        if self.state in {AppState.SHUTTING_DOWN, AppState.FINALIZING, AppState.STOPPING}:
            return
        previous_region = self.region
        self._stop_worker()
        try:
            selected = self._selector()
        except Exception as exc:
            self.region = previous_region
            fallback = AppState.READY if self.region is not None else AppState.NO_REGION
            self._set_state(fallback, f"Ready - {exc}" if self.region else str(exc))
            return

        if selected is None:
            self.region = previous_region
            fallback = AppState.READY if self.region is not None else AppState.NO_REGION
            self._set_state(fallback, "Selection cancelled")
            return
        self.region = selected
        self._set_state(AppState.READY, "Ready")

    def start(self) -> None:
        if self.state is not AppState.READY or self.region is None or self._final_job is not None:
            return
        if self.save_folder is None:
            self._set_state(AppState.READY, "Ready - Choose a save folder")
            return
        if hasattr(self.view, "get_session_options"):
            error = self.view.get_session_options().validation_error()
            if error:
                self._set_state(AppState.READY, f"Ready - {error}")
                return
        self._start_worker()

    def stop(self) -> None:
        if self.state not in {AppState.RUNNING, AppState.PAUSED}:
            return
        self._set_state(AppState.STOPPING, "Stopped - saving files")
        self._stop_worker(on_complete=self._stop_completed)

    def _stop_completed(self, close_error) -> None:
        status = "Ready" if close_error is None else f"Ready - {close_error}"
        self._set_state(AppState.READY, status)
        if self._quit_after_stop:
            self.shutdown()
            return
        if hasattr(self.view, "set_final_available"):
            available = bool(self._last_session_directory and
                             (self._last_session_directory / "audio.wav").is_file() and
                             resolve_final_model() is not None)
            self.view.set_final_available(available)

    def generate_final_transcript(self) -> None:
        folder = self._last_session_directory
        if folder is None or self._final_job is not None or self.state is not AppState.READY: return
        try:
            metadata = json.loads((folder / "session.json").read_text("utf-8"))
            intervals = tuple(AudioInterval(**value) for value in metadata["audio"]["intervals"])
            if not intervals: raise RuntimeError("No recorded audio intervals")
            selected_model = resolve_final_model()
            update_final_status(folder / "session.json", "running", "", selected_model.name if selected_model else None)
            def progress(value):
                if not self._closed and hasattr(self.view, "publish_final_progress"):
                    self.view.schedule(lambda: self.view.publish_final_progress(value))
            def complete(ok, message):
                try:
                    update_final_status(folder / "session.json", "completed" if ok else "failed", message,
                                        selected_model.name if selected_model else None)
                except Exception as metadata_error:
                    message = f"{message}; session metadata: {metadata_error}"
                def publish():
                    if self._closed:
                        return
                    self._final_job = None
                    self._set_state(AppState.READY, message)
                    if ok and self.region is not None and hasattr(self.view, "show_final_transcript"):
                        rows = [json.loads(line) for line in (folder / "transcript.jsonl").read_text("utf-8").splitlines()]
                        final_rows = [row for row in rows if row.get("phase") == "final"]
                        self.view.show_transcript_panel(self.region)
                        self.view.show_final_transcript(final_rows)
                if not self._closed:
                    self.view.schedule(publish)
            self._final_job = self._final_job_factory(
                folder / "audio.wav", intervals, folder / "transcript.jsonl",
                model_path=selected_model, progress_callback=progress, completion_callback=complete,
            )
            self._set_state(AppState.FINALIZING, "Generating final transcript")
            self._final_job.start()
        except Exception as exc:
            self._final_job = None; self._set_state(AppState.READY, f"Ready - {exc}")

    def toggle_pause(self) -> None:
        if self._tracker is None:
            return
        if self.state is AppState.RUNNING:
            self._tracker.pause()
            if self._orchestrator is not None: self._orchestrator.pause()
            self.view.pause_overlay()
            self._set_state(AppState.PAUSED, "Paused")
        elif self.state is AppState.PAUSED:
            self._tracker.resume()
            if self._orchestrator is not None: self._orchestrator.resume()
            self._set_state(AppState.RUNNING, "Running - Face not detected")

    def handle_tracker_event(
        self,
        event: TrackerEvent,
        generation: int | None = None,
    ) -> None:
        event_generation = self._generation if generation is None else generation
        self.view.schedule(lambda: self._apply_tracker_event(event, event_generation))

    def _apply_tracker_event(self, event: TrackerEvent, generation: int) -> None:
        if generation != self._generation or self.state in {AppState.SHUTTING_DOWN, AppState.STOPPING}:
            return
        if event.kind is TrackerEventKind.FACE_STATUS and self.state is AppState.RUNNING:
            self._set_state(AppState.RUNNING, f"Running - {event.message}")
        elif event.kind is TrackerEventKind.PAUSED:
            self._set_state(AppState.PAUSED, "Paused")
        elif event.kind is TrackerEventKind.RESUMED:
            self._set_state(AppState.RUNNING, "Running - Face not detected")
        elif event.kind is TrackerEventKind.RESELECT:
            self.select_region()
        elif event.kind is TrackerEventKind.ERROR:
            self._worker_failed = True
            row_count = self._recorder.raw_row_count if self._recorder is not None else 0
            self._stop_worker(remove_empty_recording=row_count == 0)
            self._set_state(AppState.READY, f"Ready - {event.message}")
        elif event.kind is TrackerEventKind.STOPPED:
            self._tracker = None
            self._stop_worker()
            if self._worker_failed:
                return
            if self.region is not None:
                self._set_state(AppState.READY, "Ready")
            else:
                self._set_state(AppState.NO_REGION, "No region selected")
        elif event.kind is TrackerEventKind.QUIT:
            self.shutdown()

    def shutdown(self) -> None:
        if self.state is AppState.STOPPING:
            self._quit_after_stop = True
            return
        if self._closed:
            return
        self._closed = True
        self._set_state(AppState.SHUTTING_DOWN, "Closing")
        self._stop_worker()
        if self._final_job is not None:
            self._final_job.cancel(); self._final_job.join(2.0); self._final_job = None
        self.view.close()
