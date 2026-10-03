from __future__ import annotations

import queue
import time
from pathlib import Path
from threading import Lock
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Callable

from .app_utils import PreviewAction
from .audio_recorder import AudioSource
from .capture_types import AppState
from .feature_data import FeatureFrame, LatestFeatureFrame, gaze_label
from .overlay_window import LandmarkOverlay
from .session_types import ComponentStatus, SessionOptions
from .transcript_panel import TranscriptPanel
from .windows_overlay import exclude_window_from_capture


def control_shortcut(keysym: str) -> PreviewAction:
    if keysym.lower() == "s":
        return PreviewAction.TOGGLE_PAUSE
    if keysym.lower() == "r":
        return PreviewAction.RESELECT
    if keysym.lower() == "q" or keysym == "Escape":
        return PreviewAction.QUIT
    return PreviewAction.NONE


def _shorten_middle(value: str, limit: int = 40) -> str:
    if len(value) <= limit:
        return value
    side = (limit - 3) // 2
    return f"{value[:side]}...{value[-(limit - 3 - side):]}"


def _score(value: float | None) -> str:
    return "--" if value is None else f"{value:.2f}"


def format_feature_display(
    frame: FeatureFrame,
    row_count: int,
    filename: str,
) -> dict[str, str]:
    head = "--"
    if all(
        value is not None
        for value in (frame.head_yaw_deg, frame.head_pitch_deg, frame.head_roll_deg)
    ):
        head = (
            f"Yaw {frame.head_yaw_deg:.2f} | Pitch {frame.head_pitch_deg:.2f} | "
            f"Roll {frame.head_roll_deg:.2f}"
        )

    gaze = "--"
    if frame.face_visible:
        direction = gaze_label(frame)
        values = {
            "Left": frame.gaze_left,
            "Right": frame.gaze_right,
            "Up": frame.gaze_up,
            "Down": frame.gaze_down,
        }
        present = [value for value in values.values() if value is not None]
        if present:
            gaze = f"{direction} {max(present):.2f}"

    return {
        "recording": _shorten_middle(filename),
        "elapsed": f"{frame.timestamp_s:.2f} s",
        "face": "Visible" if frame.face_visible else "Not detected",
        "head": head,
        "gaze": gaze,
        "blink": _score(frame.blink),
        "brow": _score(frame.brow_raise),
        "mouth": _score(frame.mouth_activity),
        "landmark_latency": "--" if frame.processing_ms is None else f"{frame.processing_ms:.1f} ms",
        "rows": str(row_count),
    }


class TkCallbackQueue:
    def __init__(self, root: tk.Tk, poll_ms: int = 25) -> None:
        self._root = root
        self._poll_ms = poll_ms
        self._callbacks: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        self._active = True
        self._root.after(self._poll_ms, self._drain)

    def schedule(self, callback: Callable[[], None]) -> None:
        if self._active:
            self._callbacks.put(callback)

    def _drain(self) -> None:
        if not self._active:
            return
        deadline = time.perf_counter() + .004
        try:
            for _ in range(32):
                self._callbacks.get_nowait()()
                if time.perf_counter() >= deadline:
                    break
        except queue.Empty:
            pass
        finally:
            if self._active:
                self._root.after(1 if not self._callbacks.empty() else self._poll_ms, self._drain)

    def close(self) -> None:
        self._active = False


class ControlPanel:
    def __init__(
        self,
        root: tk.Tk,
        *,
        exclude_native=exclude_window_from_capture,
        overlay_factory=LandmarkOverlay,
        transcript_factory=TranscriptPanel,
    ) -> None:
        self.root = root
        self._overlay_factory = overlay_factory
        self._transcript_factory = transcript_factory
        self._overlay = None
        self._transcript_panel = None
        self._active = True
        self._capture_exclusion_ready = True
        self._has_folder = False
        self._state = AppState.NO_REGION
        self._status_text = "No region selected"
        self._latest_features = LatestFeatureFrame()
        self._feature_lock = Lock()
        self._latest_row_count = 0
        self._latest_filename = "--"
        self._final_available = False
        self.root.title("Multimodal Dataset Collector")
        self.root.geometry("700x860")
        self.root.minsize(620, 720)
        self.root.resizable(True, True)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self._scheduler = TkCallbackQueue(root)

        container = ttk.Frame(root, padding=16)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure((0, 1), weight=1)

        ttk.Label(
            container,
            text="Facial Feature Recording",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self._status = tk.StringVar(value="No region selected")
        ttk.Label(
            container,
            textvariable=self._status,
            wraplength=580,
            font=("Segoe UI", 11),
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self._folder_text = tk.StringVar(value="Save folder: Not selected")
        ttk.Label(
            container,
            textvariable=self._folder_text,
            font=("Segoe UI", 10),
        ).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )

        self.select_button = ttk.Button(
            container, text="Select Region", padding=(8, 7),
        )
        self.select_button.grid(row=3, column=0, sticky="ew", padx=(0, 5), pady=4)
        self.folder_button = ttk.Button(
            container, text="Choose Save Folder", padding=(8, 7),
        )
        self.folder_button.grid(row=3, column=1, sticky="ew", padx=(5, 0), pady=4)
        self.start_button = ttk.Button(container, text="Start", padding=(8, 7))
        self.start_button.grid(row=4, column=0, sticky="ew", padx=(0, 5), pady=4)
        self.pause_button = ttk.Button(container, text="Pause", padding=(8, 7))
        self.pause_button.grid(row=4, column=1, sticky="ew", padx=(5, 0), pady=4)
        self.stop_button = ttk.Button(container, text="Stop", padding=(8, 7))
        self.stop_button.grid(row=5, column=0, sticky="ew", padx=(0, 5), pady=4)
        self.quit_button = ttk.Button(container, text="Quit", padding=(8, 7))
        self.quit_button.grid(row=5, column=1, sticky="ew", padx=(5, 0), pady=4)

        ttk.Label(container, text="Data collection", font=("Segoe UI", 12, "bold")).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(12, 5)
        )
        self._video_var = tk.StringVar(value="0")
        self._system_audio_var = tk.StringVar(value="0")
        self._microphone_var = tk.StringVar(value="0")
        self._transcript_var = tk.StringVar(value="0")
        self._consent_var = tk.StringVar(value="0")
        self._participant_var = tk.StringVar(value="")
        options = (
            ("Record selected-region video", self._video_var),
            ("Record meeting audio (Student)", self._system_audio_var),
            ("Record microphone (You)", self._microphone_var),
            ("Generate local English transcript", self._transcript_var),
        )
        for row, (text, variable) in enumerate(options, start=7):
            ttk.Checkbutton(container, text=text, variable=variable, onvalue="1", offvalue="0",
                            command=self._options_changed).grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Label(container, text="Participant ID").grid(row=11, column=0, sticky="w", pady=3)
        ttk.Entry(container, textvariable=self._participant_var).grid(row=11, column=1, sticky="ew", pady=3)
        self.consent_check = ttk.Checkbutton(
            container, text="Consent confirmed", variable=self._consent_var,
            onvalue="1", offvalue="0", command=self._options_changed,
        )
        self.consent_check.grid(row=12, column=0, columnspan=2, sticky="w", pady=(4, 6))

        self._audio_values = {
            AudioSource.MICROPHONE: tk.StringVar(value="No signal"),
            AudioSource.SYSTEM_AUDIO: tk.StringVar(value="No signal"),
        }
        ttk.Label(container, text="You audio", font=("Segoe UI", 10, "bold")).grid(row=13, column=0, sticky="w", pady=2)
        ttk.Label(container, textvariable=self._audio_values[AudioSource.MICROPHONE]).grid(row=13, column=1, sticky="w", pady=2)
        ttk.Label(container, text="Student audio", font=("Segoe UI", 10, "bold")).grid(row=14, column=0, sticky="w", pady=2)
        ttk.Label(container, textvariable=self._audio_values[AudioSource.SYSTEM_AUDIO]).grid(row=14, column=1, sticky="w", pady=2)
        self.final_button = ttk.Button(container, text="Generate Final Transcript", padding=(8, 7), state="disabled")
        self.final_button.grid(row=15, column=0, columnspan=2, sticky="ew", pady=4)

        ttk.Separator(container).grid(
            row=16, column=0, columnspan=2, sticky="ew", pady=(10, 8)
        )
        ttk.Label(container, text="Live coefficients", font=("Segoe UI", 12, "bold")).grid(
            row=17, column=0, columnspan=2, sticky="w", pady=(0, 5)
        )

        self._feature_values = {
            name: tk.StringVar(value="--")
            for name in (
                "recording",
                "elapsed",
                "face",
                "head",
                "gaze",
                "blink",
                "brow",
                "mouth",
                "landmark_latency",
                "transcript_lag",
                "rows",
            )
        }
        labels = (
            ("Recording", "recording"),
            ("Elapsed", "elapsed"),
            ("Face", "face"),
            ("Head", "head"),
            ("Gaze", "gaze"),
            ("Blink", "blink"),
            ("Brow", "brow"),
            ("Mouth", "mouth"),
            ("Landmark latency", "landmark_latency"),
            ("Transcript lag", "transcript_lag"),
            ("Rows", "rows"),
        )
        for offset, (label, name) in enumerate(labels, start=18):
            ttk.Label(
                container,
                text=label,
                width=11,
                font=("Segoe UI", 11, "bold"),
            ).grid(
                row=offset, column=0, sticky="w", pady=4
            )
            ttk.Label(
                container,
                textvariable=self._feature_values[name],
                anchor="w",
                font=("Segoe UI", 11),
            ).grid(row=offset, column=1, sticky="ew", pady=4)

        self.root.update_idletasks()
        try:
            exclude_native(self.root.winfo_id())
        except Exception:
            self._capture_exclusion_ready = False

        self.render(AppState.NO_REGION, "No region selected")
        self.root.after(16, self._draw_overlay)
        self.root.after(100, self._draw_features)

    def bind_actions(
        self,
        on_select: Callable[[], None],
        on_choose_folder: Callable[[], None],
        on_start: Callable[[], None],
        on_toggle_pause: Callable[[], None],
        on_stop: Callable[[], None],
        on_quit: Callable[[], None],
        on_generate_final: Callable[[], None] = lambda: None,
    ) -> None:
        self.select_button.configure(command=on_select)
        self.folder_button.configure(command=on_choose_folder)
        self.start_button.configure(command=on_start)
        self.pause_button.configure(command=on_toggle_pause)
        self.stop_button.configure(command=on_stop)
        self.quit_button.configure(command=on_quit)
        self.final_button.configure(command=on_generate_final)
        self.root.protocol("WM_DELETE_WINDOW", on_quit)

        def dispatch(event):
            action = control_shortcut(event.keysym)
            if action is PreviewAction.TOGGLE_PAUSE:
                on_toggle_pause()
            elif action is PreviewAction.RESELECT:
                on_select()
            elif action is PreviewAction.QUIT:
                on_quit()
            return "break" if action is not PreviewAction.NONE else None

        self.root.bind("<KeyPress>", dispatch)

    def render(self, state: AppState, status: str) -> None:
        self._state = state
        self._status_text = status
        if not self._capture_exclusion_ready:
            self._status.set("Control panel capture exclusion failed")
            for button in (
                self.select_button,
                self.folder_button,
                self.start_button,
                self.pause_button,
                self.stop_button,
            ):
                button.configure(state="disabled")
            self.quit_button.configure(state="normal")
            return

        self._status.set(status)
        active = state in {AppState.RUNNING, AppState.PAUSED}
        shutting_down = state is AppState.SHUTTING_DOWN
        busy = shutting_down or state in {AppState.FINALIZING, AppState.STOPPING}
        self.select_button.configure(state="disabled" if busy else "normal")
        self.folder_button.configure(state="disabled" if active or busy else "normal")
        options_valid = self.get_session_options().validation_error() is None
        self.start_button.configure(state="normal" if state is AppState.READY and self._has_folder and options_valid else "disabled")
        self.pause_button.configure(
            state="normal" if active else "disabled",
            text="Resume" if state is AppState.PAUSED else "Pause",
        )
        self.stop_button.configure(state="normal" if active else "disabled")
        self.final_button.configure(state="normal" if self._final_available and not active and not busy else "disabled")
        self.quit_button.configure(state="disabled" if shutting_down else "normal")

    def ask_save_folder(self) -> str:
        return filedialog.askdirectory(parent=self.root, mustexist=True)

    def _options_changed(self) -> None:
        self.render(self._state, self._status_text)

    def get_session_options(self) -> SessionOptions:
        return SessionOptions(
            video=self._video_var.get() == "1",
            system_audio=self._system_audio_var.get() == "1",
            microphone=self._microphone_var.get() == "1",
            transcript=self._transcript_var.get() == "1",
            consent_confirmed=self._consent_var.get() == "1",
            participant_id=self._participant_var.get(),
        )

    def publish_component_status(self, status: ComponentStatus) -> None:
        if status.message:
            self._status.set(f"{status.component}: {status.state.value} - {status.message}")

    def publish_audio_level(self, source: AudioSource, metrics) -> None:
        self._audio_values[source].set(f"{metrics.state.value}  RMS {metrics.rms:.3f}")

    def publish_transcript_metrics(self, metrics) -> None:
        self._feature_values["transcript_lag"].set(
            f"{metrics.lag_s:.1f} s | Dropped {metrics.dropped_chunks}"
        )

    def set_final_available(self, available: bool) -> None:
        self._final_available = bool(available)
        self.render(self._state, self._status_text)

    def publish_final_progress(self, value: float) -> None:
        self._status.set(f"Final transcript {value * 100:.0f}%")

    def show_final_transcript(self, rows) -> None:
        if self._transcript_panel is not None:
            self._transcript_panel.set_phase("final")
            self._transcript_panel.replace(rows)

    def show_transcript_panel(self, region) -> None:
        self.hide_transcript_panel()
        self._transcript_panel = self._transcript_factory(self.root, region)

    def publish_transcript(self, segment) -> None:
        if self._transcript_panel is not None: self._transcript_panel.publish(segment)

    def hide_transcript_panel(self) -> None:
        panel = self._transcript_panel; self._transcript_panel = None
        if panel is not None: panel.destroy()

    def show_save_folder(self, path: Path, next_name: str) -> None:
        self._has_folder = True
        shown = _shorten_middle(str(path), 34)
        self._folder_text.set(f"Save: {shown} / {next_name}")
        self.render(self._state, self._status_text)

    def publish_features(
        self,
        frame: FeatureFrame,
        row_count: int,
        filename: str,
    ) -> None:
        with self._feature_lock:
            self._latest_row_count = row_count
            self._latest_filename = filename
            self._latest_features.publish(frame)

    def clear_features(self) -> None:
        with self._feature_lock:
            self._latest_features.clear()
            self._latest_row_count = 0
            self._latest_filename = "--"
        for value in self._feature_values.values():
            value.set("--")

    def run_background(self, operation, completed) -> None:
        import threading
        def run():
            try:
                result = operation()
            except Exception as exc:
                result = str(exc)
            self.schedule(lambda: completed(result))
        threading.Thread(target=run, name="session-file-close", daemon=False).start()

    def schedule(self, callback: Callable[[], None]) -> None:
        self._scheduler.schedule(callback)

    def show_overlay(self, region) -> None:
        self.hide_overlay()
        self._overlay = self._overlay_factory(self.root, region)

    def publish_overlay(self, frame) -> None:
        overlay = self._overlay
        if overlay is not None:
            overlay.publish(frame)

    def pause_overlay(self) -> None:
        overlay = self._overlay
        if overlay is not None:
            overlay.set_paused(True)

    def hide_overlay(self) -> None:
        overlay = self._overlay
        self._overlay = None
        if overlay is not None:
            overlay.destroy()

    def _draw_overlay(self) -> None:
        if not self._active:
            return
        overlay = self._overlay
        if overlay is not None:
            overlay.draw_pending()
        if self._transcript_panel is not None:
            self._transcript_panel.draw_pending()
        self.root.after(16, self._draw_overlay)

    def _draw_features(self) -> None:
        if not self._active:
            return
        with self._feature_lock:
            frame = self._latest_features.take()
            row_count = self._latest_row_count
            filename = self._latest_filename
        if frame is not None:
            display = format_feature_display(frame, row_count, filename)
            for name, text in display.items():
                self._feature_values[name].set(text)
        self.root.after(100, self._draw_features)

    def close(self) -> None:
        self._active = False
        self._scheduler.close()
        self.hide_overlay()
        self.hide_transcript_panel()
        try:
            self.root.destroy()
        except tk.TclError:
            pass
