"""Installed commands and worker must work outside the checkout."""
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile
import time
import unittest
from voice_to_clipboard.worker.transport import connect
from voice_to_clipboard.worker.protocol import send, receive


class PackageTests(unittest.TestCase):
    def test_entry_points_from_another_directory(self):
        scripts = Path(sysconfig.get_path('scripts'))
        suffix = '.exe' if sys.platform == 'win32' else ''
        with tempfile.TemporaryDirectory() as directory:
            commands = [[sys.executable, '-m', 'voice_to_clipboard']]
            commands += [[str(scripts / (name + suffix))] for name in
                         ('dictate', 'voice-to-clipboard', 'voice-hotkeys')]
            for command in commands:
                with self.subTest(command=command):
                    result = subprocess.run(command + ['--help'], cwd=directory,
                                            capture_output=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
                    self.assertIn(b'--', result.stdout)

    def test_worker_module_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / 'worker'
            process = subprocess.Popen(
                [sys.executable, '-m', 'voice_to_clipboard.worker.service'],
                cwd=directory, env={**os.environ, 'DICTATE_RUNTIME': str(runtime)},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 10
                while not (runtime / 'worker.sock').exists():
                    if process.poll() is not None:
                        self.fail(process.communicate()[1].decode(errors='replace'))
                    if time.monotonic() > deadline:
                        self.fail('Worker did not create its endpoint')
                    time.sleep(.05)
                with connect(runtime / 'worker.sock', timeout=3) as sock:
                    send(sock, {'op': 'status'})
                    self.assertEqual(receive(sock), {'loaded': False, 'config': None})
                with connect(runtime / 'worker.sock', timeout=3) as sock:
                    send(sock, {'op': 'shutdown'})
                    self.assertTrue(receive(sock)['ok'])
                self.assertEqual(process.wait(timeout=5), 0)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)
