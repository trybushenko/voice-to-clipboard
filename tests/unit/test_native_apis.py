"""Validate native ABI/bindings on their CI operating systems without typing."""
import sys
import unittest


class NativeAPITests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'Windows native API')
    def test_windows_uia_and_sendinput_bindings(self):
        from voice_to_clipboard.platform.windows_input import api
        from voice_to_clipboard.platform.focus import windows_probe
        from voice_to_clipboard.platform.windows_hotkeys import user_api, layout_conflict
        self.assertTrue(callable(api().SendInput))
        self.assertTrue(callable(user_api().RegisterHotKey))
        self.assertIsInstance(layout_conflict('alt+shift'), bool)
        import comtypes
        import threading
        errors = []
        def exercise():
            try:
                probe = windows_probe()
                probe.close()
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=exercise)
        thread.start()
        thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS native API')
    def test_macos_accessibility_and_quartz_bindings(self):
        import ApplicationServices as ax
        import Quartz as q
        import CoreFoundation as cf
        for name in ('AXIsProcessTrusted', 'AXUIElementCreateSystemWide', 'AXUIElementCopyAttributeValue'):
            self.assertTrue(callable(getattr(ax, name)))
        self.assertTrue(callable(q.CGEventCreateKeyboardEvent))
        self.assertTrue(callable(cf.CFEqual))
