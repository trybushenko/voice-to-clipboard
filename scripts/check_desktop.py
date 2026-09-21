"""Isolated real tray/controller/panel smoke. No microphone, model load or autostart changes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from voice_to_clipboard.core.host_control import request
from voice_to_clipboard.platform.processes import spawn_background


def main():
    with tempfile.TemporaryDirectory(prefix='vtc-', dir=None if sys.platform == 'win32' else '/tmp') as folder:
        folder = Path(folder)
        data, cache = folder / 'data', folder / 'cache'
        data.mkdir(); cache.mkdir()
        (data / 'settings.json').write_text(json.dumps({'hotkey_modifiers': 'ctrl+alt+shift', 'schema_version': 2,
            'profiles': [{'language': 'en', 'key': 'e', 'paste': False, 'model': ''}]}))
        env = {**os.environ, 'VOICE_TO_CLIPBOARD_DATA_DIR': str(data), 'VOICE_TO_CLIPBOARD_CACHE_DIR': str(cache)}
        endpoint = cache / 'dictate-hotkey-control.sock'
        command = [sys.executable, '-m', 'voice_to_clipboard.ui.desktop_app', '--run']
        app = spawn_background(command, env=env, no_console=True, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 20
            while not endpoint.exists():
                if app.poll() is not None or time.monotonic() > deadline:
                    log = data / 'logs/desktop.log'
                    raise RuntimeError(log.read_text() if log.exists() else 'Desktop did not start')
                time.sleep(.1)
            initial = request(endpoint, 'status')
            assert initial['desktop'] is True, initial
            assert initial['dictation_processes'] == 0 and initial['worker_pid'] is None, initial
            restricted = sys.platform == 'darwin' and initial['state'] == 'paused'
            if restricted:
                assert 'Allow' in initial['message'] or 'Accessibility' in initial['message'], initial
            for _ in range(3):
                assert request(endpoint, 'pause')['state'] == 'paused'
                if restricted:
                    try:
                        request(endpoint, 'resume')
                    except RuntimeError:
                        pass
                else:
                    assert request(endpoint, 'resume')['state'] == 'listening'
            initial_profiles = request(endpoint, 'status')['profiles']
            assert [p['language'] for p in initial_profiles] == ['en'], initial_profiles
            values = {'hotkey_modifiers': 'ctrl+alt+shift', 'model': '', 'inference_device': 'cpu', 'overlay': False}
            request(endpoint, 'settings', values=values)
            assert json.loads((data/'settings.json').read_text())['inference_device'] == 'cpu'
            try:
                request(endpoint, 'settings', values={'hotkey_modifiers': 'invalid'})
                raise AssertionError('Invalid settings accepted')
            except RuntimeError:
                pass
            assert request(endpoint, 'status')['state'] == ('paused' if restricted else 'listening')
            if sys.platform == 'win32':
                from voice_to_clipboard.platform.windows_hotkeys import NativeHotkeys
                reserved = NativeHotkeys({key: lambda: None for key in ('u', 'e', 'l')}, 'ctrl+alt+win')
                try:
                    reserved.start()
                    try:
                        request(endpoint, 'settings', values={**values, 'hotkey_modifiers': 'ctrl+alt+win'})
                        raise AssertionError('Conflicting shortcut settings accepted')
                    except RuntimeError:
                        pass
                    restored = request(endpoint, 'status')
                    assert restored['state'] == 'listening' and restored['hotkey_modifiers'] == 'ctrl+alt+shift', restored
                    assert json.loads((data/'settings.json').read_text())['hotkey_modifiers'] == 'ctrl+alt+shift'
                finally:
                    reserved.stop()
                    reserved.join(timeout=2)
            profile_values = {**values, 'profiles': [
                {'language': 'en', 'key': 'e', 'paste': False, 'model': ''},
                {'language': 'pl', 'key': 'p', 'paste': True, 'model': 'small'}]}
            if not restricted:
                changed = request(endpoint, 'settings', values=profile_values)
                assert [p['language'] for p in changed['profiles']] == ['en', 'pl']
                assert json.loads((data/'settings.json').read_text())['profiles'] == changed['profiles']
                request(endpoint, 'settings', values={**values, 'profiles': initial_profiles})
                assert request(endpoint, 'status')['profiles'] == initial_profiles
            request(endpoint, 'show')
            deadline = time.monotonic() + 8
            while not (cache/'dictate-panel.sock').exists() and time.monotonic() < deadline:
                time.sleep(.1)
            assert (cache/'dictate-panel.sock').exists(), 'Settings panel did not open'
            second = spawn_background(command, env=env, no_console=True, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            assert second.wait(timeout=15) == 0
            assert request(endpoint, 'status')['pid'] == initial['pid'], 'Duplicate host started'
            assert request(endpoint, 'quit')['state'] == 'stopping'
            assert app.wait(timeout=12) == 0
            assert not endpoint.exists()
            assert not list((cache/'dictate-desktop').glob('host-*')), 'Private worker runtime remained'
            print('PASS: native tray/controller, pause/resume, settings, singleton panel and clean Quit; no microphone or model loaded')
        finally:
            if app.poll() is None:
                try:
                    request(endpoint, 'quit')
                    app.wait(timeout=10)
                except Exception:
                    app.terminate()
                    app.wait(timeout=5)


if __name__ == '__main__':
    main()
