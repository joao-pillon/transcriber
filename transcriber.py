"""Transcrição de áudio.

Duas engines, escolhidas por config.TRANSCRIBE_MODE:
  - "openai": API Whisper da OpenAI (rápido, nuvem)
  - "local":  faster-whisper na máquina (offline, CPU)

Ambas expõem a mesma interface: Transcriber().transcribe(audio) -> str
"""

import config  # importa primeiro: define HF_HOME / carrega .env

import numpy as np


def _audio_to_wav_bytes(audio: np.ndarray) -> bytes:
    """Converte float32 [-1,1] mono em um WAV PCM16 na memória."""
    import io
    import wave

    pcm16 = np.clip(audio, -1.0, 1.0)
    pcm16 = (pcm16 * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16 bits
        wf.setframerate(config.SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())
    buf.seek(0)
    return buf.read()


class _OpenAITranscriber:
    def __init__(self):
        from openai import OpenAI

        if not config.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY não encontrada. Coloque-a no arquivo .env."
            )
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""

        wav = _audio_to_wav_bytes(audio)
        # A API espera um objeto tipo arquivo com nome (para inferir o formato).
        file_tuple = ("audio.wav", wav, "audio/wav")

        kwargs = {"model": config.OPENAI_MODEL, "file": file_tuple}
        if config.WHISPER_LANGUAGE:
            kwargs["language"] = config.WHISPER_LANGUAGE

        resp = self.client.audio.transcriptions.create(**kwargs)
        return resp.text.strip()


class _LocalTranscriber:
    def __init__(self):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
        )

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""

        segments, _info = self.model.transcribe(
            audio,
            language=config.WHISPER_LANGUAGE,
            beam_size=config.WHISPER_BEAM_SIZE,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments)
        return text.strip()


class Transcriber:
    """Fachada: escolhe a engine certa conforme config.TRANSCRIBE_MODE."""

    def __init__(self):
        if config.TRANSCRIBE_MODE == "openai":
            self._engine = _OpenAITranscriber()
        else:
            self._engine = _LocalTranscriber()

    def transcribe(self, audio: np.ndarray) -> str:
        return self._engine.transcribe(audio)
