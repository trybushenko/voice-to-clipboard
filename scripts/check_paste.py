"""Visible native paste check in an isolated text field; no microphone or model.

Run with the installed virtualenv Python. --auto starts without a button click.
The synthetic test replaces clipboard content, just like dictation does.
"""
import argparse
import queue
import threading
import tkinter as tk
from voice_to_clipboard.platform.desktop import to_clipboard, do_paste
from voice_to_clipboard.platform.focus import make_guard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--auto', action='store_true')
    args = parser.parse_args()
    root = tk.Tk()
    root.title('Voice to Clipboard — paste verification')
    root.geometry('640x240')
    text = tk.Text(root, height=5)
    text.pack(fill='both', expand=True, padx=12, pady=12)
    status = tk.StringVar(value='Press Test; keep focus in this window until the result appears.')
    tk.Label(root, textvariable=status, wraplength=610).pack(padx=12)
    results = queue.Queue()
    expected = 'Перевірка вставки — English 123.'
    running = [False]
    passed = [False]
    def worker():
        guard = make_guard()
        try:
            if not to_clipboard(expected):
                raise RuntimeError('Clipboard write failed')
            do_paste(expected, guard)
            results.put(None)
        except Exception as exc:
            results.put(str(exc))
        finally:
            guard.close()
    def start():
        if running[0]:
            return
        running[0] = True
        text.delete('1.0', 'end')
        text.focus_force()
        status.set('Checking field identity and native paste…')
        root.after(300, lambda: threading.Thread(target=worker, daemon=True).start())
    def finish(error):
        actual = text.get('1.0', 'end-1c')
        passed[0] = error is None and actual == expected and root.focus_get() == text
        result = 'PASS: exact Unicode text inserted once; focus preserved.' if passed[0] else 'FAIL: ' + (error or 'Text did not appear exactly once in the original field')
        status.set(result)
        print(result, flush=True)
        running[0] = False
        if args.auto:
            root.after(300, root.destroy)
    def poll():
        try:
            result = results.get_nowait()
            # Input injection and the target's paste handler are asynchronous.
            root.after(500, lambda: finish(result))
        except queue.Empty:
            pass
        root.after(50, poll)
    tk.Button(root, text='Test native paste', command=start).pack(pady=10)
    if args.auto:
        root.after(500, start)
    root.after(50, poll)
    root.mainloop()
    if args.auto and not passed[0]:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
