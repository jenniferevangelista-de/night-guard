"""Runs the JavaScript overlay tests with Node, if Node is installed."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_overlay_js():
    r = subprocess.run(["node", "--test", str(Path(__file__).with_name("overlay.test.js"))],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_ui_js():
    r = subprocess.run(["node", "--test", str(Path(__file__).with_name("ui.test.js"))],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
