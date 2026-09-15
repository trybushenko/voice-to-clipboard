"""Selective Quartz keyboard interception and Accessibility guarded paste."""
import subprocess
import time


def focus_probe():
    from ApplicationServices import (AXIsProcessTrusted, AXUIElementCreateSystemWide,
                                      AXUIElementCopyAttributeValue)
    from CoreFoundation import CFEqual
    if not AXIsProcessTrusted():
        raise RuntimeError('Allow Accessibility for Python/terminal in System Settings')
    system = AXUIElementCreateSystemWide()
    initial = [None]
    generation = [0]
    def snapshot():
        status, element = AXUIElementCopyAttributeValue(system, 'AXFocusedUIElement', None)
        if status or element is None:
            return None
        if initial[0] is None:
            initial[0] = element
        elif not CFEqual(initial[0], element):
            generation[0] += 1
        return generation[0]
    return snapshot


def send_paste(expected, guard):
    import Quartz as q
    deadline = time.monotonic() + 2
    flags = q.kCGEventFlagMaskAlternate | q.kCGEventFlagMaskShift | q.kCGEventFlagMaskControl | q.kCGEventFlagMaskCommand
    while q.CGEventSourceFlagsState(q.kCGEventSourceStateCombinedSessionState) & flags:
        guard.check()
        if time.monotonic() >= deadline:
            raise RuntimeError('Release modifiers and paste manually; text is in clipboard')
        time.sleep(.02)
    if subprocess.run(['pbpaste'], capture_output=True, check=True, timeout=2).stdout.decode('utf-8') != expected:
        raise RuntimeError('Clipboard changed; restore text with dictate --copy-last')
    guard.check()
    # Quartz posts Command+V; it does not press Enter or move focus.
    for pressed in (True, False):
        event = q.CGEventCreateKeyboardEvent(None, 9, pressed)
        q.CGEventSetFlags(event, q.kCGEventFlagMaskCommand)
        q.CGEventPost(q.kCGHIDEventTap, event)


def listener(callbacks, modifiers='alt+shift'):
    import Quartz as q
    from ApplicationServices import AXIsProcessTrusted
    from pynput import keyboard
    if not AXIsProcessTrusted():
        raise RuntimeError('Allow Accessibility for Python/terminal, then restart voice-hotkeys')
    if hasattr(q, 'CGPreflightListenEventAccess') and not q.CGPreflightListenEventAccess():
        raise RuntimeError('Allow Input Monitoring for Python/terminal, then restart voice-hotkeys')
    masks = {'alt': q.kCGEventFlagMaskAlternate, 'shift': q.kCGEventFlagMaskShift,
             'ctrl': q.kCGEventFlagMaskControl, 'win': q.kCGEventFlagMaskCommand}
    required = sum(masks[name] for name in modifiers.split('+'))
    all_modifiers = sum(masks.values())
    codes = {32: callbacks['u'], 14: callbacks['e'], 37: callbacks['l']}
    held = set()
    def intercept(kind, event):
        code = q.CGEventGetIntegerValueField(event, q.kCGKeyboardEventKeycode)
        if kind == q.kCGEventKeyUp and code in held:
            held.discard(code)
            return None
        if kind == q.kCGEventKeyDown and code in held:
            return None
        if (kind == q.kCGEventKeyDown and code in codes
                and q.CGEventGetFlags(event) & all_modifiers == required):
            held.add(code)
            codes[code]()
            return None
        return event
    return keyboard.Listener(darwin_intercept=intercept)
