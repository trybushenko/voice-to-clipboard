"""Bounded application diagnostics, excluding child stdout and transcripts."""
import logging
import os
from logging.handlers import RotatingFileHandler
from ..platform.paths import data_dir


def log_path():
    return data_dir() / 'logs' / 'desktop.log'


class PrivateRotatingHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        os.chmod(self.baseFilename, 0o600)
        return stream


def configure():
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = PrivateRotatingHandler(path, maxBytes=512 * 1024, backupCount=3, encoding='utf-8')
    path.chmod(0o600)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger = logging.getLogger('voice_to_clipboard.desktop')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger


class LogStream:
    encoding = 'utf-8'
    def __init__(self, logger):
        self.logger = logger
    def write(self, text):
        for line in text.splitlines():
            if line.strip():
                self.logger.info('%s', line[:2000])
        return len(text)
    def flush(self):
        pass
    def isatty(self):
        return False


def collect_process(process, label):
    """Accept only structured technical events; never retain arbitrary ML output."""
    import json
    import threading
    def collect():
        suppressed = False
        try:
            while True:
                raw = process.stderr.readline(4096)
                if not raw:
                    break
                try:
                    payload = json.loads(raw)
                    event = payload.get('event')
                    if event not in {'retry', 'error', 'warn', 'paste', 'delivery', 'worker-error'}:
                        raise ValueError('Unrecognized event')
                    logging.getLogger('voice_to_clipboard.desktop').info('%s event=%s', label, event)
                except (ValueError, AttributeError):
                    if not suppressed:
                        logging.getLogger('voice_to_clipboard.desktop').warning('%s emitted unstructured diagnostics; reproduce in foreground for details', label)
                        suppressed = True
        finally:
            process.stderr.close()
    thread = threading.Thread(target=collect, daemon=True)
    thread.start()
    return thread
