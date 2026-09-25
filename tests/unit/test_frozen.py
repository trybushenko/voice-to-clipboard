import sys
import unittest
from unittest.mock import patch
from voice_to_clipboard.platform.frozen import dispatch, module_command
from voice_to_clipboard.platform import launchers


class FrozenTests(unittest.TestCase):
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

    def test_frozen_launcher_does_not_require_pythonw_or_overwrite_app(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'win32'):
            self.assertEqual(launchers.command(), module_command('voice_to_clipboard.ui.desktop_app', '--run'))
            with self.assertRaises(RuntimeError):
                launchers.install()
            with self.assertRaises(RuntimeError):
                launchers.set_enabled(False)


if __name__ == '__main__':
    unittest.main()
