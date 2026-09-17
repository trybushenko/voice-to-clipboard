# Stage C implementation and verification

> Оновлення 2026-09-15: завершальна реалізація B/C додала background/no-console,
> безперервний host focus guard і native focus events. Поточний стан —
> [ревізія A/B/C](abc-audit.md); [повний Windows-гайд](../setup/windows-stage-c-test.md).
> Нижче збережена історія попередніх перевірок; її відкриті implementation-пункти
> замінено актуальним checklist головного плану. Ручне Windows/macOS приймання нових змін відкрите.


Implementation branch: `codex/windows-hotkeys-paste`. Most code is implemented, but the focus/portal limits below remain open work.
Physical Windows/macOS acceptance is not claimed completed from Linux.
See the corrected [A/B/C audit](abc-audit.md); C is not fully accepted.

## Implemented

- Windows RegisterHotKey/WM_HOTKEY, MOD_NOREPEAT, bounded loop, explicit conflicts
  and complete registration cleanup. No global suppression of ordinary typing.
- macOS Quartz event-tap interception through pynput: only configured U/E/L key
  down/up events are suppressed, including repeat filtering; Accessibility and
  Input Monitoring preflight checks.
- Linux X11 passive grabs, Caps/NumLock variants, repeat handling, conflict cleanup.
  Existing GNOME bindings remain valid; use one host for any given shortcut.
- Configurable modifiers persisted in user settings after successful registration.
  Windows layout-switch conflict detection; system preferences are never changed.
- One session launcher with queued actions: a second shortcut stops the original
  session, including while its process is starting; its language/paste mode is fixed.
- Windows SendInput with 32/64-bit-correct ctypes INPUT union, bounded modifier and
  clipboard waits, clipboard-content verification, partial/blocked input reporting.
- Windows original field/window captured via UI Automation and tracked throughout
  recording/transcription. Changed/inaccessible targets become clipboard-only.
- macOS Accessibility focused-element tracking and Command+V; X11 window focus
  plus navigation/click observation and XTEST Ctrl+V without clearing modifiers.
- Sticky focus invalidation and fresh check before input; no arbitrary focus/caret
  restoration. Unavailable field verification fails to clipboard-only delivery.
- Distinct copied/input-sent/fallback messages in console and a short result overlay.
- Wayland checks whether the GlobalShortcuts portal interface is exposed, explains
  the supported desktop-binding/manual-paste fallback. Portal binding and automatic
  Wayland injection are not implemented or advertised as supported.

## Checks

- Baseline C: 48 automated tests; A/B/C audit revision: 53 tests, including
  control IPC/pause/resume and registry cases. Native-only cases skip on other OSes.
- Windows CI checks real UI Automation and SendInput binding construction in addition
  to mocked blocked-input, modifier, clipboard, focus and hotkey-conflict tests.
- macOS CI checks native Accessibility/Quartz symbol availability.
- Linux GUI `scripts/check_paste.py --auto`: exact Unicode inserted once in the
  test field and focus retained. No microphone/model involved.
- GUI utility available for user-run Windows/macOS validation; Notepad/browser/VS
  Code physical hotkey and paste matrix remains a required acceptance check.

## Limits to verify explicitly

Polling cannot guarantee detection of every instantaneous focus change. UI Automation
providers differ between editors; inaccessible fields safely fall back to clipboard.
On X11, field-navigation clicks/keys are observed conservatively, but a programmatic
field change inside one native window may not be detectable. On macOS, capture begins
in the recording process; verify very fast field switches during startup. On Windows,
field identity is captured in the host before launching a paste session.

UIPI, secure desktops and applications rejecting synthetic paste are not bypassed.
No automatic Enter is generated. Model accuracy, installers and tray/autostart remain
separate work. Native desktop acceptance is tracked by the Windows guide rather than
inferred from a successful SendInput return value.

## Primary API references

- [Microsoft RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey)
- [Microsoft SendInput and UIPI](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)
- [Microsoft GetFocusedElement](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomation-getfocusedelement)
- [pynput selective event suppression](https://pynput.readthedocs.io/en/latest/faq.html)
