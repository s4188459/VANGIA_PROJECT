from __future__ import annotations

import queue
import tkinter as tk

from .capture_types import CaptureRegion
from .windows_overlay import exclude_window_from_capture


def transcript_panel_geometry(region: CaptureRegion, panel_size: tuple[int, int],
                              work_area: tuple[int, int, int, int], gap: int = 8) -> str:
    width, height = panel_size; left, top, right, bottom = work_area
    if region.left + region.width + gap + width <= right:
        x = region.left + region.width + gap
    elif region.left - gap - width >= left:
        x = region.left - gap - width
    else:
        x = max(left, min(right - width, region.left + region.width + gap))
    y = max(top, min(bottom - height, region.top))
    sign_x = f"+{x}" if x >= 0 else str(x); sign_y = f"+{y}" if y >= 0 else str(y)
    return f"{width}x{height}{sign_x}{sign_y}"


class TranscriptPanel:
    def __init__(self, root, region: CaptureRegion, *, exclude_native=exclude_window_from_capture) -> None:
        self._region = region; self._pending = queue.SimpleQueue(); self._destroyed = False
        self._window = tk.Toplevel(root)
        try:
            self._window.title("Live English Transcript")
            self._window.protocol("WM_DELETE_WINDOW", self.destroy)
            self._window.attributes("-topmost", True); self._window.resizable(True, True)
            self._window.geometry(transcript_panel_geometry(region, (360, max(260, min(520, region.height))),
                                                            (0, 0, root.winfo_screenwidth(), root.winfo_screenheight())))
            header = tk.Frame(self._window, padx=10, pady=8); header.pack(fill="x")
            self._phase = tk.StringVar(value="LIVE Transcript")
            tk.Label(header, textvariable=self._phase, font=("Segoe UI", 11, "bold")).pack(side="left")
            self._text = tk.Text(self._window, wrap="word", state="disabled", font=("Segoe UI", 10), padx=10, pady=8)
            self._text.pack(fill="both", expand=True)
            self._window.update_idletasks(); exclude_native(self._window.winfo_id())
        except Exception:
            self.destroy()
            raise

    def publish(self, segment) -> None:
        if not self._destroyed: self._pending.put(segment)
    def draw_pending(self) -> bool:
        if self._destroyed: return False
        changed = False
        while True:
            try: segment = self._pending.get_nowait()
            except queue.Empty: break
            changed = True; self._text.configure(state="normal")
            self._text.insert("end", f"{segment.speaker} [{segment.start_s:06.1f}]\n{segment.text}\n\n")
            lines = int(self._text.index("end-1c").split(".")[0])
            if lines > 120: self._text.delete("1.0", f"{lines - 100}.0")
            self._text.configure(state="disabled"); self._text.see("end")
        return changed
    def set_region(self, region: CaptureRegion) -> None: self._region = region
    def set_phase(self, phase: str) -> None:
        if not self._destroyed: self._phase.set(f"{phase.upper()} Transcript")
    def replace(self, segments) -> None:
        if self._destroyed: return
        self._text.configure(state="normal"); self._text.delete("1.0", "end")
        for segment in segments:
            speaker = segment["speaker"] if isinstance(segment, dict) else segment.speaker
            start = segment["start_s"] if isinstance(segment, dict) else segment.start_s
            value = segment["text"] if isinstance(segment, dict) else segment.text
            self._text.insert("end", f"{speaker} [{start:06.1f}]\n{value}\n\n")
        self._text.configure(state="disabled"); self._text.see("end")
    def set_collapsed(self, collapsed: bool) -> None:
        if self._destroyed: return
        if collapsed: self._text.pack_forget()
        else: self._text.pack(fill="both", expand=True)
    def destroy(self) -> None:
        if not self._destroyed: self._destroyed = True; self._window.destroy()
