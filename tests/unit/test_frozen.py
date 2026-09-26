import io
import sys
import unittest
from unittest.mock import patch
from voice_to_clipboard.platform.frozen import dispatch, module_command
from voice_to_clipboard.platform import launchers


class FrozenTests(unittest.TestCase):
    def test_stream_restore_preserves_existing_pipes(self):
        from voice_to_clipboard.platform.frozen import restore_standard_streams
        stream = io.StringIO()
        with patch.object(sys, 'stdin', stream), patch.object(sys, 'stdout', stream), patch.object(sys, 'stderr', stream):
            restore_standard_streams()
            self.assertIs(sys.stdin, stream)
            self.assertIs(sys.stdout, stream)
            self.assertIs(sys.stderr, stream)

    def test_source_and_frozen_commands_preserve_arguments(self):
        for frozen, flag in [(False, '-m'), (True, '--app-module')]:
            with patch.object(sys, 'frozen', frozen, create=True):
                self.assertEqual(module_command('voice_to_clipboard', '--model', 'path with spaces'),
                    [sys.executable, flag, 'voice_to_clipboard', '--model', 'path with spaces'])

    def test_dispatch_does_not_start_desktop_for_worker(self):
        with patch('runpy.run_module') as run, patch.object(sys, 'argv', []):
            dispatch(['--app-module', 'voice_to_clipboard.worker.service'])
            run.assert_called_once_with('voice_to_clipboard.worker.service', run_name='__main__')
            self.assertEqual(sys.argv, [sys.executable])

    def test_unknown_or_missing_route_fails_closed(self):
        with patch('runpy.run_module') as run:
            for args in [['--app-module'], ['--app-module', 'os']]:
                with self.assertRaises(ValueError):
                    dispatch(args)
            run.assert_not_called()

    def test_frozen_macos_launcher_remains_guarded(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'darwin'):
            self.assertEqual(launchers.command(), module_command('voice_to_clipboard.ui.desktop_app', '--run'))
            with self.assertRaises(RuntimeError):
                launchers.install()
            launchers.set_enabled(False)


if __name__ == '__main__':
    unittest.main()


class CpuBundleTests(unittest.TestCase):
    def test_cpu_bundle_auto_never_probes_cuda_and_explicit_cuda_explains(self):
        from voice_to_clipboard.backends.faster_whisper import resolve_device
        from unittest.mock import Mock
        count = Mock(return_value=1)
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'win32'):
            self.assertEqual(resolve_device('auto', count), 'cpu')
            self.assertEqual(resolve_device('cpu', count), 'cpu')
            with self.assertRaisesRegex(ValueError, 'CPU only'):
                resolve_device('cuda', count)
            count.assert_not_called()
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(resolve_device('auto', count), 'cuda')

    def test_frozen_windows_autostart_can_be_enabled_and_disabled(self):
        from unittest.mock import Mock
        registry = Mock()
        registry.CreateKey.return_value.__enter__ = Mock(return_value='key')
        registry.CreateKey.return_value.__exit__ = Mock(return_value=False)
        with patch.dict(sys.modules, winreg=registry), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'win32'), patch.object(launchers, 'install'):
            launchers.set_enabled(True)
            self.assertIn('--app-module', registry.SetValueEx.call_args.args[-1])
            launchers.set_enabled(False)
            registry.DeleteValue.assert_called_once_with('key', launchers.APP_ID)
