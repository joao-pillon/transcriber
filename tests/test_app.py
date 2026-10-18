import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import threading
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PySide6.QtWidgets import QApplication

from main import StreamingApp, FileApp
from ui import Popup

qt = QApplication.instance() or QApplication([])


def wait_for(predicate):
    deadline = time.monotonic() + 2
    while not predicate() and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(0.005)
    return predicate()


class AppTests(unittest.TestCase):
    def setUp(self):
        self.popup = Popup()
        self.addCleanup(self.popup.close)

    def test_streaming_ignores_repeated_f9_until_finalized(self):
        app = StreamingApp(self.popup)
        sessions = []
        def factory(**callbacks):
            session = Mock()
            session.callbacks = callbacks
            sessions.append(session)
            return session
        app._session_factory = factory
        app.on_toggle()
        app.on_toggle()
        app.on_toggle()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(app._state, "stopping")
        sessions[0].callbacks["on_done"]()
        qt.processEvents()
        app.on_toggle()
        self.assertEqual(len(sessions), 2)

    def test_streaming_error_is_visible_and_next_f9_restarts(self):
        app = StreamingApp(self.popup)
        # Testa falha síncrona de start, seguida do ciclo assíncrono de erro.
        session = Mock()
        session.start.side_effect = RuntimeError("missing key")
        app._session_factory = Mock(return_value=session)
        app.on_toggle()
        self.assertEqual(app._state, "idle")
        self.assertTrue(self.popup.isVisible())
        session.start.side_effect = None
        app.on_toggle()
        app.failed.emit("offline")
        app.finished.emit()
        self.assertEqual(app._state, "idle")
        self.assertEqual(self.popup._label.text(), "offline")

    def test_ui_responds_while_network_start_is_blocked(self):
        from test_streaming import Mic, Socket
        app = StreamingApp(self.popup)
        gate = threading.Event()
        entered = threading.Event()
        def connect(*args, **kwargs):
            entered.set()
            gate.wait(1)
            return Socket()
        with patch("config.OPENAI_API_KEY", "test"), \
             patch("streaming.sd.InputStream", Mic), \
             patch("streaming.resolve_input_device", return_value=1), \
             patch("streaming.describe", return_value="test"), \
             patch("streaming.websocket.create_connection", side_effect=connect):
            app.on_toggle()
            self.assertTrue(entered.wait(1))
            start = time.monotonic()
            app.on_toggle()
            for _ in range(20):
                qt.processEvents()
            self.assertLess(time.monotonic() - start, 0.2)
            self.assertEqual(app._state, "stopping")
            gate.set()
            # Evita qualquer alteração no clipboard real durante o teste.
            with patch("main.deliver"):
                self.assertTrue(wait_for(lambda: app._state == "idle"))

    def test_dictation_is_saved_before_paste_and_failure_marks_incomplete(self):
        import tempfile
        from history import History
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        history = History(os.path.join(folder.name, "history.db"))
        self.addCleanup(history.close)
        app = StreamingApp(self.popup, history)
        sessions = []
        app._session_factory = lambda **callbacks: sessions.append(callbacks) or Mock()
        app.on_toggle()
        with patch("main.deliver", side_effect=OSError("clipboard ocupado")):
            with self.assertRaises(OSError):
                sessions[0]["on_final"]("primeira parte")
        with patch("main.deliver"):
            sessions[0]["on_final"]("segunda parte")
        self.assertEqual(history.recent()[0]["status"], "live")
        sessions[0]["on_error"]("offline")
        sessions[0]["on_done"]()
        qt.processEvents()
        entries = history.recent()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["text"], "primeira parte segunda parte")
        self.assertEqual(entries[0]["status"], "error")
        # Cada F9 abre uma transcrição nova.
        app.on_toggle()
        with patch("main.deliver"):
            sessions[1]["on_final"]("outro ditado")
        sessions[1]["on_done"]()
        qt.processEvents()
        self.assertEqual([e["text"] for e in history.recent()], ["outro ditado", "primeira parte segunda parte"])
        self.assertEqual(history.recent()[0]["status"], "done")

    def test_file_failure_resets_state_and_prevents_overlapping_requests(self):
        app = FileApp(self.popup)
        app.recorder = Mock()
        app.recorder.stop.return_value = np.zeros(1600, dtype=np.float32)
        app.transcriber = Mock()
        gate = threading.Event()
        def fail(audio):
            gate.wait(1)
            raise OSError("network offline")
        app.transcriber.transcribe.side_effect = fail
        app._state = "recording"
        app.on_toggle()
        app.on_toggle()
        self.assertEqual(app._state, "working")
        self.assertEqual(app.recorder.start.call_count, 0)
        gate.set()
        self.assertTrue(wait_for(lambda: app._state == "idle"))
        self.assertEqual(app.transcriber.transcribe.call_count, 1)


if __name__ == "__main__":
    unittest.main()
