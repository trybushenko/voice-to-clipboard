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
    root.title('Voice to Clipboard — Settings and status')
    root.geometry('670x650')
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill='both', expand=True)
    status = tk.StringVar(value='Connecting…')
    ttk.Label(frame, textvariable=status, wraplength=630).pack(anchor='w', pady=(0, 12))
    work = queue.Queue(maxsize=16)
    results = queue.Queue()
    stopping = threading.Event()
    def worker():
        while not stopping.is_set():
            try:
                function, callback = work.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                value = function()
                results.put((callback, value, None))
            except Exception as exc:
                results.put((callback, None, str(exc)))
    threading.Thread(target=worker, daemon=True).start()
    def enqueue(function, callback=lambda value: None):
        try:
            work.put_nowait((function, callback))
        except queue.Full:
            status.set("Please wait for the current operation")
    def command(operation):
        enqueue(lambda: request(endpoint(), operation))
    row = ttk.Frame(frame)
    row.pack(fill='x')
    for label, operation in [('Start Ukrainian', 'start-uk'), ('Start English', 'start-en'),
                             ('Stop recording', 'stop-recording')]:
        ttk.Button(row, text=label, command=lambda op=operation: command(op)).pack(side='left', padx=3)
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
    form = ttk.LabelFrame(frame, text='Dictation settings', padding=12)
    form.pack(fill='x', pady=10)
    for number, (label, variable, values) in enumerate([
            ('Shortcut modifiers (U/E/L)', mods, ['alt+shift', 'ctrl+alt', 'ctrl+alt+shift']),
            ('Inference device', device, ['auto', 'cpu', 'cuda', 'metal']),
            ('Model (empty = existing default)', model, None)]):
        ttk.Label(form, text=label).grid(row=number, column=0, sticky='w', padx=5, pady=5)
        entry = ttk.Combobox(form, textvariable=variable, values=values) if values else ttk.Entry(form, textvariable=variable)
        entry.grid(row=number, column=1, sticky='ew', padx=5)
    form.columnconfigure(1, weight=1)
    ttk.Checkbutton(form, text='Show recording overlay', variable=overlay).grid(row=3, columnspan=2, sticky='w')
    def save():
        values = {'hotkey_modifiers': mods.get(), 'model': model.get().strip(),
                  'inference_device': device.get(), 'overlay': overlay.get()}
        enqueue(lambda: request(endpoint(), 'settings', values=values), lambda value: status.set('Settings saved.'))
    ttk.Button(form, text='Apply settings', command=save).grid(row=4, columnspan=2, sticky='w', pady=8)
    def autostart():
        desired = auto.get()
        def changed(value):
            auto.set(value)
            status.set('Login startup enabled.' if value else 'Login startup disabled.')
        def apply():
            try:
                set_enabled(desired)
            finally:
                results.put((lambda value: auto.set(value), enabled(), None))
            return enabled()
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
        poll_pending[0] = False
        misses[0] = 0
        status.set(f"{value.get('phase', value['state'])} · hotkeys {value['state']}\n{value.get('message', '')}")
    def poll():
        control.dispatch(show)
        try:
            while True:
                callback, value, error = results.get_nowait()
                if error:
                    if callback is received:
                        poll_pending[0] = False
                        misses[0] += 1
                        if misses[0] >= 2:
                            root.destroy()
                            return
                    else:
                        messagebox.showerror('Voice to Clipboard', error, parent=root)
                else:
                    callback(value)
        except queue.Empty:
            pass
        if not poll_pending[0]:
            poll_pending[0] = True
            enqueue(lambda: request(endpoint(), 'status'), received)
        root.after(500, poll)
    root.after(100, poll)
    try:
        root.mainloop()
    finally:
        stopping.set()
        control.close()
        lock.close()


if __name__ == '__main__':
    main()
