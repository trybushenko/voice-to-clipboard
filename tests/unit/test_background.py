import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from voice_to_clipboard.platform import background, processes
from voice_to_clipboard.platform.focus import RemoteGuard
from voice_to_clipboard.core.hotkey_session import SessionLauncher


class BackgroundTests(unittest.TestCase):
    def test_no_console_uses_distinct_windows_policy(self):
        fake = SimpleNamespace(CREATE_NO_WINDOW=0x08000000, Popen=Mock())
        with patch.object(processes.sys, 'platform', 'win32'), patch.object(processes, 'subprocess', fake):
            processes.spawn_background(['python'], no_console=True)
        self.assertEqual(fake.Popen.call_args.kwargs['creationflags'], 0x08000000)

    def test_existing_background_host_is_reused(self):
        with patch('voice_to_clipboard.core.host_control.request', return_value={'pid': 42}), patch.object(background, 'spawn_background') as spawn:
            self.assertEqual(background.start([], Path('endpoint')), {'pid': 42})
        spawn.assert_not_called()

    def test_background_launch_redirects_console_and_reports_ready(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(background, 'data_dir', return_value=Path(folder)), patch('voice_to_clipboard.core.host_control.request', side_effect=[OSError(), {'pid': 42}]), patch.object(background, 'spawn_background') as spawn:
            spawn.return_value.poll.return_value = None
            self.assertEqual(background.start(['--no-overlay'], Path('endpoint')), {'pid': 42})
            options = spawn.call_args.kwargs
            self.assertTrue(options['no_console'])
            self.assertEqual(options['env']['DICTATE_BACKGROUND'], '1')
            self.assertIs(options['stdout'], options['stderr'])
            self.assertEqual((Path(folder)/'logs/hotkeys.log').read_text(), '')

    def test_session_monitor_survives_launch_and_token_expires(self):
        args = SimpleNamespace(model=None, inference_device='cpu', no_overlay=True)
        process, guard = Mock(), Mock()
        process.poll.return_value = None
        with patch('voice_to_clipboard.core.hotkey_session.try_stop_running', return_value=False), patch('voice_to_clipboard.core.hotkey_session.spawn_background', return_value=process) as spawn, patch('voice_to_clipboard.platform.focus.make_guard', return_value=guard), patch.dict(os.environ, DICTATE_BACKGROUND='1'):
            launcher = SessionLauncher(args)
            launcher.launch('uk', True)
            token = spawn.call_args.kwargs['env']['DICTATE_PASTE_TOKEN']
            self.assertTrue(spawn.call_args.kwargs['no_console'])
            guard.close.assert_not_called()
            self.assertEqual(launcher.check_paste(token), {'ok': True})
            with self.assertRaises(RuntimeError):
                launcher.check_paste('wrong token')
            guard.changed = True
            guard.check.side_effect = RuntimeError('changed')
            with self.assertRaises(RuntimeError):
                launcher.check_paste(token)
            process.poll.return_value = 0
            launcher.tick()
            guard.close.assert_called_once()
            with self.assertRaises(RuntimeError):
                launcher.check_paste(token)

    def test_remote_guard_never_recaptures_when_host_fails(self):
        with patch('voice_to_clipboard.core.host_control.request', side_effect=OSError()):
            with self.assertRaisesRegex(RuntimeError, 'clipboard'):
                RemoteGuard('token', 'endpoint').check()

    @unittest.skipUnless(sys.platform == 'win32', 'Windows console attachment')
    def test_real_child_has_no_console(self):
        import subprocess
        process = processes.spawn_background([sys.executable, '-c', 'import ctypes; print(int(ctypes.windll.kernel32.GetConsoleWindow() or 0))'], no_console=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, errors = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, errors)
        self.assertEqual(output.strip(), b'0')
