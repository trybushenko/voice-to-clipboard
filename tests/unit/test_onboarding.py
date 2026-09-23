"""Setup completion uses the same transaction as validated settings."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from voice_to_clipboard.core import desktop_settings, settings
from voice_to_clipboard.ui import hotkeys


class OnboardingTests(unittest.TestCase):
    def test_load_is_read_only_for_clean_legacy_and_completed_settings(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, VOICE_TO_CLIPBOARD_DATA_DIR=folder):
            path = Path(folder) / 'settings.json'
            self.assertFalse(desktop_settings.load()['onboarding_complete'])
            self.assertEqual([p['language'] for p in desktop_settings.load()['profiles']], ['en'])
            self.assertFalse(path.exists())
            history = Path(folder) / 'history.json'
            history.write_text('[]')
            self.assertEqual(len(desktop_settings.load()['profiles']), 3)
            for version in (2, 3):
                original = {'schema_version': version, 'model': 'team/custom', 'unrelated': 42,
                            'profiles': [{'language': 'pl', 'key': 'p', 'modifiers': 'ctrl+alt'}]}
                path.write_text(json.dumps(original))
                before = path.read_bytes()
                loaded = desktop_settings.load()
                self.assertFalse(loaded['onboarding_complete'])
                self.assertEqual(path.read_bytes(), before)
                loaded['onboarding_complete'] = True
                settings.save_settings(desktop_settings.validate(loaded))
                self.assertTrue(desktop_settings.load()['onboarding_complete'])
                self.assertEqual(settings.read_settings()['unrelated'], 42)
                self.assertEqual(desktop_settings.load()['profiles'][0]['modifiers'], 'alt+ctrl')
                self.assertEqual(history.read_text(), '[]')

    def test_completion_requires_boolean(self):
        for invalid in ('true', 1, None):
            with self.assertRaises(ValueError):
                desktop_settings.validate({'onboarding_complete': invalid})

    def test_host_start_failure_success_and_restart(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,
                VOICE_TO_CLIPBOARD_DATA_DIR=folder, VOICE_TO_CLIPBOARD_CACHE_DIR=folder, WAYLAND_DISPLAY=''):
            path = Path(folder) / 'settings.json'
            history = Path(folder) / 'history.json'
            history.write_text('[]')
            original = {'schema_version': 2, 'profiles': [{'language': 'en', 'key': 'e'}], 'other': 42}
            path.write_text(json.dumps(original))
            before = path.read_bytes()
            launcher = Mock(children=[], worker=None, state='idle', message='')
            listener = Mock(error=None)
            controller = Mock(paused=False, listener=listener)
            server = Mock()
            def exercise(handle):
                self.assertEqual(path.read_bytes(), before, 'Startup must not rewrite preferences')
                self.assertFalse(handle({'op': 'status'})['onboarding_complete'])
                values = {'onboarding_complete': True, 'model': 'small'}
                for failure in ('validation', 'registration', 'write'):
                    with self.subTest(failure=failure):
                        candidate = {**values, 'overlay': 'invalid'} if failure == 'validation' else values
                        controller.resume.side_effect = [RuntimeError('conflict'), None] if failure == 'registration' else None
                        with patch.object(settings, 'save_settings', side_effect=OSError('disk full')) if failure == 'write' else patch.object(settings, 'save_settings', wraps=settings.save_settings):
                            with self.assertRaises((RuntimeError, OSError, ValueError)):
                                handle({'op': 'settings', 'values': candidate})
                        self.assertFalse(handle({'op': 'status'})['onboarding_complete'])
                        self.assertEqual(path.read_bytes(), before)
                controller.resume.side_effect = None
                reply = handle({'op': 'settings', 'values': values})
                self.assertTrue(reply['onboarding_complete'])
                self.assertTrue(desktop_settings.load()['onboarding_complete'])
                self.assertEqual(settings.read_settings()['other'], 42)
                self.assertEqual(history.read_text(), '[]')
                handle({'op': 'quit'})
            server.dispatch.side_effect = exercise
            with patch('voice_to_clipboard.platform.desktop.SessionLock'), patch('voice_to_clipboard.core.hotkey_session.SessionLauncher', return_value=launcher), patch('voice_to_clipboard.core.host_control.ListenerController', return_value=controller), patch('voice_to_clipboard.core.host_control.ControlServer', return_value=server):
                hotkeys.main([], desktop=Mock())
                persisted = path.read_bytes()
                def restarted(handle):
                    self.assertTrue(handle({'op': 'status'})['onboarding_complete'])
                    self.assertEqual(path.read_bytes(), persisted)
                    handle({'op': 'quit'})
                server.dispatch.side_effect = restarted
                hotkeys.main([], desktop=Mock())

    def test_clean_host_remembers_english_before_first_recording_creates_history(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,
                VOICE_TO_CLIPBOARD_DATA_DIR=folder, VOICE_TO_CLIPBOARD_CACHE_DIR=folder, WAYLAND_DISPLAY=''):
            launcher = Mock(children=[], worker=None, state='idle', message='')
            controller = Mock(paused=False, listener=Mock(error=None))
            server = Mock()
            def exercise(handle):
                self.assertFalse(handle({'op': 'status'})['onboarding_complete'])
                (Path(folder) / 'history.json').write_text('[]')
                self.assertEqual([p['language'] for p in desktop_settings.load()['profiles']], ['en'])
                self.assertFalse(desktop_settings.load()['onboarding_complete'])
                handle({'op': 'quit'})
            server.dispatch.side_effect = exercise
            with patch('voice_to_clipboard.platform.desktop.SessionLock'), patch('voice_to_clipboard.core.hotkey_session.SessionLauncher', return_value=launcher), patch('voice_to_clipboard.core.host_control.ListenerController', return_value=controller), patch('voice_to_clipboard.core.host_control.ControlServer', return_value=server):
                hotkeys.main([], desktop=Mock())
                hotkeys.main([], desktop=Mock())
