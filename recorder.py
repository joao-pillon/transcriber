"""Gravação do microfone direto para a memória (sem salvar arquivo)."""

import numpy as np
import sounddevice as sd

import config


class Recorder:
    """Grava áudio do mic enquanto estiver ativo e devolve um array float32."""

    def __init__(self):
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time, status):
        # Chamado pela sounddevice em outra thread a cada bloco de áudio.
        self._frames.append(indata.copy())

    def start(self):
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype="float32",
            device=config.INPUT_DEVICE,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Para a gravação e devolve o áudio capturado (mono, 16kHz, float32)."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._frames:
            return np.zeros(0, dtype=np.float32)

        audio = np.concatenate(self._frames, axis=0).flatten()
        self._frames = []
        return audio
