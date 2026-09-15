import json
from pathlib import Path
import signal
import struct
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from voice_to_clipboard.platform import processes, files
from voice_to_clipboard.worker import client, transport, protocol
from voice_to_clipboard.core.lifecycle import stop_on_interrupt
from voice_to_clipboard.ui import hotkeys


class LifecycleTests(unittest.TestCase):
    def test_platform_process_isolation(self):
        for platform in ('win32', 'linux', 'darwin'):
            fake = SimpleNamespace(CREATE_NEW_PROCESS_GROUP=512, Popen=Mock())
            with patch.object(processes.sys, 'platform', platform), patch.object(processes, 'subprocess', fake):
                processes.spawn_background(['python', 'worker'])
            options = fake.Popen.call_args.kwargs
            self.assertEqual(options, {'close_fds': True, **(
                {'creationflags': 512} if platform == 'win32' else {'start_new_session': True})})

    def test_permission_retry_does_not_launch_or_delete_live_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            endpoint = Path(directory) / 'worker.sock'
            endpoint.write_text('live endpoint')
            sock = Mock()
            sock.recv.side_effect = [struct.pack('!I', 12), b'{"ok": true}']
            with patch.object(client, 'connect', side_effect=[PermissionError('busy'), sock]), patch.object(client, 'spawn_background') as spawn:
                model = client.RemoteModel('test', 'auto', Path(directory))
                model.close()
            spawn.assert_not_called()
            self.assertEqual(endpoint.read_text(), 'live endpoint')

    def test_permission_retry_has_deadline_and_path(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(client, 'connect', side_effect=PermissionError('busy')), patch.object(client, 'spawn_background') as spawn, patch.object(client.time, 'monotonic', side_effect=[0, 0, 16]):
                with self.assertRaisesRegex(TimeoutError, 'worker.sock'):
                    client.RemoteModel('test', 'auto', Path(directory))
            spawn.assert_not_called()

    def test_windows_file_retry_and_permanent_failure(self):
        with patch.object(files.sys, 'platform', 'win32'), patch.object(files.time, 'sleep'):
            operation = Mock(side_effect=[PermissionError(), None])
            files.retry_file(operation, 'worker.sock')
            self.assertEqual(operation.call_count, 2)
            with patch.object(files.time, 'monotonic', side_effect=[0, 3]):
                with self.assertRaisesRegex(PermissionError, 'worker.sock'):
                    files.retry_file(Mock(side_effect=PermissionError()), 'worker.sock')

    def test_endpoint_replace_retries_without_removing_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'endpoint'
            path.write_text('previous')
            original = transport.os.replace
            attempts = []
            def replace(source, target):
                attempts.append(source)
                if len(attempts) == 1:
                    self.assertEqual(path.read_text(), 'previous')
                    raise PermissionError('sharing violation')
                return original(source, target)
            with patch.object(transport.sys, 'platform', 'win32'), patch.object(transport.os, 'replace', side_effect=replace):
                with transport.Server(path):
                    self.assertEqual(len(attempts), 2)
                    self.assertIn('token', json.loads(path.read_text()))
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_fragmented_frame_and_eof(self):
        payload = json.dumps({'segments': ['Привіт']}).encode()
        wire = struct.pack('!I', len(payload)) + payload
        self.assertEqual(protocol.receive(Mock(recv=Mock(side_effect=[bytes([b]) for b in wire]))), {'segments': ['Привіт']})
        with self.assertRaises(EOFError):
            protocol.receive(Mock(recv=Mock(side_effect=[b'\0', b''])))
        with self.assertRaises(ConnectionResetError):
            protocol.receive(Mock(recv=Mock(side_effect=ConnectionResetError())))

    def test_fragmented_authentication_acknowledgement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'endpoint'
            path.write_text(json.dumps({'port': 42, 'token': 'x' * 64}))
            sock = Mock(); sock.recv.side_effect = [b'O', b'K']
            with patch.object(transport.sys, 'platform', 'win32'), patch.object(transport.socket, 'socket', return_value=sock):
                self.assertIs(transport.connect(path), sock)

    def test_sigint_requests_stop_and_restores_handler(self):
        event = threading.Event()
        previous = signal.getsignal(signal.SIGINT)
        with stop_on_interrupt(event):
            signal.raise_signal(signal.SIGINT)
            self.assertTrue(event.is_set())
            signal.raise_signal(signal.SIGINT)  # draining must not lose the tail
        self.assertIs(signal.getsignal(signal.SIGINT), previous)

    def test_quit_drains_owned_child(self):
        process = Mock(); process.poll.side_effect = [None, 0]
        with patch.object(hotkeys, 'try_stop_running') as stop, patch.object(hotkeys.time, 'sleep'), patch('builtins.print'):
            hotkeys.drain_children([process])
        stop.assert_called_once()
        process.terminate.assert_not_called()

    def test_second_interrupt_cancels_only_owned_children(self):
        process = Mock(); process.poll.return_value = None
        with patch.object(hotkeys, 'try_stop_running'), patch.object(hotkeys.time, 'sleep', side_effect=KeyboardInterrupt), patch('builtins.print'):
            hotkeys.drain_children([process])
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=2)
