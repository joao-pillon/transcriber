"""Transcriber — fala em qualquer janela, atalho global.

Aperte o atalho (Ctrl+B por padrão) para começar; o texto aparece ao vivo
e é colado onde o cursor estiver. Aperte de novo para encerrar.

Modos (config.py):
  - USE_STREAMING=True  -> texto ao vivo via OpenAI Realtime (recomendado)
  - USE_STREAMING=False -> grava tudo, depois transcreve (arquivo)
"""

import ctypes
import os
import sys
import threading

# Sob pythonw.exe (início com o Windows) não há console: sem isso qualquer erro
# de boot some em silêncio. Redireciona para um log, ANTES dos imports pesados.
if sys.stdout is None or sys.stderr is None:
    _log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp")
    os.makedirs(_log_dir, exist_ok=True)
    sys.stdout = sys.stderr = open(
        os.path.join(_log_dir, "transcriber.log"), "a", buffering=1, encoding="utf-8"
    )

from PySide6.QtWidgets import QApplication

import config
from hotkey import HotkeyListener
from inserter import deliver
from ui import Popup


class StreamingApp:
    """Modo ao vivo: transmite o mic e cola cada trecho final conforme chega."""

    def __init__(self, popup: Popup):
        from streaming import StreamingSession

        self.popup = popup
        self._active = False
        self._lock = threading.Lock()
        self._final_acc = ""   # tudo que já foi colado (p/ o "done")
        self._finish_timer: threading.Timer | None = None

        self._session = StreamingSession(
            on_delta=self._on_delta,
            on_final=self._on_final,
            on_level=lambda lvl: self.popup.update_level.emit(lvl),
        )
        print(f"Modo: streaming ao vivo (OpenAI {config.OPENAI_REALTIME_MODEL}).")
        print("Pronto para transcrever.")

    def on_toggle(self):
        with self._lock:
            if not self._active:
                # "done" pendente da gravação anterior não pode fechar esta.
                if self._finish_timer is not None:
                    self._finish_timer.cancel()
                    self._finish_timer = None
                self._active = True
                self._final_acc = ""
                try:
                    self._session.start()
                except Exception as e:
                    self._active = False
                    print(f"[ERRO] Não consegui iniciar o streaming: {e}")
                    self.popup.show_error.emit("Falha ao conectar — veja o terminal")
                    return
                self.popup.show_recording.emit()
            else:
                self._active = False
                self.popup.show_working.emit()
                self._session.stop()
                # dá um instante para o último "completed" chegar
                self._finish_timer = threading.Timer(0.6, self._finish)
                self._finish_timer.start()

    def _on_delta(self, text: str):
        # texto parcial acumulado: só mostra ao vivo (ainda não cola)
        self.popup.update_text.emit(self._final_acc + text)

    def _on_final(self, text: str):
        if not text:
            return
        # cola este trecho finalizado e guarda
        sep = " " if self._final_acc else ""
        deliver(sep + text)
        self._final_acc += sep + text
        self.popup.update_text.emit(self._final_acc)

    def _finish(self):
        with self._lock:
            if self._active:  # nova gravação começou nesse meio-tempo
                return
            self._finish_timer = None
            text = self._final_acc.strip()
        self.popup.show_done.emit(text)


class FileApp:
    """Modo arquivo: grava tudo, transcreve no fim (sem streaming)."""

    def __init__(self, popup: Popup):
        from recorder import Recorder
        from transcriber import Transcriber

        self.popup = popup
        self.recorder = Recorder()
        if config.TRANSCRIBE_MODE == "openai":
            print(f"Modo: arquivo (OpenAI {config.OPENAI_MODEL}).")
        else:
            print(f"Carregando modelo Whisper local '{config.WHISPER_MODEL}'…")
        self.transcriber = Transcriber()
        print("Pronto para transcrever.")

        self._recording = False
        self._lock = threading.Lock()

    def on_toggle(self):
        with self._lock:
            if not self._recording:
                self._recording = True
                try:
                    self.recorder.start()
                except Exception as e:
                    self._recording = False
                    print(f"[ERRO] microfone (INPUT_DEVICE_NAME={config.INPUT_DEVICE_NAME!r}, "
                          f"INPUT_DEVICE={config.INPUT_DEVICE}): {e}")
                    self.popup.show_error.emit("Mic inválido — veja o terminal")
                    return
                self.popup.show_recording.emit()
            else:
                self._recording = False
                audio = self.recorder.stop()
                self.popup.show_working.emit()
                threading.Thread(target=self._work, args=(audio,), daemon=True).start()

    def _work(self, audio):
        text = self.transcriber.transcribe(audio)
        if text:
            deliver(text)
        self.popup.show_done.emit(text)


def _already_running() -> bool:
    """Mutex nomeado: uma segunda instância sairia no conflito do atalho."""
    ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\Transcriber-SingleInstance")
    return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def main():
    if _already_running():
        print("Transcriber já está rodando — saindo.")
        return

    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    popup = Popup()

    use_streaming = config.USE_STREAMING and config.TRANSCRIBE_MODE == "openai"
    app = StreamingApp(popup) if use_streaming else FileApp(popup)

    listener = HotkeyListener(on_toggle=app.on_toggle)
    listener.start(popup)

    print(f"Pronto! Aperte {config.HOTKEY} em qualquer janela.")
    print("Ctrl+C aqui no terminal para sair.")

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
