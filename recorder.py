"""Gravação do microfone direto para a memória (sem salvar arquivo)."""

import numpy as np
import sounddevice as sd
import logging

import config
from mic import resolve_input_device


class Recorder:
    """Grava áudio do mic enquanto estiver ativo e devolve um array float32."""

    def __init__(self):
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time, status):
        # Chamado pela sounddevice em outra thread a cada bloco de áudio.
        if status:
            logging.getLogger(__name__).warning("Captura: %s", status)
        self._frames.append(indata.copy())

    def start(self):
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype="float32",
            device=resolve_input_device(),
            callback=self._callback,
        )
        try:
            self._stream.start()
        except Exception:
            self._stream.close()
            self._stream = None
            raise

    def stop(self) -> np.ndarray:
        """Para a gravação e devolve o áudio capturado (mono, 16kHz, float32)."""
        if self._stream is not None:
            stream, self._stream = self._stream, None
            try:
                stream.stop()
            finally:
                stream.close()

        if not self._frames:
            return np.zeros(0, dtype=np.float32)

        audio = np.concatenate(self._frames, axis=0).flatten()
        self._frames = []
        return audio
