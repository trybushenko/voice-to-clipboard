"""Run the actual Qt settings client in isolation, including failure paths."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Install the desktop extra for Qt UI tests')
class SettingsUITests(unittest.TestCase):
    def test_settings_interactions_offscreen(self):
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'check_settings_panel.py'
        result = subprocess.run([sys.executable, str(script)],
                                env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS: Qt', result.stdout)
