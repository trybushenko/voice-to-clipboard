import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from voice_to_clipboard.core import desktop_settings, settings
from voice_to_clipboard.core.model_compatibility import describe, validate


class ModelCompatibilityTests(unittest.TestCase):
    def test_known_aliases_and_language_limits(self):
        for model in ('small.en', 'distil-large-v3', 'Systran/faster-whisper-small.en',
                      'mlx-community/whisper-small.en-mlx', 'distil-whisper/distil-large-v3'):
            with self.subTest(model=model):
                validate('en', model)
                with self.assertRaisesRegex(ValueError, 'English-only'):
                    validate('pl', model)
        for model in ('tiny', 'large-v2', 'Systran/faster-whisper-medium'):
            validate('uk', model)
            with self.assertRaisesRegex(ValueError, 'Cantonese'):
                validate('yue', model)
        for model in ('large-v3', '', 'large-v3-turbo'):
            validate('yue', model)

    def test_unknown_paths_are_unverified_not_guessed(self):
        for model in ('team/small.en', '/models/small.en', r'C:\models\small.en', 'team/distil-large-v3'):
            self.assertEqual(describe('pl', model)[0], 'unverified')
            validate('pl', model)

    def test_effective_default_and_override(self):
        with self.assertRaises(ValueError):
            desktop_settings.validate({'model': 'distil-large-v3', 'profiles': [{'language': 'pl', 'key': 'p'}]})
        result = desktop_settings.validate({'model': 'distil-large-v3', 'profiles': [{'language': 'pl', 'key': 'p', 'model': 'small'}]})
        self.assertEqual(result['model'], 'distil-large-v3')
        self.assertEqual(describe('pl', '', 'small')[0], 'compatible')

    def test_old_incompatible_settings_can_be_repaired_without_rewrite(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(settings, 'data_dir', return_value=Path(folder)):
            original = {'schema_version': 3, 'model': 'distil-large-v3',
                        'profiles': [{'language': 'pl', 'key': 'p', 'model': '', 'modifiers': 'ctrl+alt'}], 'other': 42}
            settings.save_settings(original)
            path = Path(folder) / 'settings.json'
            before = path.read_bytes()
            loaded = desktop_settings.load()
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(ValueError):
                desktop_settings.validate(loaded)
            for model in ('small', 'team/my-model'):
                loaded['profiles'][0]['model'] = model
                settings.save_settings(desktop_settings.validate(loaded))
                reloaded = desktop_settings.load()
                self.assertEqual(reloaded['profiles'][0]['model'], model)
                self.assertEqual(reloaded['profiles'][0]['modifiers'], 'alt+ctrl')
                self.assertEqual(reloaded['model'], 'distil-large-v3')
                self.assertEqual(settings.read_settings()['other'], 42)

    def test_cli_rejects_before_any_runtime_work(self):
        from voice_to_clipboard.cli import parse_args
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            parse_args(['--lang', 'pl', '--model', 'distil-large-v3'])
        self.assertEqual(error.exception.code, 2)
        parse_args(['--history', '--lang', 'pl', '--model', 'distil-large-v3'])

    def test_launcher_never_spawns_incompatible_model(self):
        from voice_to_clipboard.core.hotkey_session import SessionLauncher
        launcher = SessionLauncher(SimpleNamespace(model='distil-large-v3', inference_device='cpu', no_overlay=True))
        with patch('voice_to_clipboard.core.hotkey_session.try_stop_running', return_value=False), patch('voice_to_clipboard.core.hotkey_session.spawn_background') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'English-only'):
                launcher.launch('pl')
            spawn.assert_not_called()
