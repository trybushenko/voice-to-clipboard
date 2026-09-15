"""Real subprocess reuse/crash recovery without model downloads or microphone."""
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import numpy as np
from voice_to_clipboard.core.lifecycle import stop_on_interrupt
from voice_to_clipboard.worker import client
from voice_to_clipboard.platform.processes import spawn_background

FIXTURE = '''
import os
from pathlib import Path
from types import SimpleNamespace
from voice_to_clipboard.worker.service import serve
class Model:
    def transcribe(self, audio, **options):
        return [SimpleNamespace(text=f"{os.getpid()}:{len(audio)}")], None
    def unload(self):
        pass
serve(Path(os.environ['DICTATE_RUNTIME']), idle=10, make_model=lambda *args: Model())
'''


class WorkerLifecycleTests(unittest.TestCase):
    def test_twenty_sessions_sigint_tail_and_crash_recovery(self):
        processes = []
        def spawn(command, **options):
            process = spawn_background([sys.executable, '-c', FIXTURE], **options)
            processes.append(process)
            return process
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            try:
                with patch.object(client, 'spawn_background', side_effect=spawn):
                    pid = None
                    for _ in range(20):
                        event = threading.Event()
                        with stop_on_interrupt(event):
                            model = client.RemoteModel('fake', 'auto', runtime)
                            try:
                                signal.raise_signal(signal.SIGINT)
                                self.assertTrue(event.is_set())
                                segments, _ = model.transcribe(np.zeros(777, dtype=np.float32))
                                worker_pid, samples = segments[0].text.split(':')
                                self.assertEqual(samples, '777')
                                if pid is None:
                                    pid = worker_pid
                                self.assertEqual(worker_pid, pid)
                                self.assertIsNone(processes[0].poll())
                            finally:
                                model.close()
                    self.assertEqual(len(processes), 1)
                    # Kill the owned worker while a client connection is open.
                    model = client.RemoteModel('fake', 'auto', runtime)
                    processes[0].kill(); processes[0].wait(timeout=5)
                    with self.assertRaises((OSError, EOFError)):
                        model.transcribe(np.zeros(123, dtype=np.float32))
                    try:
                        segments, _ = model.transcribe(np.zeros(123, dtype=np.float32))
                        new_pid, samples = segments[0].text.split(':')
                        self.assertNotEqual(new_pid, pid)
                        self.assertEqual(samples, '123')
                        self.assertEqual(len(processes), 2)
                        model.request({'op': 'shutdown'})
                    finally:
                        model.close()
                    self.assertEqual(processes[-1].wait(timeout=5), 0)
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=5)
