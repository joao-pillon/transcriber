"""Ditado global F9. Operações de áudio/rede ficam fora da interface Qt."""

import ctypes
from ctypes import wintypes
import logging
import signal
import sys
import threading
import time

from diagnostics import setup_logging, install_qt_diagnostics, mark_run

# Antes de importar Qt, áudio, clipboard ou configuração.
if __name__ == "__main__":
    setup_logging()

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication

import config
from history import History
from hotkey import HotkeyListener
from inserter import deliver
from ui import Popup

log = logging.getLogger(__name__)
_mutex = None


class StreamingApp(QObject):
    ready = Signal()
    finished = Signal()
    failed = Signal(str)

    def __init__(self, popup, history=None):
        super().__init__()
        from streaming import StreamingSession

        self._session_factory = StreamingSession
        self.popup = popup
        self.history = history
        self._entry = None
        self._session = None
        self._state = "idle"
        self._final_acc = ""
        self._error = False
        self.ready.connect(self._ready)
        self.failed.connect(self._failed)
        self.finished.connect(self._finished)
        log.info("Modo streaming model=%s", config.OPENAI_REALTIME_MODEL)

    def on_toggle(self):
        if self._state == "stopping":
            log.info("F9 ignorado durante finalização")
            return
        if self._state == "idle":
            self._state = "starting"
            self._final_acc = ""
            self._entry = None
            self._error = False
            self.popup.show_connecting.emit()
            self._session = self._session_factory(
                on_delta=self._on_delta, on_final=self._on_final,
                on_level=self.popup.update_level.emit, on_ready=self.ready.emit,
                on_error=self.failed.emit, on_done=self.finished.emit,
            )
            try:
                self._session.start()
            except Exception:
                log.exception("Não foi possível iniciar o ditado")
                self._failed("Falha ao iniciar — veja .tmp/transcriber.log")
                self._finished()
        else:
            self._state = "stopping"
            self.popup.show_working.emit()
            self._session.stop()

    @Slot()
    def _ready(self):
        if self._state == "starting":
            self._state = "recording"
            self.popup.show_recording.emit()

    @Slot(str)
    def _failed(self, message):
        self._error = True
        self.popup.show_error.emit(message)

    @Slot()
    def _finished(self):
        self._state = "idle"
        self._session = None
        if self.history is not None and self._entry is not None:
            self.history.finish(self._entry, ok=not self._error)
            self._entry = None
            self.popup.history_changed.emit()
        if not self._error:
            self.popup.show_done.emit(self._final_acc.strip())

    def _on_delta(self, text):
        self.popup.update_text.emit(self._final_acc + (" " if self._final_acc else "") + text)

    def _on_final(self, text):
        if text:
            sep = " " if self._final_acc else ""
            self._final_acc += sep + text
            # Salva antes de colar: se a colagem falhar, o texto continua no histórico.
            if self.history is not None:
                self._entry = self.history.save(self._final_acc, self._entry, status="live")
                self.popup.history_changed.emit()
            # A thread da sessão serializa as colagens; nenhuma pausa na UI.
            deliver(sep + text)
            self.popup.update_text.emit(self._final_acc)

    def close(self):
        if self._session is not None:
            self._session.close()


class FileApp(QObject):
    completed = Signal(str)
    failed = Signal(str)
    recording = Signal()

    def __init__(self, popup, history=None):
        super().__init__()
        from recorder import Recorder

        self.popup = popup
        self.history = history
        self.recorder = Recorder()
        self.transcriber = None  # carrega fora da UI, somente quando necessário
        self._state = "idle"
        self.completed.connect(self._completed)
        self.failed.connect(self._failed)
        self.recording.connect(self._recording)

    def on_toggle(self):
        if self._state == "idle":
            self._state = "starting"
            self.popup.show_connecting.emit()
            threading.Thread(target=self._start, name="file-start", daemon=True).start()
        elif self._state == "recording":
            self._state = "working"
            self.popup.show_working.emit()
            threading.Thread(target=self._work, name="file-transcribe", daemon=True).start()

    def _start(self):
        try:
            self.recorder.start()
            self.recording.emit()
        except Exception:
            log.exception("Falha ao iniciar microfone")
            self.failed.emit("Falha no microfone — veja .tmp/transcriber.log")

    @Slot()
    def _recording(self):
        self._state = "recording"
        self.popup.show_recording.emit()

    def _work(self):
        started = time.monotonic()
        try:
            audio = self.recorder.stop()
            if audio.size and self.transcriber is None:
                from transcriber import Transcriber
                self.transcriber = Transcriber()
            text = self.transcriber.transcribe(audio) if audio.size else ""
            if text and self.history is not None:
                self.history.save(text)
                self.popup.history_changed.emit()
            if text:
                deliver(text)
            log.info("Arquivo transcrito seconds=%.2f chars=%d", time.monotonic()-started, len(text))
            self.completed.emit(text)
        except Exception:
            log.exception("Falha na transcrição/colagem")
            self.failed.emit("Falha ao transcrever/colar — tente F9 novamente")

    @Slot(str)
    def _completed(self, text):
        self._state = "idle"
        self.popup.show_done.emit(text)

    @Slot(str)
    def _failed(self, message):
        self._state = "idle"
        self.popup.show_error.emit(message)

    def close(self):
        # Não bloqueia o encerramento do Qt em uma chamada PortAudio.
        threading.Thread(target=self.recorder.stop, daemon=True).start()


def _insert_in_background(text):
    def run():
        try:
            deliver(text)
            log.info("Histórico inserido chars=%d", len(text))
        except Exception:
            log.exception("Falha ao inserir texto do histórico")
    # deliver espera o clipboard; a interface não para.
    threading.Thread(target=run, name="history-insert", daemon=True).start()


def _already_running():
    global _mutex
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    _mutex = kernel.CreateMutexW(None, False, "Local\\Transcriber-SingleInstance")
    if not _mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    return ctypes.get_last_error() == 183


def main():
    if _already_running():
        log.info("Transcriber já está rodando — saindo")
        return
    mark_run()
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)
    install_qt_diagnostics(qt_app)
    history = History()
    popup = Popup(history)
    use_streaming = config.USE_STREAMING and config.TRANSCRIBE_MODE == "openai"
    app = StreamingApp(popup, history) if use_streaming else FileApp(popup, history)
    listener = HotkeyListener(on_toggle=app.on_toggle, on_history=popup.toggle_history.emit)
    popup.insert_requested.connect(_insert_in_background)
    listener.start(popup)
    qt_app.aboutToQuit.connect(listener.stop)
    qt_app.aboutToQuit.connect(app.close)
    signal.signal(signal.SIGINT, lambda *_: qt_app.quit())
    signal_timer = QTimer(qt_app)
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(500)
    log.info("Pronto! Atalho=%s", config.HOTKEY)
    result = qt_app.exec()
    history.close()
    log.info("Encerramento normal result=%s", result)
    mark_run(clean=True)
    return result


if __name__ == "__main__":
    sys.exit(main())
