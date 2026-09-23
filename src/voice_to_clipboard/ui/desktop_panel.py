"""Temporary settings/status window; never owns a second dictation controller."""
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading


def open_log():
    from ..core.app_logging import log_path
    path = log_path()
    if sys.platform == 'win32':
        os.startfile(str(path))
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(path)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    import tkinter as tk
    from tkinter import ttk, messagebox
    from ..platform.desktop import SessionLock
    from ..platform.paths import cache_dir
    from ..core.host_control import ControlServer, request
    from ..core.desktop_settings import load
    from ..platform.launchers import enabled, set_enabled
    from .desktop_app import endpoint
    panel_endpoint = cache_dir() / 'dictate-panel.sock'
    try:
        lock = SessionLock(cache_dir() / 'dictate-panel.lock')
    except BlockingIOError:
        try:
            request(panel_endpoint, 'show')
        except (OSError, RuntimeError, EOFError):
            pass
        return
    control = ControlServer(panel_endpoint)
    root = tk.Tk()
    closed = [False]
    root.bind('<Destroy>', lambda event: closed.__setitem__(0, True) if event.widget is root else None)
    root.title('Voice to Clipboard — Settings and status')
    root.geometry('780x760')
    canvas = tk.Canvas(root, highlightthickness=0)
    scrollbar = ttk.Scrollbar(root, orient='vertical', command=canvas.yview)
    scrollbar.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)
    frame = ttk.Frame(canvas, padding=16)
    content = canvas.create_window((0, 0), window=frame, anchor='nw')
    frame.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda event: canvas.itemconfigure(content, width=event.width))
    status = tk.StringVar(value='Connecting…')
    ttk.Label(frame, textvariable=status, wraplength=630).pack(anchor='w', pady=(0, 12))
    work = queue.Queue(maxsize=16)
    results = queue.Queue()
    stopping = threading.Event()
    callbacks = {}
    next_callback = [0]
    def worker():
        while not stopping.is_set():
            try:
                function, callback_id = work.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                value = function()
                results.put((callback_id, value, None))
            except Exception as exc:
                results.put((callback_id, None, str(exc)))
    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()
    def enqueue(function, callback=lambda value: None):
        callback_id = next_callback[0]
        next_callback[0] += 1
        callbacks[callback_id] = callback
        try:
            work.put_nowait((function, callback_id))
            return True
        except queue.Full:
            callbacks.pop(callback_id, None)
            status.set("Please wait for the current operation")
            return False
    def command(operation):
        def completed(value):
            if operation == 'quit':
                status.set('Finishing dictation and exiting…')
                if not value.get('dictation_processes'):
                    root.destroy()
        enqueue(lambda: request(endpoint(), operation), completed)
    row = ttk.Frame(frame)
    row.pack(fill='x')
    from ..core.profiles import LANGUAGES, LANGUAGE_NAMES, label as profile_label, validate as validate_profiles, language_options, language_code, saved_profiles
    settings = load()
    profiles = [dict(p) for p in settings['profiles']]
    active_profiles = [dict(p) for p in profiles]
    selected_start = tk.StringVar()
    start_choice = ttk.Combobox(row, textvariable=selected_start, state='readonly', width=30)
    start_choice.pack(side='left')
    def refresh_start():
        start_choice['values'] = [profile_label(p) for p in active_profiles]
        if profiles:
            start_choice.current(0)
    refresh_start()
    def start_recording():
        index = start_choice.current()
        if index >= 0:
            key = active_profiles[index]['key']
            enqueue(lambda: request(endpoint(), 'start-profile', key=key))
    ttk.Button(row, text='Start (clipboard)', command=start_recording).pack(side='left', padx=3)
    ttk.Button(row, text='Stop recording', command=lambda: command('stop-recording')).pack(side='left', padx=3)
    row = ttk.Frame(frame)
    row.pack(fill='x', pady=8)
    for label, operation in [('Pause shortcuts', 'pause'), ('Resume', 'resume'), ('Copy last', 'copy-last')]:
        ttk.Button(row, text=label, command=lambda op=operation: command(op)).pack(side='left', padx=3)
    settings = load()
    mods = tk.StringVar(value=settings['hotkey_modifiers'])
    model = tk.StringVar(value=settings['model'])
    device = tk.StringVar(value=settings['inference_device'])
    overlay = tk.BooleanVar(value=settings['overlay'])
    auto = tk.BooleanVar(value=enabled())
    from ..core.model_compatibility import CHOICES, describe, validate as validate_model
    form = ttk.LabelFrame(frame, text='Dictation settings', padding=12)
    form.pack(fill='x', pady=10)
    for number, (label, variable, values) in enumerate([
            ('Default shortcut modifiers', mods, ['alt+shift', 'ctrl+alt', 'ctrl+alt+shift']),
            ('Inference device', device, ['auto', 'cpu', 'cuda', 'metal']),
            ('Default model (empty = multilingual turbo)', model, CHOICES)]):
        ttk.Label(form, text=label).grid(row=number, column=0, sticky='w', padx=5, pady=5)
        entry = ttk.Combobox(form, textvariable=variable, values=values) if values else ttk.Entry(form, textvariable=variable)
        entry.grid(row=number, column=1, sticky='ew', padx=5)
    form.columnconfigure(1, weight=1)
    ttk.Checkbutton(form, text='Show recording overlay', variable=overlay).grid(row=3, columnspan=2, sticky='w')
    profile_frame = ttk.LabelFrame(frame, text='Language profiles — default or individual shortcut modifiers', padding=8)
    profile_frame.pack(fill='x', pady=6)
    profile_list = tk.Listbox(profile_frame, height=4, exportselection=False)
    profile_list.pack(fill='x')
    language = tk.StringVar(value='English (en)')
    letter = tk.StringVar(value='e')
    delivery = tk.BooleanVar(value=False)
    profile_model = tk.StringVar()
    profile_modifiers = tk.StringVar()
    editor = ttk.Frame(profile_frame)
    editor.pack(fill='x')
    language_choice = ttk.Combobox(editor, textvariable=language, values=language_options(), width=25, state='readonly')
    language_choice.pack(side='left')
    ttk.Label(editor, text='Key A–Z').pack(side='left')
    ttk.Entry(editor, textvariable=letter, width=4).pack(side='left')
    ttk.Checkbutton(editor, text='Paste with hotkey', variable=delivery).pack(side='left')
    ttk.Label(profile_frame, text='Profile modifiers (empty = default above)').pack(anchor='w')
    ttk.Combobox(profile_frame, textvariable=profile_modifiers,
                 values=['', 'alt+shift', 'ctrl+alt', 'ctrl+alt+shift']).pack(fill='x')
    ttk.Label(profile_frame, text='Model override (empty = default model; custom models must support the language)').pack(anchor='w')
    ttk.Combobox(profile_frame, textvariable=profile_model, values=CHOICES).pack(fill='x')
    model_feedback = tk.StringVar()
    ttk.Label(profile_frame, textvariable=model_feedback, wraplength=680).pack(anchor='w')
    def update_model_feedback(*unused):
        code = language_code(language.get())
        model_feedback.set(describe(code, profile_model.get(), model.get())[1])
    for variable in (language, profile_model, model):
        variable.trace_add('write', update_model_feedback)
    update_model_feedback()
    def refresh_profiles():
        profile_list.delete(0, 'end')
        for p in profiles:
            profile_list.insert('end', profile_label(p) + (' → paste' if p['paste'] else ' → clipboard'))
    def selected(event=None):
        selection = profile_list.curselection()
        if selection:
            p = profiles[selection[0]]
            language.set(f"{LANGUAGE_NAMES[p['language']]} ({p['language']})")
            letter.set(p['key'])
            delivery.set(p['paste'])
            profile_model.set(p['model'])
            profile_modifiers.set(p.get('modifiers', ''))
    profile_list.bind('<<ListboxSelect>>', selected)
    def edit_profile(mode):
        if save_pending[0]:
            feedback.set('Wait for Apply to finish before editing profiles.')
            return
        candidate = [dict(p) for p in profiles]
        selection = profile_list.curselection()
        try:
            if mode != 'add' and not selection:
                raise ValueError('Select a profile first')
            profile = dict(language=language_code(language.get()),
                           key=letter.get().strip(), paste=delivery.get(), model=profile_model.get().strip(),
                           modifiers=profile_modifiers.get().strip())
            if mode == 'add':
                candidate.append(profile)
            elif mode == 'update':
                candidate[selection[0]] = profile
            else:
                del candidate[selection[0]]
            if mode != 'remove':
                validate_model(profile['language'], profile['model'], model.get())
            profiles[:] = validate_profiles(candidate, check_models=False)
            refresh_profiles()
            feedback.set('Profile changes are pending. Click Apply settings to activate them.')
        except ValueError as exc:
            messagebox.showerror('Profiles', str(exc), parent=root)
    buttons = ttk.Frame(profile_frame)
    buttons.pack(fill='x')
    for text, mode in [('Add', 'add'), ('Update selected', 'update'), ('Remove selected', 'remove')]:
        ttk.Button(buttons, text=text, command=lambda mode=mode: edit_profile(mode)).pack(side='left')
    refresh_profiles()
    compatible = [False]
    save_pending = [False]
    close_after_save = [False]
    feedback = tk.StringVar(value='Add or update a profile, then Apply. Closing this window keeps the tray app running.')
    ttk.Label(profile_frame, textvariable=feedback, wraplength=680).pack(anchor='w')
    def saved(value):
        active_profiles[:] = saved_profiles(value)
        profiles[:] = [dict(p) for p in active_profiles]
        refresh_profiles()
        refresh_start()
        feedback.set('Saved and active. You can close Settings; shortcuts remain available.')
        if close_after_save[0]:
            root.destroy()
    def save():
        if not compatible[0]:
            feedback.set('Waiting for a compatible host. If this persists, Quit the tray app and relaunch after updating.')
            return
        if save_pending[0]:
            return
        values = {'hotkey_modifiers': mods.get(), 'model': model.get().strip(),
                  'inference_device': device.get(), 'overlay': overlay.get(),
                  'schema_version': 3, 'profiles': [dict(p) for p in profiles]}
        from ..core.desktop_settings import validate as validate_settings
        try:
            values = validate_settings(values)
        except ValueError as exc:
            feedback.set(str(exc))
            return
        save_pending[0] = True
        apply_button.configure(state='disabled')
        feedback.set('Saving and registering shortcuts…')
        if not enqueue(lambda: request(endpoint(), 'settings', values=values), saved):
            save_pending[0] = False
            apply_button.configure(state='normal')
            feedback.set('Busy; settings were not submitted. Try Apply again.')
    apply_button = ttk.Button(form, text='Apply all settings and profiles', command=save)
    apply_button.grid(row=4, columnspan=2, sticky='w', pady=8)
    def autostart():
        desired = auto.get()
        def changed(value):
            auto.set(value['enabled'])
            if value['error']:
                raise RuntimeError(value['error'])
            status.set('Login startup enabled.' if value['enabled'] else 'Login startup disabled.')
        def apply():
            error = None
            try:
                set_enabled(desired)
            except Exception as exc:
                error = str(exc)
            return {'enabled': enabled(), 'error': error}
        enqueue(apply, changed)
    ttk.Checkbutton(frame, text='Start at login (current user only)', variable=auto, command=autostart).pack(anchor='w')
    checks = tk.Text(frame, height=9, wrap='word')
    checks.pack(fill='both', expand=True, pady=8)
    checks.insert('1.0', 'System check does not record audio or download models.\n')
    checks.configure(state='disabled')
    def show_report(value):
        checks.configure(state='normal')
        checks.delete('1.0', 'end')
        checks.insert('1.0', value)
        checks.configure(state='disabled')
    def check():
        from ..platform.diagnostics import report
        enqueue(report, show_report)
    row = ttk.Frame(frame)
    row.pack(fill='x')
    ttk.Button(row, text='Check system', command=check).pack(side='left', padx=3)
    ttk.Button(row, text='Open log', command=lambda: enqueue(open_log)).pack(side='left', padx=3)
    ttk.Button(row, text='Quit app (finish recording)', command=lambda: command('quit')).pack(side='right', padx=3)
    ttk.Button(row, text='Cancel unfinished and exit', command=lambda: command('cancel')).pack(side='right', padx=3)
    def show(payload):
        if payload.get('op') == 'quit':
            root.after(150, root.destroy)
            return {'ok': True}
        root.deiconify()
        root.lift()
        root.focus_force()  # Explicit user action to open this settings window.
        return {'ok': True}
    poll_pending = [False]
    misses = [0]
    def received(value):
        compatible[0] = False
        current_profiles = saved_profiles(value)
        if value.get('profile_modifiers') is not True:
            raise RuntimeError('Quit Voice to Clipboard from the tray and relaunch the updated app to edit profile modifiers.')
        compatible[0] = True
        if profiles == active_profiles and not save_pending[0] and current_profiles != active_profiles:
            active_profiles[:] = current_profiles
            profiles[:] = [dict(p) for p in current_profiles]
            refresh_profiles()
            refresh_start()
        poll_pending[0] = False
        misses[0] = 0
        status.set(f"{value.get('phase', value['state'])} · hotkeys {value['state']}\n{value.get('message', '')}")
    def close_window():
        if save_pending[0]:
            close_after_save[0] = True
            feedback.set('Waiting for Apply to finish before closing…')
            return
        if profiles != active_profiles:
            if not messagebox.askyesno('Unsaved profiles', 'Discard pending profile changes and close Settings?', parent=root):
                return
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', close_window)
    def poll():
        control.dispatch(show)
        try:
            while True:
                callback_id, value, error = results.get_nowait()
                callback = callbacks.pop(callback_id)
                if callback is saved:
                    save_pending[0] = False
                    apply_button.configure(state='normal')
                if error:
                    if callback is received:
                        poll_pending[0] = False
                        misses[0] += 1
                        if misses[0] >= 2:
                            root.destroy()
                            return
                    else:
                        close_after_save[0] = False
                        feedback.set('Not saved: ' + error)
                        messagebox.showerror('Voice to Clipboard', error, parent=root)
                else:
                    try:
                        callback(value)
                    except tk.TclError:
                        return
                    except Exception as exc:
                        poll_pending[0] = False
                        close_after_save[0] = False
                        feedback.set(str(exc))
        except queue.Empty:
            pass
        if closed[0]:
            return
        if not poll_pending[0]:
            poll_pending[0] = True
            if not enqueue(lambda: request(endpoint(), 'status'), received):
                poll_pending[0] = False
        if not closed[0]:
            root.after(500, poll)
    root.after(100, poll)
    try:
        root.mainloop()
    finally:
        stopping.set()
        worker_thread.join(timeout=11)
        callbacks.clear()  # Release all Tk-owning callbacks on the UI thread.
        control.close()
        lock.close()


if __name__ == '__main__':
    main()
