import os
from pathlib import Path
from ..platform.paths import cache_dir

RUNTIME = Path(os.environ.get('DICTATE_RUNTIME', str(cache_dir() / 'dictate-worker')))
