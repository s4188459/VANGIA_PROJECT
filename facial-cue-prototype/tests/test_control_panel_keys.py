import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.app_utils import PreviewAction
from src.capture_types import AppState
from src.control_panel import ControlPanel, control_shortcut
from src.feature_data import FeatureFrame
from src.audio_quality import AudioLevelMetrics, AudioLevelState
from src.audio_recorder import AudioSource
from src.transcription import TranscriptionMetrics


class FakeRoot:
    def __init__(self):
        self.bindings = {}
        self.protocols = {}
        self.after_calls = []
        self.resizable_values = None
        self.geometry_value = None
        self.minsize_value = None

    def title(self, _value):
        pass

    def resizable(self, *values):
        self.resizable_values = values

    def geometry(self, value):
        self.geometry_value = value

    def minsize(self, *values):
        self.minsize_value = values

    def rowconfigure(self, *_args, **_kwargs):
        pass

    def columnconfigure(self, *_args, **_kwargs):
        pass

    def after(self, *args):
        self.after_calls.append(args)

    def update_idletasks(self):
        pass

    def winfo_id(self):
        return 99

    def protocol(self, name, callback):
        self.protocols[name] = callback

    def bind(self, name, callback):
        self.bindings[name] = callback

    def destroy(self):
        pass


class FakeWidget:
    def __init__(self, _parent=None, **kwargs):
        self.options = dict(kwargs)

    def grid(self, **_kwargs):
        return self

    def columnconfigure(self, *_args, **_kwargs):
        pass

    def configure(self, **kwargs):
        self.options.update(kwargs)


class FakeStringVar:
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class ControlShortcutTests(unittest.TestCase):
    def test_finalizing_disables_capture_and_duplicate_final_commands(self):
        _root, panel = self.make_panel()
        panel.set_final_available(True)
        panel.render(AppState.FINALIZING, "Generating final transcript")
        for button in (panel.start_button, panel.select_button, panel.folder_button, panel.final_button):
            self.assertEqual(button.options["state"], "disabled")
        self.assertEqual(panel.quit_button.options["state"], "normal")

    def test_shortcut_mapping(self):
        expected = {
            "s": PreviewAction.TOGGLE_PAUSE,
            "S": PreviewAction.TOGGLE_PAUSE,
            "r": PreviewAction.RESELECT,
            "R": PreviewAction.RESELECT,
            "q": PreviewAction.QUIT,
            "Q": PreviewAction.QUIT,
            "Escape": PreviewAction.QUIT,
            "x": PreviewAction.NONE,
        }
        for keysym, action in expected.items():
            with self.subTest(keysym=keysym):
                self.assertIs(control_shortcut(keysym), action)

    def make_panel(self, exclude_native=lambda _hwnd: None):
        root = FakeRoot()
        patches = [
            patch("src.control_panel.ttk.Frame", FakeWidget),
            patch("src.control_panel.ttk.Label", FakeWidget),
            patch("src.control_panel.ttk.Button", FakeWidget),
            patch("src.control_panel.ttk.Checkbutton", FakeWidget),
            patch("src.control_panel.ttk.Entry", FakeWidget),
            patch("src.control_panel.ttk.Separator", FakeWidget),
            patch("src.control_panel.tk.StringVar", FakeStringVar),
        ]
        for active_patch in patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)
        return root, ControlPanel(root, exclude_native=exclude_native)

    def test_folder_enables_start_and_state_controls_other_buttons(self):
        _root, panel = self.make_panel()
        panel.render(AppState.READY, "Ready")
        self.assertEqual(panel.start_button.options["state"], "disabled")

        panel.show_save_folder(Path("C:/sessions"), "session_001.csv")
        panel._consent_var.set("1")
        panel.render(AppState.READY, "Ready")
        self.assertEqual(panel.start_button.options["state"], "normal")

    def test_options_require_consent_and_audio_for_transcript(self):
        _root, panel = self.make_panel()
        panel._transcript_var.set("1")
        panel._consent_var.set("1")
        self.assertEqual(panel.get_session_options().validation_error(), "Transcript requires meeting audio or microphone")
        panel._system_audio_var.set("1")
        self.assertIsNone(panel.get_session_options().validation_error())
        self.assertEqual(panel.consent_check.options["text"], "Consent confirmed")

        panel.render(AppState.RUNNING, "Running")
        self.assertEqual(panel.folder_button.options["state"], "disabled")
        self.assertEqual(panel.stop_button.options["state"], "normal")
        panel.render(AppState.PAUSED, "Paused")
        self.assertEqual(panel.stop_button.options["state"], "normal")
        panel.render(AppState.READY, "Ready")
        self.assertEqual(panel.stop_button.options["state"], "disabled")

    def test_panel_is_large_and_resizable_for_readable_coefficients(self):
        root, _panel = self.make_panel()

        self.assertEqual(root.resizable_values, (True, True))
        self.assertEqual(root.geometry_value, "700x860")
        self.assertEqual(root.minsize_value, (620, 720))

    def test_audio_levels_and_final_button_have_stable_states(self):
        _root, panel = self.make_panel()
        panel.publish_audio_level(AudioSource.MICROPHONE, AudioLevelMetrics(.02, .1, AudioLevelState.GOOD))
        self.assertIn("Good", panel._audio_values[AudioSource.MICROPHONE].value)
        panel.set_final_available(True)
        self.assertEqual(panel.final_button.options["state"], "normal")

    def test_transcript_latency_metrics_are_readable(self):
        _root, panel = self.make_panel()
        panel.publish_transcript_metrics(TranscriptionMetrics(2.84, 3))

        self.assertEqual(
            panel._feature_values["transcript_lag"].value,
            "2.8 s | Dropped 3",
        )

    def test_ask_save_folder_uses_native_directory_dialog(self):
        _root, panel = self.make_panel()
        with patch(
            "src.control_panel.filedialog.askdirectory", return_value="C:/sessions"
        ) as ask:
            self.assertEqual(panel.ask_save_folder(), "C:/sessions")
        ask.assert_called_once_with(parent=panel.root, mustexist=True)

    def test_capture_exclusion_failure_disables_capture_actions(self):
        def fail(_hwnd):
            raise RuntimeError("denied")

        _root, panel = self.make_panel(fail)
        self.assertEqual(panel._status.value, "Control panel capture exclusion failed")
        for button in (
            panel.select_button,
            panel.folder_button,
            panel.start_button,
            panel.pause_button,
            panel.stop_button,
        ):
            self.assertEqual(button.options["state"], "disabled")
        self.assertEqual(panel.quit_button.options["state"], "normal")

    def test_bound_actions_and_shortcuts_dispatch(self):
        root, panel = self.make_panel()
        calls = []
        panel.bind_actions(
            lambda: calls.append("select"),
            lambda: calls.append("folder"),
            lambda: calls.append("start"),
            lambda: calls.append("pause"),
            lambda: calls.append("stop"),
            lambda: calls.append("quit"),
        )
        panel.stop_button.options["command"]()
        dispatch = root.bindings["<KeyPress>"]
        dispatch(SimpleNamespace(keysym="s"))
        dispatch(SimpleNamespace(keysym="r"))
        dispatch(SimpleNamespace(keysym="Escape"))
        self.assertEqual(calls, ["stop", "pause", "select", "quit"])

    def test_feature_updates_coalesce_to_latest_frame(self):
        _root, panel = self.make_panel()
        panel.publish_features(FeatureFrame(1.0, 0, False), 1, "session_001.csv")
        panel.publish_features(
            FeatureFrame(2.0, 1, True, blink=0.8), 2, "session_001.csv"
        )

        panel._draw_features()

        self.assertEqual(panel._feature_values["elapsed"].value, "2.00 s")
        self.assertEqual(panel._feature_values["face"].value, "Visible")
        self.assertEqual(panel._feature_values["rows"].value, "2")


if __name__ == "__main__":
    unittest.main()
