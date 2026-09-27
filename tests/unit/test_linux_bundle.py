from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from voice_to_clipboard.platform import launchers
from voice_to_clipboard.backends.faster_whisper import resolve_device


class LinuxBundleTests(unittest.TestCase):
    def test_linux_cpu_bundle_and_source_selection(self):
        count = Mock(return_value=1)
        with patch.object(sys, 'platform', 'linux'), patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(resolve_device('auto', count), 'cpu')
            self.assertEqual(resolve_device('cpu', count), 'cpu')
            with self.assertRaisesRegex(ValueError, 'source installation'):
                resolve_device('cuda', count)
            count.assert_not_called()
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(resolve_device('auto', count), 'cuda')

    def test_startup_ownership_and_uninstall_preserve_other_installations(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder).resolve()
            exe = home / 'opt/VoiceToClipboard'
            exe.parent.mkdir()
            exe.write_bytes(b'runtime')
            launcher = home / 'system.desktop'
            launcher.write_text('system owned')
            startup = home / 'autostart/voice-to-clipboard.desktop'
            user_launcher = home / 'user.desktop'
            history = home / 'history.json'
            history.write_bytes(b'private data')
            with patch.object(sys, 'platform', 'linux'), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(exe)), patch.object(launchers, 'LINUX_EXECUTABLE', exe), patch.object(launchers, 'LINUX_LAUNCHER', launcher), patch.object(launchers, 'autostart_path', return_value=startup), patch.object(launchers, 'launcher_path', return_value=user_launcher):
                self.assertEqual(launchers.install(), launcher)
                self.assertFalse(user_launcher.exists())
                launchers.set_enabled(True)
                launchers.set_enabled(True)
                self.assertTrue(launchers.enabled())
                self.assertEqual(len(list(startup.parent.iterdir())), 1)
                self.assertIn('TryExec=' + str(exe), startup.read_text())
                frozen_entry = startup.read_bytes()
                launchers.uninstall()
                self.assertFalse(startup.exists())
                self.assertEqual(exe.read_bytes(), b'runtime')
                self.assertEqual(launcher.read_text(), 'system owned')
                self.assertEqual(history.read_bytes(), b'private data')
                # A later source install owns the same single startup slot.
                with patch.object(sys, 'frozen', False):
                    launchers.set_enabled(True)
                    source_entry = startup.read_bytes()
                launchers.uninstall()
                self.assertEqual(startup.read_bytes(), source_entry)
                startup.write_bytes(frozen_entry)
                with patch.object(sys, 'frozen', False):
                    launchers.set_enabled(False)
                self.assertEqual(startup.read_bytes(), frozen_entry)
                startup.write_text('unrelated desktop file')
                launchers.set_enabled(False)
                self.assertEqual(startup.read_text(), 'unrelated desktop file')

    def test_uninstalled_bundle_cannot_enable_startup(self):
        with patch.object(sys, 'platform', 'linux'), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', '/tmp/preview/VoiceToClipboard'):
            with self.assertRaisesRegex(RuntimeError, 'Install the .deb'):
                launchers.set_enabled(True)

    def test_frozen_accessibility_helper_uses_dispatch(self):
        from voice_to_clipboard.platform.frozen import module_command, dispatch
        with patch.object(sys, 'frozen', True, create=True), patch('runpy.run_module') as run, patch.object(sys, 'argv', []):
            argv = module_command('voice_to_clipboard.platform.atspi_probe')
            dispatch(argv[1:])
            run.assert_called_once_with('voice_to_clipboard.platform.atspi_probe', run_name='__main__')

    def test_external_environment_restores_system_libraries_without_mutation(self):
        import os
        from voice_to_clipboard.platform.processes import external_environment
        with patch.object(sys, 'platform', 'linux'), patch.object(sys, 'frozen', True, create=True):
            with patch.dict(os.environ, {'LD_LIBRARY_PATH': '/bundle'}, clear=True):
                self.assertNotIn('LD_LIBRARY_PATH', external_environment())
                self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/bundle')
            with patch.dict(os.environ, {'LD_LIBRARY_PATH': '/bundle', 'LD_LIBRARY_PATH_ORIG': '/system'}, clear=True):
                self.assertEqual(external_environment()['LD_LIBRARY_PATH'], '/system')
        with patch.object(sys, 'frozen', False, create=True):
            self.assertIsNone(external_environment())
