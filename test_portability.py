import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock
import numpy as np
import local_ipc
import platform_support as desktop
import speech_backends as backends


class PortabilityTests(unittest.TestCase):
    def test_apple_silicon_selects_mlx(self):
        with patch.object(backends.sys, 'platform', 'darwin'), patch.object(backends.platform, 'machine', return_value='arm64'):
            self.assertEqual(backends.resolve_backend(), 'mlx')
            self.assertEqual(backends.resolve_backend(device='cpu'), 'faster-whisper')
            self.assertEqual(backends.resolve_backend('faster-whisper'), 'faster-whisper')

    def test_cpu_and_cuda_compute_defaults(self):
        engine = Mock()
        for count, device, compute in [(0, 'cpu', 'int8'), (1, 'cuda', 'float16')]:
            with patch.dict('sys.modules', {'ctranslate2': SimpleNamespace(get_cuda_device_count=lambda: count),
                                          'faster_whisper': SimpleNamespace(WhisperModel=engine)}):
                backends.FasterModel('tiny', 'auto', 'auto')
                engine.assert_called_with('tiny', device=device, compute_type=compute)

    def test_mlx_adapter_drops_unsupported_options(self):
        engine = Mock()
        engine.transcribe.return_value = {'segments': [{'text': 'hello'}]}
        with patch.dict('sys.modules', {'mlx_whisper': engine}):
            model = backends.MLXModel('large-v3-turbo')
            result, _ = model.transcribe(np.zeros(100), language='en', beam_size=5, vad_filter=True, vad_parameters={})
        self.assertEqual(result[0].text, 'hello')
        options = engine.transcribe.call_args.kwargs
        self.assertEqual(options['language'], 'en')
        self.assertNotIn('beam_size', options)
        self.assertNotIn('vad_filter', options)
        self.assertEqual(options['path_or_hf_repo'], 'mlx-community/whisper-large-v3-turbo')

    def test_macos_clipboard_unicode(self):
        with patch.object(desktop.sys, 'platform', 'darwin'), patch.object(desktop.shutil, 'which', return_value='/usr/bin/pbcopy'), patch.object(desktop.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertTrue(desktop.to_clipboard('Привіт 👋'))
            self.assertEqual(run.call_args.args[0], ['pbcopy'])
            self.assertEqual(run.call_args.kwargs['input'], 'Привіт 👋'.encode())

    def test_windows_clipboard_dispatch(self):
        with patch.object(desktop.sys, 'platform', 'win32'), patch.object(desktop, '_windows_clipboard', return_value=True) as copy:
            self.assertTrue(desktop.to_clipboard('Hello'))
            copy.assert_called_once_with('Hello')

    def test_process_lock_released(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.lock'
            with desktop.SessionLock(path):
                with self.assertRaises(BlockingIOError):
                    desktop.SessionLock(path)
            with desktop.SessionLock(path):
                pass

    def test_windows_transport_rejects_bad_token_and_serves_valid_client(self):
        # TCP implementation is exercised on every CI host, not only Windows.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'endpoint'
            with patch.object(local_ipc.sys, 'platform', 'win32'):
                with local_ipc.Server(path) as server:
                    server.settimeout(3)
                    errors = []
                    def respond():
                        try:
                            conn, _ = server.accept()
                            with conn:
                                conn.sendall(conn.recv(5).upper())
                        except Exception as exc:
                            errors.append(exc)
                    thread = threading.Thread(target=respond, daemon=True)
                    thread.start()
                    info = json.loads(path.read_text())
                    with socket.create_connection(('127.0.0.1', info['port']), timeout=2) as bad:
                        bad.sendall(b'x'*64)
                        self.assertEqual(bad.recv(2), b'')
                    with local_ipc.connect(path, timeout=2) as client:
                        client.sendall(b'hello')
                        self.assertEqual(client.recv(5), b'HELLO')
                    thread.join(3)
                    self.assertFalse(thread.is_alive())
                    self.assertEqual(errors, [])
                self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
