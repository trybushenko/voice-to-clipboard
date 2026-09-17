"""Owned real worker starts and exits without loading a model or opening audio."""
from pathlib import Path
import tempfile
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from voice_to_clipboard.core.hotkey_session import SessionLauncher


class DesktopWorkerTests(unittest.TestCase):
    def test_shutdown_reaps_owned_worker_and_removes_private_runtime(self):
        with tempfile.TemporaryDirectory(prefix='vtc-', dir=None if sys.platform == 'win32' else '/tmp') as folder, patch('voice_to_clipboard.platform.paths.cache_dir', return_value=Path(folder)):
            launcher = SessionLauncher(SimpleNamespace(desktop=True))
            runtime = launcher.runtime
            try:
                launcher._ensure_worker()
                worker = launcher.worker
                self.assertIsNone(worker.poll())
                self.assertTrue((runtime / 'worker.sock').exists())
                launcher._ensure_worker()
                self.assertIs(launcher.worker, worker)
            finally:
                launcher.shutdown()
            self.assertIsNotNone(worker.poll())
            self.assertFalse(runtime.exists())
