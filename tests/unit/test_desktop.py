import io
import json
import logging
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from voice_to_clipboard.core import desktop_settings, session_status, app_logging
from voice_to_clipboard.core.hotkey_session import SessionLauncher
from voice_to_clipboard.platform import launchers
from voice_to_clipboard.ui import terminal


class DesktopTests(unittest.TestCase):
    def test_macos_quit_is_queued_until_native_loop_dispatches(self):
        from voice_to_clipboard.ui.desktop_app import stop_icon, dispatch_tray
        pending = []
        helper = SimpleNamespace(callAfter=pending.append)
        icon = Mock()
        with patch('sys.platform', 'darwin'), patch.dict('sys.modules', {
                'PyObjCTools': SimpleNamespace(AppHelper=helper)}):
            dispatch_tray(icon.update_menu)
            stop_icon(icon)
        icon.update_menu.assert_not_called()
        icon.stop.assert_not_called()
        self.assertEqual(len(pending), 2)
        pending.pop(0)()
        icon.update_menu.assert_called_once()
        pending.pop(0)()
        icon.stop.assert_called_once()

    def test_settings_reject_invalid_values(self):
        for values in ([], {'hotkey_modifiers': 'alt+banana'}, {'overlay': 'yes'}, {'model': 42}, {'inference_device': 'gpu'}):
            with self.assertRaises((ValueError, TypeError)):
                desktop_settings.validate(values)
        self.assertEqual(desktop_settings.validate({})['inference_device'], 'auto')

    def test_status_is_atomic_and_has_no_audio_or_transcript(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'
            with patch.dict(os.environ, DICTATE_STATUS_PATH=str(path)):
                session_status.publish('recording', 'Microphone is recording')
                value = json.loads(path.read_text())
                self.assertEqual(value, {'state': 'recording', 'message': 'Microphone is recording'})
                session_status.publish('invalid', 'must not replace')
                self.assertEqual(json.loads(path.read_text()), value)
            self.assertEqual(len(list(Path(folder).iterdir())), 1)

    def test_technical_stream_never_contains_transcript_or_error_payload(self):
        output = io.StringIO()
        with patch.dict(os.environ, DICTATE_TECHNICAL_ONLY='1'), patch.object(terminal.sys, 'stderr', output):
            terminal.emit('  › private transcript', False)
            terminal.emit('[error] private provider payload', False)
            terminal.emit('[delivery] arbitrary payload', False)
        self.assertNotIn('private', output.getvalue())
        self.assertEqual([json.loads(row)['event'] for row in output.getvalue().splitlines()], ['error', 'delivery'])

    def test_process_log_drops_unstructured_text(self):
        process = Mock(stderr=io.BytesIO(b'private transcript\n{"event":"retry"}\n{"event":"private"}\n'))
        with self.assertLogs('voice_to_clipboard.desktop', level='INFO') as captured:
            thread = app_logging.collect_process(process, 'dictation')
            thread.join(2)
        text = '\n'.join(captured.output)
        self.assertIn('event=retry', text)
        self.assertNotIn('private', text)

    def test_log_rotation_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app_logging, 'data_dir', return_value=Path(folder)):
            logger = app_logging.configure()
            handler = logger.handlers[-1]
            handler.maxBytes = 100
            try:
                for _ in range(20):
                    logger.info('technical metadata ' * 4)
                self.assertLessEqual(len(list((Path(folder)/'logs').iterdir())), 4)
            finally:
                handler.close()
                logger.removeHandler(handler)

    def test_desktop_states_and_owned_process_shutdown(self):
        with tempfile.TemporaryDirectory() as folder, patch('voice_to_clipboard.platform.paths.cache_dir', return_value=Path(folder)):
            launcher = SessionLauncher(SimpleNamespace(desktop=True))
            runtime = launcher.runtime
            process = Mock(); process.poll.return_value = None
            worker = Mock(); worker.poll.return_value = None
            launcher.children, launcher.worker = [process], worker
            launcher.status_path = runtime / 'session.json'
            for state in ('recording', 'transcribing', 'delivered'):
                launcher.status_path.write_text(json.dumps({'state': state, 'message': state}))
                launcher.tick()
                self.assertEqual(launcher.state, state)
            launcher.shutdown()
            process.terminate.assert_called_once()
            worker.terminate.assert_called_once()
            self.assertFalse(runtime.exists())

    def test_failed_child_retains_actionable_reported_error(self):
        with tempfile.TemporaryDirectory() as folder, patch('voice_to_clipboard.platform.paths.cache_dir', return_value=Path(folder)):
            launcher = SessionLauncher(SimpleNamespace(desktop=True))
            child = Mock(); child.poll.return_value = 1
            launcher.children = [child]
            launcher.status_path = launcher.runtime / 'session.json'
            launcher.status_path.write_text(json.dumps({'state': 'error', 'message': 'Microphone unavailable'}))
            with patch('builtins.print'):
                launcher.tick()
            self.assertEqual(launcher.message, 'Microphone unavailable')
            launcher.shutdown()

    def test_desktop_capture_precedes_worker_start_and_stop_is_private(self):
        args = SimpleNamespace(desktop=True, inference_device='cpu', model=None, no_overlay=True)
        with tempfile.TemporaryDirectory() as folder, patch('voice_to_clipboard.platform.paths.cache_dir', return_value=Path(folder)), patch('voice_to_clipboard.core.hotkey_session.try_stop_running', return_value=False) as stop:
            launcher = SessionLauncher(args)
            child = Mock(); child.poll.return_value = None
            child.stderr = io.BytesIO()
            order = []
            guard = Mock()
            def capture(**kwargs):
                order.append('capture')
                return guard
            with patch('voice_to_clipboard.platform.focus.make_guard', side_effect=capture), patch.object(launcher, '_ensure_worker', side_effect=lambda: order.append('worker')), patch('voice_to_clipboard.core.hotkey_session.spawn_background', return_value=child) as spawn, patch.dict(os.environ, DICTATE_BACKGROUND='1'):
                launcher.launch('uk', True)
                self.assertEqual(order, ['capture', 'worker'])
                stop.assert_not_called()
                self.assertEqual(spawn.call_args.kwargs['env']['DICTATE_SESSION_ENDPOINT'], str(launcher.runtime/'dictate.sock'))
                launcher.pending_stop = True
                launcher.tick()
                stop.assert_called_once_with(str(launcher.runtime/'dictate.sock'))
                launcher.shutdown()

    def test_unresponsive_owned_process_is_killed(self):
        child = Mock(); child.poll.return_value = None
        child.wait.side_effect = [subprocess.TimeoutExpired('child', 2), 0]
        SessionLauncher._terminate(child)
        child.terminate.assert_called_once()
        child.kill.assert_called_once()

    def test_linux_launcher_and_autostart_are_reversible_and_quoted(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(launchers.sys, 'platform', 'linux'), patch.object(launchers, 'launcher_path', return_value=Path(folder)/'applications/app.desktop'), patch.object(launchers, 'autostart_path', return_value=Path(folder)/'autostart/app.desktop'), patch.object(launchers, 'command', return_value=['/some path/$cash%/python', '-m', 'app']):
            path = launchers.install()
            self.assertIn('"/some path/\\$cash%%/python"', path.read_text())
            launchers.set_enabled(True)
            self.assertTrue(launchers.enabled())
            launchers.set_enabled(True)
            self.assertEqual(len(list((Path(folder)/'autostart').iterdir())), 1)
            launchers.set_enabled(False)
            self.assertFalse(launchers.enabled())
            self.assertTrue(path.exists())
            launchers.uninstall()
            self.assertFalse(path.exists())

    def test_macos_bundle_and_launchagent_are_stable_and_reversible(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(launchers.sys, 'platform', 'darwin'), patch.object(launchers, 'launcher_path', return_value=Path(folder)/'Voice.app'), patch.object(launchers, 'autostart_path', return_value=Path(folder)/'agent.plist'), patch.object(launchers, 'command', return_value=['/path with spaces/python', '-m', 'app', '--run']):
            path = launchers.install()
            info = plistlib.loads((path/'Contents/Info.plist').read_bytes())
            self.assertEqual(info['CFBundleIdentifier'], launchers.APP_ID)
            self.assertTrue(info['LSUIElement'])
            launchers.set_enabled(True)
            agent = plistlib.loads((Path(folder)/'agent.plist').read_bytes())
            self.assertFalse(agent['KeepAlive'])
            self.assertEqual(agent['ProgramArguments'], [str(path/'Contents/MacOS/VoiceToClipboard')])
            launchers.uninstall()
            self.assertFalse(path.exists())
            self.assertFalse((Path(folder)/'agent.plist').exists())

    def test_windows_autostart_uses_only_our_hkcu_value(self):
        registry = Mock()
        context = registry.CreateKey.return_value.__enter__ = Mock(return_value='key')
        registry.CreateKey.return_value.__exit__ = Mock(return_value=False)
        with patch.dict(sys.modules, winreg=registry), patch.object(launchers.sys, 'platform', 'win32'), patch.object(launchers, 'install'), patch.object(launchers, 'command', return_value=['C:\\Path with spaces\\pythonw.exe', '-m', 'app', '--run']):
            launchers.set_enabled(True)
            self.assertEqual(registry.SetValueEx.call_args.args[1], launchers.APP_ID)
            self.assertEqual(registry.SetValueEx.call_args.args[-1], subprocess.list2cmdline(launchers.command()))
            launchers.set_enabled(False)
            registry.DeleteValue.assert_called_once_with('key', launchers.APP_ID)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows shortcut COM')
    def test_windows_shortcut_installs_in_isolated_directory(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(launchers, 'launcher_path', return_value=Path(folder)/'Voice to Clipboard.lnk'):
            path = launchers.install()
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)
