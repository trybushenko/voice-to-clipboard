"""PyInstaller entry point; keep imports light until multiprocessing dispatch."""
import multiprocessing
import os
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    multiprocessing.freeze_support()
    # Windowed Windows builds have no standard streams unless explicitly piped.
    for name in ('stdin', 'stdout', 'stderr'):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, 'r' if name == 'stdin' else 'w'))
    if sys.argv[1:2] == ['--packaging-probe']:
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        runpy.run_path(str(Path(sys._MEIPASS) / 'probe.py'), run_name='__main__')
    else:
        from voice_to_clipboard.platform.frozen import dispatch
        dispatch(sys.argv[1:])
