"""Offline regression tests: no microphone, GPU or clipboard mutation."""
from pathlib import Path
import tempfile
from contextlib import ExitStack
import threading
import types
import unittest
from unittest.mock import patch
import numpy as np
from voice_to_clipboard.platform import desktop
import sys

from voice_to_clipboard import cli as d
from voice_to_clipboard.core import history, transcription
import subprocess

class WorkflowTests(unittest.TestCase):
    def test_session_delivers_tail_after_package_split(self):
        for tty in (False, True):
            with self.subTest(tty=tty):
                self.check_session_tail(tty)

    def check_session_tail(self, tty):
        from unittest.mock import Mock
        gate = types.SimpleNamespace(last_db=-25.0, armed=True, speech_total=1.0,
                                     in_speech=True, floor_db=-60.0, threshold_db=-40.0,
                                     vad_hit=False, vad=None)
        recorder = Mock()
        recorder.elapsed.return_value = 2.0
        recorder.finish.return_value = np.zeros(16000, dtype=np.float32)
        model = Mock()
        model.transcribe.return_value = ([types.SimpleNamespace(text='Hello')], None)
        def load(holder, ready, *args):
            holder['model'] = model
            ready.set()
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch.object(d, 'parse_args', return_value=d.parse_args(['--max', '1', '--lang', 'en'])))
            stack.enter_context(patch.object(d, 'SOCK', str(Path(directory) / 'session.sock')))
            for name, replacement in {'try_stop_running': Mock(return_value=False),
                                      'stop_listener': Mock(), 'SessionLock': Mock(),
                                      'SpeechGate': Mock(return_value=gate),
                                      'Recorder': Mock(return_value=recorder),
                                      'load_model': load, 'notify': Mock(),
                                      'save_history': Mock(), 'to_clipboard': Mock(return_value=True)}.items():
                stack.enter_context(patch.object(d, name, replacement))
            stack.enter_context(patch('voice_to_clipboard.ui.overlay.Overlay'))
            stack.enter_context(patch.object(d.atexit, 'register'))
            stream = Mock()
            stream.isatty.return_value = tty
            stack.enter_context(patch.object(sys, 'stderr', stream))
            stack.enter_context(patch('builtins.print'))
            d.main()
            d.save_history.assert_called_once_with('Hello', complete=True)
            d.to_clipboard.assert_called_once_with('Hello')
            model.close.assert_called_once()
            if tty:
                self.assertTrue(any("поріг" in str(call) for call in stream.write.call_args_list))

    def test_cli_preserves_hotkey_options_and_live_toggle(self):
        uk = d.parse_args(['--silence', '0', '--lang', 'uk', '--overlay'])
        en = d.parse_args(['--silence', '0', '--lang', 'en', '--beam', '5', '--overlay'])
        self.assertEqual((uk.lang, uk.silence, uk.live, uk.overlay), ('uk', 0, True, True))
        self.assertEqual((en.lang, en.beam), ('en', 5))
        self.assertFalse(d.parse_args(['--no-live']).live)

    def test_clipboard_failure_and_timeout(self):
        with patch.object(desktop.sys, 'platform', 'linux'), patch.object(desktop.shutil, 'which', return_value='/usr/bin/xclip'), patch.object(desktop.subprocess, 'run') as run:
            run.return_value.returncode = 1
            self.assertFalse(d.to_clipboard('text'))
            run.return_value.returncode = 0
            self.assertTrue(d.to_clipboard('text'))
            run.side_effect = subprocess.TimeoutExpired('xclip', 5)
            self.assertFalse(d.to_clipboard('text'))

    def test_history_keeps_complete_text_and_is_private_and_bounded(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(history, 'HISTORY', Path(temp) / 'history.json'):
            self.assertEqual(history.latest_text(), '')
            for i in range(55):
                history.save_history(f'Український текст {i}')
            history.save_history('partial', complete=False)
            self.assertEqual(len(history.read_history()), 50)
            self.assertEqual(history.latest_text(), 'Український текст 54')
            if sys.platform != 'win32':
                self.assertEqual(history.HISTORY.stat().st_mode & 0o777, 0o600)

    def test_legacy_prompt_history_is_not_used_for_append(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(history, 'HISTORY', Path(temp) / 'history.json'):
            history.save_history('Original')
            history.HISTORY.write_text(history.json.dumps(history.read_history() + [{'text': 'Formatted', 'kind': 'prompt', 'source': 'Original', 'complete': True}]))
            self.assertEqual(history.latest_text(), 'Original')
            self.assertEqual(history.read_history()[-1]['source'], 'Original')

    def test_corrupt_history_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(history, 'HISTORY', Path(temp) / 'history.json'):
            history.HISTORY.write_text('broken')
            with self.assertRaises(ValueError):
                history.save_history('new')
            self.assertEqual(history.HISTORY.read_text(), 'broken')

    def test_audio_tail_at_block_boundaries(self):
        rec = object.__new__(d.Recorder)
        rec.lock = threading.Lock()
        rec.frames = [np.arange(5), np.arange(5, 10), np.arange(10, 13)]
        rec.n = 13
        for start in (0, 3, 5, 10, 12, 13):
            audio, total = rec.slice_from(start)
            np.testing.assert_array_equal(audio, np.arange(start, 13))
            self.assertEqual(total, 13)

    def test_english_language_and_beam_reach_decoder(self):
        from unittest.mock import Mock
        model = Mock()
        model.transcribe.return_value = ([types.SimpleNamespace(text='Hello world')], None)
        worker = d.Transcriber({'model': model}, threading.Event(), types.SimpleNamespace(lang='en', beam=5), False)
        self.assertEqual(worker._transcribe(np.zeros(16000)), 'Hello world')
        options = model.transcribe.call_args.kwargs
        self.assertEqual(options['language'], 'en')
        self.assertEqual(options['beam_size'], 5)
        self.assertNotIn('Технічний', options['initial_prompt'])

    def test_transcription_retry_and_partial_failure(self):
        ready = threading.Event(); ready.set()
        worker = d.Transcriber({'model': object()}, ready, types.SimpleNamespace(), False)
        with patch.object(worker, '_transcribe', side_effect=[RuntimeError('first'), 'recovered', RuntimeError('second'), RuntimeError('failed'), 'last']), patch.object(transcription, 'emit'):
            for _ in range(3):
                worker.submit(np.zeros(16000))
            worker.close(); worker.start(); worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(worker.parts, ['recovered', 'last'])
        self.assertEqual(worker.errors, ['failed'])

if __name__ == '__main__':
    unittest.main()
