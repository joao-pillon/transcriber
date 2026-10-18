import collections
import json
import logging
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import websocket

from streaming import StreamingSession


class Mic:
    instances = []

    def __init__(self, callback, **kwargs):
        self.callback = callback
        self.active = False
        self.closed = False
        self.instances.append(self)

    def start(self):
        self.active = True
        for _ in range(4):
            self.callback(np.zeros((2400, 1), dtype=np.float32), 2400, None, False)

    def stop(self):
        self.active = False

    def close(self):
        self.closed = True


class Socket:
    def __init__(self, mode="normal"):
        self.mode = mode
        self.events = collections.deque()
        self.sent = []
        self.closed = False
        self.threads = set()
        self.updates = 0

    def settimeout(self, timeout):
        pass

    def push(self, kind, **kwargs):
        self.events.append({"type": kind, **kwargs})

    def send(self, payload):
        self.threads.add(threading.get_ident())
        event = json.loads(payload)
        self.sent.append(event)
        if event["type"] == "session.update":
            self.updates += 1
            if self.mode == "api_error":
                self.push("error", error={"code": "invalid_api_key"})
            elif self.mode != "no_ack":
                if self.updates == 2 and self.mode == "empty_pending":
                    self.push("input_audio_buffer.committed", item_id="a")
                self.push("session.updated")
        elif event["type"] == "input_audio_buffer.commit":
            if self.mode in ("empty", "empty_pending"):
                self.push("error", error={"code": "input_audio_buffer_commit_empty"})
                if self.mode == "empty_pending":
                    self.push("conversation.item.input_audio_transcription.completed",
                              item_id="a", transcript="última frase")
            else:
                self.push("input_audio_buffer.committed", item_id="a")
                if self.mode != "no_final":
                    self.push("conversation.item.input_audio_transcription.completed",
                              item_id="a", transcript="última frase")

    def recv_data_frame(self, control_frame=False):
        self.threads.add(threading.get_ident())
        if self.mode == "disconnect" and self.updates:
            return websocket.ABNF.OPCODE_CLOSE, SimpleNamespace(data=b"")
        if self.events:
            return websocket.ABNF.OPCODE_TEXT, SimpleNamespace(data=json.dumps(self.events.popleft()))
        time.sleep(0.002)
        raise websocket.WebSocketTimeoutException()

    def ping(self, payload):
        pass

    def close(self, timeout=0):
        self.threads.add(threading.get_ident())
        self.closed = True


class StreamingTests(unittest.TestCase):
    def setUp(self):
        Mic.instances = []
        self.patches = [
            patch("streaming.sd.InputStream", Mic),
            patch("streaming.resolve_input_device", return_value=1),
            patch("streaming.describe", return_value="test mic"),
            patch("config.OPENAI_API_KEY", "test-key"),
            patch("config.STREAM_CONNECT_TIMEOUT", 0.1),
            patch("config.STREAM_FINAL_TIMEOUT", 0.1),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        logging.getLogger("streaming").addHandler(logging.NullHandler())
        logging.getLogger("streaming").propagate = False

    def run_session(self, mode="normal", connection_error=None, on_final=None):
        sock = Socket(mode)
        finals, errors = [], []
        done = threading.Event()
        def final(text):
            self.assertFalse(sock.closed, "Socket fechou antes de receber o texto final")
            finals.append(text)
            if on_final:
                on_final(text)
        session = StreamingSession(on_final=final, on_error=errors.append, on_done=done.set)
        session._on_ready = session.stop
        with patch("streaming.websocket.create_connection", side_effect=connection_error,
                   return_value=sock):
            session.start()
            self.assertTrue(done.wait(2), "Sessão não finalizou")
            session._thread.join(1)
        self.assertTrue(all(m.closed for m in Mic.instances), "Microfone vazou")
        self.assertLessEqual(len(sock.threads), 1, "Socket acessado por threads diferentes")
        return session, sock, finals, errors

    def test_waits_for_final_before_closing(self):
        _, sock, finals, errors = self.run_session()
        self.assertEqual(finals, ["última frase"])
        self.assertEqual(errors, [])
        self.assertTrue(sock.closed)

    def test_empty_vad_buffer_is_normal(self):
        _, _, finals, errors = self.run_session("empty")
        self.assertEqual((finals, errors), ([], []))

    def test_empty_commit_still_waits_for_earlier_turn(self):
        _, _, finals, errors = self.run_session("empty_pending")
        self.assertEqual(finals, ["última frase"])
        self.assertEqual(errors, [])

    def test_connection_failure_closes_microphone(self):
        _, _, _, errors = self.run_session(connection_error=OSError("offline"))
        self.assertEqual(len(errors), 1)

    def test_api_failure_closes_microphone(self):
        _, sock, _, errors = self.run_session("api_error")
        self.assertEqual(len(errors), 1)
        self.assertTrue(sock.closed)

    def test_disconnect_recovers(self):
        self.assertEqual(len(self.run_session("disconnect")[3]), 1)

    def test_connection_ack_timeout(self):
        self.assertEqual(len(self.run_session("no_ack")[3]), 1)

    def test_final_timeout_does_not_hang(self):
        self.assertEqual(len(self.run_session("no_final")[3]), 1)

    def test_paste_failure_also_cleans_up(self):
        def fail(text):
            raise OSError("clipboard locked")
        self.assertEqual(len(self.run_session(on_final=fail)[3]), 1)

    def test_stop_does_not_touch_socket_or_microphone(self):
        session = StreamingSession()
        start = time.monotonic()
        session.stop()
        self.assertLess(time.monotonic() - start, 0.02)
        self.assertIsNone(session._stream)

    def test_stop_during_connect_preserves_captured_audio(self):
        done = threading.Event()
        finals = []
        session = StreamingSession(on_done=done.set, on_final=finals.append)
        sock = Socket()
        def connect(*args, **kwargs):
            session.stop()
            return sock
        with patch("streaming.websocket.create_connection", side_effect=connect):
            session.start()
            self.assertTrue(done.wait(2))
        self.assertEqual(finals, ["última frase"])
        self.assertTrue(Mic.instances[0].closed)

    def test_audio_callback_never_blocks_on_full_queue(self):
        session = StreamingSession()
        data = np.zeros((2400, 1), dtype=np.float32)
        for _ in range(101):
            session._capture(data, 2400, None, False)
        self.assertEqual(session._audio.qsize(), 100)
        self.assertEqual(session._dropped, 1)

    def test_cancel_before_worker_starts_does_not_open_mic(self):
        done = threading.Event()
        session = StreamingSession(on_done=done.set)
        session.stop()
        session.start()
        self.assertTrue(done.wait(1))
        self.assertEqual(Mic.instances, [])

    def test_mic_start_failure_still_closes_stream(self):
        with patch.object(Mic, "start", side_effect=OSError("device unavailable")):
            self.assertEqual(len(self.run_session()[3]), 1)

    def test_cleanup_failure_still_notifies_app(self):
        with patch.object(Socket, "close", side_effect=OSError("already closed")):
            self.assertEqual(self.run_session()[2], ["última frase"])

    def test_capture_glitches_do_not_abort_dictation(self):
        # Overflow do PortAudio e fila cheia não podem derrubar o ditado inteiro.
        original = Mic.start
        def unstable(mic):
            original(mic)
            mic.callback(np.zeros((2400, 1), dtype=np.float32), 2400, None, True)
            for _ in range(101):
                mic.callback(np.zeros((2400, 1), dtype=np.float32), 2400, None, False)
        with patch.object(Mic, "start", unstable):
            _, _, finals, errors = self.run_session()
        self.assertEqual(errors, [])
        self.assertEqual(finals, ["última frase"])

    def test_transcript_completions_are_delivered_in_audio_order(self):
        finals = []
        session = StreamingSession(on_final=finals.append)
        for item in ("a", "b"):
            session._event({"type": "input_audio_buffer.committed", "item_id": item})
        session._event({"type": "conversation.item.input_audio_transcription.completed",
                        "item_id": "b", "transcript": "segundo"})
        self.assertEqual(finals, [])
        session._event({"type": "conversation.item.input_audio_transcription.completed",
                        "item_id": "a", "transcript": "primeiro"})
        self.assertEqual(finals, ["primeiro", "segundo"])


if __name__ == "__main__":
    unittest.main()
