import queue
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock
from voice_to_clipboard.core.host_control import ControlServer, ListenerController, request


class HostControlTests(unittest.TestCase):
    def listener(self):
        listener = Mock(ident=1)
        listener.is_alive.return_value = False
        return listener

    def test_pause_releases_bindings_and_resume_discards_old_actions(self):
        first, second = self.listener(), self.listener()
        factory = Mock(side_effect=[first, second])
        enqueue = Mock()
        controller = ListenerController(factory, enqueue)
        controller.resume()
        old_callbacks = factory.call_args.args[0]
        old_callbacks['l']()
        old_generation = enqueue.call_args.args[0][0]
        controller.pause()
        first.stop.assert_called_once()
        first.join.assert_called_once_with(timeout=2)
        self.assertFalse(controller.accepts(old_generation))
        old_callbacks['u']()
        self.assertEqual(enqueue.call_count, 1)
        controller.resume()
        second.start.assert_called_once()
        self.assertFalse(controller.accepts(old_generation))
        old_callbacks['e']()
        self.assertEqual(enqueue.call_count, 1)
        factory.call_args.args[0]['u']()
        self.assertEqual(enqueue.call_count, 2)
        controller.pause()

    def test_resume_conflict_leaves_host_paused(self):
        listener = self.listener()
        listener.start.side_effect = RuntimeError('conflict')
        controller = ListenerController(lambda callbacks: listener, Mock())
        with self.assertRaisesRegex(RuntimeError, 'conflict'):
            controller.resume()
        self.assertTrue(controller.paused)
        listener.stop.assert_called_once()

    def test_resume_refuses_to_duplicate_slow_listener(self):
        listener = self.listener()
        controller = ListenerController(lambda callbacks: listener, Mock())
        controller.resume()
        listener.is_alive.return_value = True
        with self.assertRaisesRegex(RuntimeError, 'still stopping'):
            controller.pause()
        with self.assertRaisesRegex(RuntimeError, 'cannot resume'):
            controller.resume()

    def test_control_roundtrip_quit_ack_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'host.sock'
            server = ControlServer(path)
            results = queue.Queue()
            def client():
                try:
                    results.put(request(path, 'quit'))
                except Exception as exc:
                    results.put(exc)
            thread = threading.Thread(target=client)
            thread.start()
            deadline = time.monotonic() + 2
            while server.requests.empty() and time.monotonic() < deadline:
                time.sleep(.01)
            server.dispatch(lambda operation: {'state': 'stopping'})
            server.close()  # Immediate shutdown must not swallow the quit acknowledgement.
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(results.get(timeout=1), {'state': 'stopping'})
            self.assertFalse(path.exists())
            self.assertFalse(server.thread.is_alive())
