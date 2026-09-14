"""Offline regression tests: no microphone, GPU or clipboard mutation."""
import importlib.util
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
import numpy as np
import platform_support as desktop
import sys

spec = importlib.util.spec_from_file_location('dictate', Path(__file__).with_name('dictate.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

class WorkflowTests(unittest.TestCase):
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
            run.side_effect = d.subprocess.TimeoutExpired('xclip', 5)
            self.assertFalse(d.to_clipboard('text'))

    def test_history_keeps_complete_text_and_is_private_and_bounded(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(d, 'HISTORY', Path(temp) / 'history.json'):
            self.assertEqual(d.latest_text(), '')
            for i in range(55):
                d.save_history(f'Український текст {i}')
            d.save_history('partial', complete=False)
            self.assertEqual(len(d.read_history()), 50)
            self.assertEqual(d.latest_text(), 'Український текст 54')
            if sys.platform != 'win32':
                self.assertEqual(d.HISTORY.stat().st_mode & 0o777, 0o600)

    def test_legacy_prompt_history_is_not_used_for_append(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(d, 'HISTORY', Path(temp) / 'history.json'):
            d.save_history('Original')
            d.HISTORY.write_text(d.json.dumps(d.read_history() + [{'text': 'Formatted', 'kind': 'prompt', 'source': 'Original', 'complete': True}]))
            self.assertEqual(d.latest_text(), 'Original')
            self.assertEqual(d.read_history()[-1]['source'], 'Original')

    def test_corrupt_history_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(d, 'HISTORY', Path(temp) / 'history.json'):
            d.HISTORY.write_text('broken')
            with self.assertRaises(ValueError):
                d.save_history('new')
            self.assertEqual(d.HISTORY.read_text(), 'broken')

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
        with patch.object(worker, '_transcribe', side_effect=[RuntimeError('first'), 'recovered', RuntimeError('second'), RuntimeError('failed'), 'last']), patch.object(d, 'emit'):
            for _ in range(3):
                worker.submit(np.zeros(16000))
            worker.close(); worker.start(); worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(worker.parts, ['recovered', 'last'])
        self.assertEqual(worker.errors, ['failed'])

if __name__ == '__main__':
    unittest.main()
