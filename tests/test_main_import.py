import unittest

import tkinter

from src import control_panel, main


class MainImportTests(unittest.TestCase):
    def test_gui_modules_import_without_creating_a_window(self):
        self.assertTrue(callable(main.run))
        self.assertEqual(main.WINDOW_TITLE, "Multimodal Dataset Collector")
        self.assertTrue(hasattr(control_panel, "ControlPanel"))
        self.assertGreater(tkinter.TkVersion, 0)


if __name__ == "__main__":
    unittest.main()
