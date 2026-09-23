"""Exercise real Tk Add/Apply/close and Quit, with an isolated simulated host."""
import os
import tempfile
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from unittest.mock import patch
from voice_to_clipboard.core.desktop_settings import load, validate
from voice_to_clipboard.core.settings import save_settings
from voice_to_clipboard.ui import desktop_panel


def main():
    errors = []
    original_loop = tk.Tk.mainloop
    with tempfile.TemporaryDirectory(prefix='vtc-panel-', dir=None if os.name == 'nt' else '/tmp') as folder, patch.dict(os.environ, VOICE_TO_CLIPBOARD_DATA_DIR=folder, VOICE_TO_CLIPBOARD_CACHE_DIR=folder):
        malformed_reply = [False]
        def request(path, operation, **details):
            if operation == 'settings':
                time.sleep(.3)  # Close immediately after Apply must wait for this acknowledgment.
                save_settings(validate(details['values']))
                if malformed_reply[0]:
                    malformed_reply[0] = False
                    return {'state': 'listening'}
            return {'state': 'stopping' if operation == 'quit' else 'listening',
                    'phase': 'idle', 'message': '', 'dictation_processes': 0,
                    'profiles': load()['profiles'], 'profile_modifiers': True}
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        def drive(root, quit_only=False, recover=False):
            def action():
                try:
                    widgets = list(descendants(root))
                    buttons = {w.cget('text'): w for w in widgets if isinstance(w, ttk.Button)}
                    if quit_only:
                        buttons['Quit app (finish recording)'].invoke()
                        return
                    combo = next(w for w in widgets if isinstance(w, ttk.Combobox) and 'Polish (pl)' in w.cget('values'))
                    combo.set('Polish (pl)')
                    key = next(w for w in widgets if isinstance(w, ttk.Entry) and str(w.cget('width')) == '4')
                    key.delete(0, 'end'); key.insert(0, 'p')
                    modifier_choice = next(w for w in widgets if isinstance(w, ttk.Combobox)
                                           and tuple(w.cget('values')) == ('', 'alt+shift', 'ctrl+alt', 'ctrl+alt+shift'))
                    modifier_choice.set('ctrl+alt')
                    buttons['Add'].invoke()
                    buttons['Apply all settings and profiles'].invoke()
                    def close_after_apply():
                        if recover:
                            buttons['Apply all settings and profiles'].invoke()
                        root.tk.call(root.protocol('WM_DELETE_WINDOW'))
                    if recover:
                        root.after(1200, close_after_apply)
                    else:
                        close_after_apply()
                except Exception as exc:
                    errors.append(str(exc))
                    root.destroy()
            def timeout():
                errors.append('Panel failed to close without another interaction')
                root.destroy()
            root.report_callback_exception = lambda *args: errors.append(str(args))
            root.after(1100, action)
            timeout_id = root.after(6000, timeout)
            original_loop(root)
            try:
                root.after_cancel(timeout_id)
            except tk.TclError:
                pass
        with patch('voice_to_clipboard.core.host_control.request', side_effect=request), patch('voice_to_clipboard.platform.launchers.enabled', return_value=False), patch('tkinter.messagebox.showerror', side_effect=lambda *args, **kwargs: errors.append(str(args))):
            with patch.object(tk.Tk, 'mainloop', drive):
                desktop_panel.main()
                import gc
                gc.collect()  # Collect destroyed Tcl interpreters on their owning thread.
            assert [p['language'] for p in load()['profiles']] == ['en', 'pl'], load()
            assert load()['profiles'][1]['modifiers'] == 'alt+ctrl', load()
            save_settings({'profiles': [{'language': 'en', 'key': 'e', 'paste': False, 'model': ''}]})
            malformed_reply[0] = True
            with patch.object(tk.Tk, 'mainloop', lambda root: drive(root, recover=True)):
                desktop_panel.main()
                import gc
                gc.collect()  # Collect destroyed Tcl interpreters on their owning thread.
            assert [p['language'] for p in load()['profiles']] == ['en', 'pl']
            with patch.object(tk.Tk, 'mainloop', lambda root: drive(root, quit_only=True)):
                desktop_panel.main()
                import gc
                gc.collect()  # Collect destroyed Tcl interpreters on their owning thread.
        assert not errors, errors
        print('PASS: real Tk Add, Apply followed immediately by close, saved profile reload, and Quit without extra clicks')


if __name__ == '__main__':
    main()
