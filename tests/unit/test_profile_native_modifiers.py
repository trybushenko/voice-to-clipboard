"""Per-profile Quartz matching without requiring macOS permissions."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from voice_to_clipboard.platform.macos import listener


class ProfileNativeModifiersTests(unittest.TestCase):
    def test_quartz_matches_each_profile_and_suppresses_repeat(self):
        quartz = SimpleNamespace(kCGEventFlagMaskAlternate=1, kCGEventFlagMaskShift=2,
                                 kCGEventFlagMaskControl=4, kCGEventFlagMaskCommand=8,
                                 kCGEventKeyUp=10, kCGEventKeyDown=11, kCGKeyboardEventKeycode=0,
                                 CGEventGetIntegerValueField=lambda event, field: event['code'],
                                 CGEventGetFlags=lambda event: event['flags'])
        keyboard = SimpleNamespace(Listener=Mock())
        callbacks = {'e': Mock(), 'p': Mock()}
        with patch.dict('sys.modules', {'Quartz': quartz,
                         'ApplicationServices': SimpleNamespace(AXIsProcessTrusted=lambda: True),
                         'pynput': SimpleNamespace(keyboard=keyboard)}):
            listener(callbacks, {'e': 'alt+shift', 'p': 'ctrl+alt'})
        intercept = keyboard.Listener.call_args.kwargs['darwin_intercept']
        wrong = {'code': 35, 'flags': 3}
        self.assertIs(intercept(11, wrong), wrong)
        callbacks['p'].assert_not_called()
        for key, code, flags in [('e', 14, 3), ('p', 35, 5)]:
            event = {'code': code, 'flags': flags}
            self.assertIsNone(intercept(11, event))
            self.assertIsNone(intercept(11, event))
            callbacks[key].assert_called_once()
            self.assertIsNone(intercept(10, event))
