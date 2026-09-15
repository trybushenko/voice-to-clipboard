"""Visible eight-second overlay smoke test; no microphone or clipboard access."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import subprocess
import time
from voice_to_clipboard.ui.overlay import Overlay

def active():
    return subprocess.check_output(['xdotool','getactivewindow'],text=True).strip()

def windows():
    return subprocess.run(['xdotool','search','--onlyvisible','--name','^Dictate Overlay$'],capture_output=True,text=True).stdout.split()

def main():
    before = active()
    o = Overlay(True, 'en')
    try:
        for i in range(30):
            o.update(elapsed=i/10,level=(i%10)/10)
            time.sleep(.1)
        ids = windows()
        assert ids, 'Overlay did not appear'
        assert active() == before, 'Overlay stole keyboard focus'
        props = subprocess.check_output(['xprop','-id',ids[0],'_NET_WM_STATE','WM_HINTS'],text=True)
        print(props)
        import gi
        gi.require_version('Gtk','3.0')
        gi.require_version('GdkX11','3.0')
        from gi.repository import Gtk, Gdk, GdkX11
        foreign = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(),int(ids[0]))
        _, _, w, h = foreign.get_geometry()
        Gdk.pixbuf_get_from_window(foreign,0,0,w,h).savev('/tmp/dictate-overlay.png','png',[],[])
        o.update(state='transcribing')
        time.sleep(3)
    finally:
        o.close()
    assert not windows(), 'Overlay remained after close'
    print('PASS: appears, stays above, preserves focus, closes after processing')


if __name__ == "__main__":
    main()
