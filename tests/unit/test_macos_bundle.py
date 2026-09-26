import plistlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from voice_to_clipboard.platform import launchers


class MacBundleTests(unittest.TestCase):
    def test_frozen_agent_ownership_and_data_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            app = home / 'Applications/VoiceToClipboard.app'
            exe = app / 'Contents/MacOS/VoiceToClipboard'
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b'bundle executable')
            (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({
                'CFBundleIdentifier': launchers.APP_ID}))
            agent = home / 'Library/LaunchAgents/agent.plist'
            data = home / 'history.json'
            data.write_bytes(b'private unchanged data')
            with patch.object(sys, 'platform', 'darwin'), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(exe)), patch.object(Path, 'home', return_value=home), patch.object(launchers, 'autostart_path', return_value=agent):
                self.assertEqual(launchers.install(), app)
                launchers.set_enabled(True)
                self.assertTrue(launchers.enabled())
                launchers.set_enabled(True)
                self.assertEqual(len(list(agent.parent.iterdir())), 1)
                info = plistlib.loads(agent.read_bytes())
                self.assertEqual(info['ProgramArguments'], [str(exe)])
                self.assertFalse(info['KeepAlive'])
                launchers.uninstall()
                self.assertFalse(agent.exists())
                self.assertTrue(exe.exists())
                self.assertEqual(data.read_bytes(), b'private unchanged data')
                launchers.set_enabled(True)
                info['ProgramArguments'] = ['/some/newer/source/launcher']
                agent.write_bytes(plistlib.dumps(info))
                before = agent.read_bytes()
                self.assertFalse(launchers.enabled())
                launchers.uninstall()
                self.assertEqual(agent.read_bytes(), before)
                agent.write_bytes(b'not a plist')
                launchers.set_enabled(False)
                self.assertEqual(agent.read_bytes(), b'not a plist')

    def test_frozen_volume_or_translocated_app_cannot_enable_startup(self):
        with patch.object(sys, 'platform', 'darwin'), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', '/Volumes/Preview/VoiceToClipboard.app/Contents/MacOS/VoiceToClipboard'):
            with self.assertRaisesRegex(RuntimeError, 'Move the app'):
                launchers.set_enabled(True)
