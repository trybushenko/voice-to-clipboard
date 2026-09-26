"""Measure a standalone bundle from an unrelated cwd, without PYTHONPATH."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('executable', type=Path)
    parser.add_argument('--report', type=Path, default=Path('packaging-report.json'))
    args = parser.parse_args()
    exe = args.executable.resolve()
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.pop('PYTHONHOME', None)
    with tempfile.TemporaryDirectory(prefix='vtc-launch-') as folder:
        output = Path(folder) / 'report.json'
        started = time.perf_counter()
        subprocess.run([str(exe), '--packaging-probe', str(output)], cwd=folder,
                       env=environment, check=True, timeout=90)
        elapsed = time.perf_counter() - started
        result = json.loads(output.read_text(encoding='utf-8'))
    assert result['frozen'], result
    bundle = exe.parent.parent.parent if exe.parent.name == 'MacOS' else exe.parent
    result.update(process_start_to_exit_seconds=elapsed,
                  bundle_bytes=sum(p.stat().st_size for p in bundle.rglob('*')
                                   if p.is_file() and not p.is_symlink()))
    args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
