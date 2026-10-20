import os
import pytest


@pytest.mark.skipif(os.environ.get('ASRLAB_TEST_UI')!='1',reason='Desktop test enabled explicitly with ASRLAB_TEST_UI=1')
def test_desktop_seven_views_registry_and_fixture(tmp_path):
    import tkinter as tk
    from asrlab.ui import LabApp
    from asrlab.runner import run
    path=tmp_path/'fixture';run({'mode':'synthetic_fixture','out':str(path)})
    root=tk.Tk()
    try:
        app=LabApp(root,path);root.update()
        assert len(app.tabs.tabs())==7
        assert len(app.candidate_ids)==11
        assert app.review_tree.winfo_exists()
        assert 'synthetic_fixture' in app.summary.get('1.0','end')
        app.load_evidence()
        assert app.review_tree.get_children()
    finally:root.destroy()
