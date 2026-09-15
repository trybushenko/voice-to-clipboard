import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
import numpy as np
from voice_to_clipboard.worker import client as m, service, protocol

class ServiceTests(unittest.TestCase):
    def test_reuse_audio_options_errors_and_idle_exit(self):
        calls, loads = [], []
        class Model:
            def transcribe(self, audio, **options):
                calls.append((audio.copy(), options))
                if options.get('language') == 'bad':
                    raise ValueError('test decode failure')
                return [SimpleNamespace(text='Тест')], None
        def factory(*config):
            loads.append(config)
            return Model()
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp)
            thread = threading.Thread(target=service.serve, args=(runtime, .5, factory), daemon=True)
            thread.start()
            for _ in range(100):
                if (runtime / 'worker.sock').exists():
                    break
                time.sleep(.01)
            # Patch only this module's dependency, not subprocess globally:
            # NumPy/Python may legitimately query Windows platform information.
            with patch.object(m, 'subprocess', SimpleNamespace(Popen=Mock(side_effect=AssertionError('Unexpected launch')))):
                first = m.RemoteModel('test', 'float16', runtime)
                audio = np.array([.1, -.4], dtype=np.float32)
                segments, _ = first.transcribe(audio, language='uk')
                self.assertEqual(segments[0].text, 'Тест')
                first.close()
                second = m.RemoteModel('test', 'float16', runtime)
                self.assertEqual(len(loads), 1)
                np.testing.assert_array_equal(calls[0][0], audio)
                self.assertEqual(calls[0][1], {'language': 'uk'})
                with self.assertRaisesRegex(RuntimeError, 'test decode failure'):
                    second.transcribe(audio, language='bad')
                # A failed request reconnects and reuses the loaded model.
                self.assertEqual(second.transcribe(audio, language='uk')[0][0].text, 'Тест')
                self.assertEqual(len(loads), 1)
                second.close()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertFalse((runtime / 'worker.sock').exists())

    def test_framing_rejects_oversize(self):
        a, b = socket.socketpair()
        with a, b:
            a.sendall(protocol.struct.pack('!I', protocol.MAX_PACKET + 1))
            with self.assertRaises(ValueError):
                protocol.receive(b)

if __name__ == '__main__':
    unittest.main()
