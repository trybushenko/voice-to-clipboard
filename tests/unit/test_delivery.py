import ctypes
from pathlib import Path
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from voice_to_clipboard.platform.windows_input import INPUT, KEYBDINPUT, send_paste
from voice_to_clipboard.platform.focus import FocusGuard, UnavailableGuard
from voice_to_clipboard.core import hotkey_session, settings


class DeliveryTests(unittest.TestCase):
    def guard(self):
        return SimpleNamespace(check=Mock(), target=None)

    def api(self, count=4):
        return SimpleNamespace(GetAsyncKeyState=Mock(return_value=0), SendInput=Mock(return_value=count))

    def test_input_layout_and_unicode_clipboard_contract(self):
        self.assertEqual(ctypes.sizeof(INPUT), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
        self.assertEqual(ctypes.sizeof(KEYBDINPUT), 24 if ctypes.sizeof(ctypes.c_void_p) == 8 else 16)
        api = self.api()
        send_paste('Привіт 👋', self.guard(), api, lambda: 'Привіт 👋')
        size, events, structure_size = api.SendInput.call_args.args
        self.assertEqual(size, 4)
        self.assertEqual([(e.ki.wVk, e.ki.dwFlags) for e in events], [(17, 0), (86, 0), (86, 2), (17, 2)])
        self.assertEqual(structure_size, ctypes.sizeof(INPUT))

    def test_held_modifier_never_injects(self):
        api = self.api(); api.GetAsyncKeyState.return_value = 0x8000
        with self.assertRaisesRegex(RuntimeError, 'Release'):
            send_paste('text', self.guard(), api, lambda: 'text', timeout=0)
        api.SendInput.assert_not_called()

    def test_changed_clipboard_never_injects(self):
        api = self.api()
        with self.assertRaisesRegex(RuntimeError, 'Clipboard changed'):
            send_paste('text', self.guard(), api, lambda: 'different')
        api.SendInput.assert_not_called()

    def test_changed_target_never_injects(self):
        api = self.api()
        with self.assertRaises(RuntimeError):
            send_paste('text', UnavailableGuard(), api, lambda: 'text')
        api.SendInput.assert_not_called()

    def test_blocked_and_partial_input_are_reported(self):
        for count in (0, 1, 2, 3):
            api = self.api(count)
            with self.subTest(count=count), self.assertRaisesRegex(RuntimeError, 'blocked or incomplete'):
                send_paste('text', self.guard(), api, lambda: 'text')
            if count:
                cleanup = api.SendInput.call_args.args[1]
                self.assertTrue(all(e.ki.dwFlags == 2 for e in cleanup))
            else:
                self.assertEqual(api.SendInput.call_count, 1)

    def test_guard_change_is_sticky_even_after_return(self):
        current = ['first']
        guard = FocusGuard(lambda: lambda: current[0], interval=.005)
        try:
            guard.check()
            current[0] = 'other'
            deadline = time.monotonic() + 1
            while not guard.changed and time.monotonic() < deadline:
                time.sleep(.005)
            self.assertTrue(guard.changed)
            current[0] = 'first'
            with self.assertRaises(RuntimeError):
                guard.check()
        finally:
            guard.close()
        self.assertFalse(guard.thread.is_alive())

    def test_guard_rejects_initial_mismatch_and_unavailable_probe(self):
        for factory, expected in ((lambda: lambda: 'other', 'first'), (lambda: lambda: None, None)):
            guard = FocusGuard(factory, expected, interval=.005)
            try:
                with self.assertRaises(RuntimeError):
                    guard.check()
            finally:
                guard.close()

    def test_mixed_shortcut_stops_without_changing_original_action(self):
        args = SimpleNamespace(model=None, inference_device='auto', no_overlay=True)
        process = Mock(); process.poll.return_value = None
        with patch.object(hotkey_session, 'try_stop_running', return_value=False) as stop, patch.object(hotkey_session, 'spawn_background', return_value=process) as spawn, patch.object(hotkey_session.sys, 'platform', 'linux'), patch('voice_to_clipboard.platform.focus.make_guard'):
            launcher = hotkey_session.SessionLauncher(args)
            launcher.launch('uk', True)
            launcher.launch('en', False)
            self.assertEqual(spawn.call_count, 1)
            self.assertIn('--paste', spawn.call_args.args[0])
            self.assertEqual(spawn.call_args.args[0][spawn.call_args.args[0].index('--lang') + 1], 'uk')
            self.assertTrue(launcher.pending_stop)
            stop.return_value = True
            launcher.tick()
            self.assertFalse(launcher.pending_stop)

    def test_settings_round_trip_preserves_other_preferences(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, 'data_dir', return_value=Path(directory)):
            self.assertEqual(settings.read_modifiers(), 'alt+shift')
            (Path(directory)/'settings.json').write_text('{"other": 42}')
            settings.save_modifiers('ctrl+alt')
            self.assertEqual(settings.read_modifiers(), 'ctrl+alt')
            self.assertIn('42', (Path(directory)/'settings.json').read_text())
