"""System-Python accessibility helper; no application/virtualenv imports."""
import json
import sys
import time
import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi, GLib


def main():
    Atspi.init()
    Atspi.set_timeout(100, 100)
    current = [None]
    invalid = [False]
    def event(event, *args):
        if event.detail1 and current[0] is not None and event.source != current[0]:
            invalid[0] = True
    listener = Atspi.EventListener.new(event, None)
    if not listener.register('object:state-changed:focused'):
        raise RuntimeError('AT-SPI focus subscription unavailable')
    try:
        deadline = time.monotonic() + 2
        pending = [Atspi.get_desktop(0)]
        count = 0
        while pending and count < 1000 and time.monotonic() < deadline:
            node = pending.pop(0)
            count += 1
            try:
                states = node.get_state_set()
                if states.contains(Atspi.StateType.FOCUSED):
                    current[0] = node
                    break
                if not states.contains(Atspi.StateType.DEFUNCT):
                    pending.extend(node.get_child_at_index(i) for i in range(min(node.get_child_count(), 300)))
            except Exception:
                continue
        if current[0] is None:
            raise RuntimeError('Focused field not exposed through AT-SPI; paste manually')
        def respond():
            focused = current[0].get_state_set().contains(Atspi.StateType.FOCUSED)
            print(json.dumps({'ok': focused and not invalid[0]}), flush=True)
        respond()
        loop = GLib.MainLoop()
        def read(source, condition):
            if condition & (GLib.IO_HUP | GLib.IO_ERR):
                loop.quit()
                return False
            line = sys.stdin.readline()
            if not line:
                loop.quit()
                return False
            respond()
            return True
        GLib.io_add_watch(sys.stdin, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, read)
        loop.run()
    finally:
        listener.deregister('object:state-changed:focused')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'error': str(exc)}), flush=True)
        sys.exit(1)
