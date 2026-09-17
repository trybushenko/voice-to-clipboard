import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from voice_to_clipboard.platform.windows_hotkeys import NativeHotkeys, parse_modifiers, MOD_NOREPEAT, WM_HOTKEY, layout_conflict


class WindowsHotkeyTests(unittest.TestCase):
    def test_register_dispatch_and_unregister(self):
        api = Mock()
        api.RegisterHotKey.return_value = True
        callback = Mock()
        listener = NativeHotkeys({'u': callback}, api_factory=lambda: api)
        def peek(message, *args):
            message._obj.message = WM_HOTKEY
            message._obj.wParam = 1
            listener.stop()
            return True
        api.PeekMessageW.side_effect = peek
        listener.start(); listener.join(timeout=2)
        self.assertFalse(listener.is_alive())
        self.assertIsNone(listener.error)
        callback.assert_called_once()
        api.RegisterHotKey.assert_called_once_with(None, 1, MOD_NOREPEAT | 5, ord('U'))
        api.UnregisterHotKey.assert_called_once_with(None, 1)

    def test_conflict_releases_previous_registrations(self):
        api = Mock()
        api.RegisterHotKey.side_effect = [True, False]
        listener = NativeHotkeys({'u': Mock(), 'e': Mock()}, api_factory=lambda: api)
        with self.assertRaisesRegex(RuntimeError, 'shortcut unavailable'):
            listener.start()
        api.UnregisterHotKey.assert_called_once_with(None, 1)

    def test_stop_while_idle(self):
        api = Mock(); api.PeekMessageW.return_value = False
        listener = NativeHotkeys({'u': Mock()}, api_factory=lambda: api)
        listener.start(); listener.stop(); listener.join(timeout=2)
        self.assertFalse(listener.is_alive())
        api.UnregisterHotKey.assert_called_once()

    def test_modifiers(self):
        self.assertEqual(parse_modifiers('ctrl+alt+shift'), 7)
        for value in ('', 'alt+alt', 'control+alt', 'u'):
            with self.assertRaises(ValueError):
                parse_modifiers(value)

    def test_layout_conflict_reads_modern_registry_values(self):
        key = Mock()
        key.__enter__ = Mock(return_value=key)
        key.__exit__ = Mock(return_value=False)
        def query(key, name):
            if name == 'Language Hotkey':
                return ('1', 1)
            raise FileNotFoundError(name)
        registry = SimpleNamespace(HKEY_CURRENT_USER=1, OpenKey=Mock(return_value=key), QueryValueEx=query)
        with patch.dict('sys.modules', {'winreg': registry}):
            self.assertTrue(layout_conflict('alt+shift'))
            self.assertFalse(layout_conflict('ctrl+alt'))
