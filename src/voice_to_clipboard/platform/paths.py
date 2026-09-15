import os
import sys
from pathlib import Path

def data_dir():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'VoiceToClipboard'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/VoiceToClipboard'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'dictate'


def cache_dir():
    if sys.platform == 'win32':
        return data_dir() / 'cache'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Caches/VoiceToClipboard'
    return Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))

