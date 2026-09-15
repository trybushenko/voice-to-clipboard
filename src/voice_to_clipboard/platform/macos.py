"""Selective Quartz keyboard interception and Accessibility guarded paste."""
import subprocess
import time


def focus_probe():
    import ApplicationServices as ax
    import CoreFoundation as cf
    if not ax.AXIsProcessTrusted():
        raise RuntimeError('Allow Accessibility for Python/terminal in System Settings')
    system = ax.AXUIElementCreateSystemWide()
    status, initial = ax.AXUIElementCopyAttributeValue(system, 'AXFocusedUIElement', None)
    if status or initial is None:
        raise RuntimeError('Focused field is unavailable')
    status, pid = ax.AXUIElementGetPid(initial, None)
    if status:
        raise RuntimeError('Focused application is unavailable')
    application = ax.AXUIElementCreateApplication(pid)
    changed = [False]
    def event(observer, element, notification, context):
        if not cf.CFEqual(initial, element):
            changed[0] = True
    status, observer = ax.AXObserverCreate(pid, event, None)
    if status:
        raise RuntimeError('Focus notifications unavailable; paste manually')
    notification = 'AXFocusedUIElementChanged'
    status = ax.AXObserverAddNotification(observer, application, notification, None)
    if status:
        raise RuntimeError('Application does not support focus notifications; paste manually')
    source = ax.AXObserverGetRunLoopSource(observer)
    loop = cf.CFRunLoopGetCurrent()
    cf.CFRunLoopAddSource(loop, source, cf.kCFRunLoopDefaultMode)
    def snapshot():
        cf.CFRunLoopRunInMode(cf.kCFRunLoopDefaultMode, .001, False)
        status, element = ax.AXUIElementCopyAttributeValue(system, 'AXFocusedUIElement', None)
        if status or element is None or not cf.CFEqual(initial, element):
            changed[0] = True
        return None if changed[0] else pid
    def close():
        ax.AXObserverRemoveNotification(observer, application, notification)
        cf.CFRunLoopRemoveSource(loop, source, cf.kCFRunLoopDefaultMode)
    snapshot.close = close
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
