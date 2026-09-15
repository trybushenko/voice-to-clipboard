"""Optional GTK status overlay in a separate process; never takes keyboard focus."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import queue


class Overlay:
    def __init__(self, enabled=True, lang='uk'):
        self.process = None
        self.messages = queue.Queue(maxsize=1)
        self.thread = None
        if enabled:
            python = '/usr/bin/python3' if sys.platform.startswith('linux') else sys.executable
            try:
                from voice_to_clipboard.platform.processes import spawn_background
                self.process = spawn_background(
                    [python, str(Path(__file__).resolve()), lang],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.thread = threading.Thread(target=self._write, daemon=True)
                self.thread.start()
            except OSError:
                self.close()

    def _write(self):
        process = self.process
        try:
            while True:
                message = self.messages.get()
                if message is None:
                    break
                process.stdin.write((json.dumps(message) + '\n').encode())
                process.stdin.flush()
        except (OSError, ValueError):
            pass
        finally:
            process.stdin.close()

    def update(self, state='recording', elapsed=0, level=0):
        if self.process is not None:
            self._enqueue(dict(state=state, elapsed=elapsed, level=level))

    def _enqueue(self, message):
        try:
            self.messages.put_nowait(message)
        except queue.Full:
            try:
                self.messages.get_nowait()
            except queue.Empty:
                pass
            try:
                self.messages.put_nowait(message)
            except queue.Full:
                pass

    def close(self):
        if self.process is not None:
            process = self.process
            self._enqueue(None)
            try:
                process.wait(timeout=.5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if self.thread:
                self.thread.join(timeout=.5)
            self.process = None


def window(lang):
    import sys
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk, GLib

    win = Gtk.Window(title='Dictate Overlay')
    win.set_decorated(False)
    win.set_resizable(False)
    win.set_keep_above(True)
    win.set_accept_focus(False)
    win.set_focus_on_map(False)
    win.set_skip_taskbar_hint(True)
    win.set_skip_pager_hint(True)
    win.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
    win.stick()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.set_border_width(16)
    title = Gtk.Label(label='●  Запис  ·  ' + lang.upper())
    detail = Gtk.Label(label='00:00  ·  повтори хоткей для завершення')
    bar = Gtk.ProgressBar()
    bar.set_size_request(290, 4)
    box.pack_start(title, False, False, 0)
    box.pack_start(bar, False, False, 0)
    box.pack_start(detail, False, False, 0)
    win.add(box)
    css = Gtk.CssProvider()
    css.load_from_data(b'window {background: #18212f; color: #f2f5fa;} label {font: 14px Sans;} progressbar trough {min-height: 4px; background: #344052;} progressbar progress {background: #49dcb1;}')
    Gtk.StyleContext.add_provider_for_screen(win.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    display = Gdk.Display.get_default()
    pointer = display.get_default_seat().get_pointer()
    _, x, y = pointer.get_position()
    area = display.get_monitor_at_point(x, y).get_workarea()
    win.show_all()
    width, height = win.get_size()
    win.move(area.x + (area.width - width)//2, area.y + 28)
    state = {'state': 'recording', 'elapsed': 0, 'level': 0}
    pending = bytearray()
    os.set_blocking(sys.stdin.fileno(), False)

    def tick():
        try:
            data = os.read(sys.stdin.fileno(), 65536)
            if not data:
                Gtk.main_quit()
                return False
            pending.extend(data)
            while b'\n' in pending:
                line, _, tail = pending.partition(b'\n')
                pending[:] = tail
                try:
                    state.update(json.loads(line))
                except (ValueError, TypeError):
                    pass
        except BlockingIOError:
            pass
        processing = state['state'] == 'transcribing'
        title.set_text(('◌  Розпізнавання' if processing else '●  Запис') + '  ·  ' + lang.upper())
        seconds = int(state['elapsed'])
        detail.set_text('Текст скоро буде в буфері' if processing else f'{seconds//60:02}:{seconds%60:02}  ·  повтори хоткей для завершення')
        if processing:
            bar.pulse()
        else:
            bar.set_fraction(max(0, min(1, state['level'])))
        return True

    GLib.timeout_add(100, tick)
    win.connect('destroy', Gtk.main_quit)
    Gtk.main()


def tk_window(lang):
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.withdraw()
    root.title('Dictate Overlay')
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    root.configure(bg='#18212f')
    title = tk.Label(root, text='Recording · ' + lang.upper(), fg='#f2f5fa', bg='#18212f', font=('Arial', 14))
    title.pack(padx=20, pady=(14, 8))
    bar = ttk.Progressbar(root, length=290, maximum=1)
    bar.pack(padx=20)
    detail = tk.Label(root, text='00:00 · press shortcut again to finish', fg='#c2cddd', bg='#18212f')
    detail.pack(padx=20, pady=(8, 14))
    root.update_idletasks()
    root.geometry(f'+{(root.winfo_screenwidth()-root.winfo_reqwidth())//2}+40')
    if sys.platform == 'darwin':
        try:
            root.tk.call('::tk::unsupported::MacWindowStyle', 'style', root._w, 'help', 'noActivates')
        except tk.TclError:
            pass
    elif sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        user = ctypes.windll.user32
        user.GetParent.argtypes = [wintypes.HWND]
        user.GetParent.restype = wintypes.HWND
        user.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        hwnd = user.GetParent(root.winfo_id())
        user.SetWindowLongW(hwnd, -20, user.GetWindowLongW(hwnd, -20) | 0x08000000 | 0x00000080)
    updates = queue.Queue()

    def read():
        try:
            for line in sys.stdin:
                updates.put(json.loads(line))
        finally:
            updates.put(None)

    def tick():
        latest = {}
        while not updates.empty():
            message = updates.get_nowait()
            if message is None:
                root.destroy()
                return
            latest = message
        if latest:
            processing = latest['state'] == 'transcribing'
            title.configure(text=('Transcribing' if processing else 'Recording') + ' · ' + lang.upper())
            seconds = int(latest['elapsed'])
            detail.configure(text='Preparing clipboard…' if processing else f'{seconds//60:02}:{seconds%60:02} · press shortcut again to finish')
            if processing:
                bar.configure(mode='indeterminate')
                bar.start(30)
            else:
                bar.stop()
                bar.configure(mode='determinate', value=latest['level'])
        root.after(100, tick)

    threading.Thread(target=read, daemon=True).start()
    root.deiconify()
    root.after(100, tick)
    root.mainloop()


if __name__ == '__main__':
    language = sys.argv[1] if len(sys.argv) > 1 else 'uk'
    if sys.platform.startswith('linux'):
        window(language)
    else:
        tk_window(language)
