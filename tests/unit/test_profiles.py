import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from voice_to_clipboard.core import profiles, desktop_settings
from voice_to_clipboard.core.host_control import ListenerController


class ProfileTests(unittest.TestCase):
    def test_new_user_has_only_english_and_no_ukrainian_shortcuts(self):
        with tempfile.TemporaryDirectory() as folder, patch('voice_to_clipboard.platform.paths.data_dir', return_value=Path(folder)), patch.object(desktop_settings, 'read_settings', return_value={}):
            result = desktop_settings.load()
        self.assertEqual(result['profiles'], profiles.defaults())
        self.assertEqual(result['schema_version'], 2)

    def test_existing_preferences_migrate_without_overwriting_model(self):
        with patch.object(desktop_settings, 'read_settings', return_value={'hotkey_modifiers': 'ctrl+alt', 'model': 'custom'}):
            result = desktop_settings.load()
        self.assertEqual([p['key'] for p in result['profiles']], ['u', 'e', 'l'])
        self.assertEqual(result['model'], 'custom')
        # Saving/reloading versioned profiles must never restore deleted languages.
        result['profiles'] = profiles.defaults()
        with patch.object(desktop_settings, 'read_settings', return_value=result):
            self.assertEqual(desktop_settings.load()['profiles'], profiles.defaults())

    def test_history_only_legacy_user_keeps_shortcuts(self):
        with tempfile.TemporaryDirectory() as folder, patch('voice_to_clipboard.platform.paths.data_dir', return_value=Path(folder)), patch.object(desktop_settings, 'read_settings', return_value={}):
            (Path(folder)/'history.json').write_text('[]')
            self.assertEqual(len(desktop_settings.load()['profiles']), 3)

    def test_profile_validation(self):
        for value in ([], [{'language': 'xx', 'key': 'x'}], [{'language': 'pl', 'key': 'p', 'model': 'small.en'}], [{'language': 'en', 'key': 'e'}, {'language': 'pl', 'key': 'E'}]):
            with self.assertRaises(ValueError):
                profiles.validate(value)
        self.assertEqual(profiles.validate([{'language': 'pl', 'key': 'P'}])[0]['key'], 'p')
        with self.assertRaises(ValueError):
            desktop_settings.validate({'model': 'small.en', 'profiles': [{'language': 'pl', 'key': 'p'}]})
        with self.assertRaises(ValueError):
            desktop_settings.validate({'schema_version': 99})

    def test_callbacks_only_register_configured_profiles_and_preserve_identity(self):
        configured = [{'language': 'pl', 'key': 'p', 'paste': False, 'model': 'small'},
                      {'language': 'pl', 'key': 'o', 'paste': False, 'model': 'large-v3-turbo'}]
        listener = Mock(ident=None)
        factory, enqueue = Mock(return_value=listener), Mock()
        controller = ListenerController(factory, enqueue, lambda: configured)
        controller.resume()
        callbacks = factory.call_args.args[0]
        self.assertEqual(set(callbacks), {'p', 'o'})
        callbacks['o']()
        self.assertEqual(enqueue.call_args.args[0][1]['model'], 'large-v3-turbo')
        listener.is_alive.return_value = False
        controller.pause()
        enqueue.reset_mock()
        callbacks['p']()
        enqueue.assert_not_called()

    def test_selected_model_and_language_are_passed_explicitly(self):
        from types import SimpleNamespace
        from voice_to_clipboard.core.hotkey_session import SessionLauncher
        args = SimpleNamespace(model=None, inference_device='cpu', no_overlay=True)
        launcher = SessionLauncher(args)
        with patch('voice_to_clipboard.core.hotkey_session.try_stop_running', return_value=False), patch('voice_to_clipboard.core.hotkey_session.spawn_background') as spawn:
            launcher.launch('pl', model='small')
            command = spawn.call_args.args[0]
            self.assertEqual(command[command.index('--model') + 1], 'small')
            self.assertEqual(command[command.index('--lang') + 1], 'pl')
            launcher.children.clear()
            launcher.launch('en')
            command = spawn.call_args.args[0]
            self.assertEqual(command[command.index('--model') + 1], 'large-v3-turbo')
