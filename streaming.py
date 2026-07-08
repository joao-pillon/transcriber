"""Transcrição em STREAMING via OpenAI Realtime API.

Abre um WebSocket, transmite o áudio do microfone ao vivo (PCM16 24kHz)
e devolve o texto em pedaços (deltas) conforme você fala, mais o texto final.

Uso:
    s = StreamingSession(
        on_delta=lambda txt: ...,   # texto parcial acumulado (ao vivo)
        on_final=lambda txt: ...,   # texto final de um trecho de fala
        on_level=lambda lvl: ...,   # nível de volume 0..1 (p/ waveform)
    )
    s.start()   # começa a captar e transmitir
    ...
    s.stop()    # encerra; on_final recebe o que faltou
"""

import base64
import json
import threading

import numpy as np
import sounddevice as sd
import websocket  # websocket-client

import config

# Para transcrição, a API Realtime usa este endpoint.
WS_URL = "wss://api.openai.com/v1/realtime?intent=transcription"

# A Realtime API trabalha em 24kHz PCM16 mono.
STREAM_RATE = 24000


class StreamingSession:
    def __init__(self, on_delta=None, on_final=None, on_level=None):
        self._on_delta = on_delta or (lambda t: None)
        self._on_final = on_final or (lambda t: None)
        self._on_level = on_level or (lambda l: None)

        self._ws: websocket.WebSocketApp | None = None
        self._stream: sd.InputStream | None = None
        self._running = False
        self._ws_thread: threading.Thread | None = None
        self._connected = threading.Event()

        # Texto acumulado da fala atual (deltas vão somando aqui).
        self._current_text = ""

    # ─── Ciclo de vida ───────────────────────────────────────────────────
    def start(self):
        self._running = True
        self._current_text = ""
        self._connected.clear()

        self._ws = websocket.WebSocketApp(
            WS_URL,
            header=[f"Authorization: Bearer {config.OPENAI_API_KEY}"],
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._ws_thread = threading.Thread(target=self._ws.run_forever, daemon=True)
        self._ws_thread.start()

    def stop(self):
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._ws is not None:
            try:
                # Pede para finalizar o que ainda estiver no buffer.
                self._ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            except Exception:
                pass
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    # ─── WebSocket callbacks ─────────────────────────────────────────────
    def _on_open(self, ws):
        # Configura a sessão de transcrição.
        ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": STREAM_RATE},
                        "transcription": {
                            "model": config.OPENAI_REALTIME_MODEL,
                            **({"language": config.WHISPER_LANGUAGE}
                               if config.WHISPER_LANGUAGE else {}),
                        },
                        # VAD do servidor detecta começo/fim de fala sozinho.
                        "turn_detection": {"type": "server_vad"},
                    },
                },
            },
        }))
        self._connected.set()
        self._open_mic()

    def _on_message(self, ws, message):
        try:
            event = json.loads(message)
        except Exception:
            return
        etype = event.get("type", "")

        if etype.endswith("input_audio_transcription.delta"):
            self._current_text += event.get("delta", "")
            self._on_delta(self._current_text)
        elif etype.endswith("input_audio_transcription.completed"):
            final = event.get("transcript", self._current_text).strip()
            self._on_final(final)
            self._current_text = ""
        elif etype == "error":
            err = event.get("error", {})
            print(f"[streaming] erro da API: {err.get('message', err)}")

    def _on_error(self, ws, error):
        print(f"[streaming] erro no WebSocket: {error}")

    def _on_close(self, ws, code, msg):
        pass

    # ─── Captura do microfone ────────────────────────────────────────────
    def _open_mic(self):
        def callback(indata, frames, time_info, status):
            if not self._running or self._ws is None:
                return
            mono = indata[:, 0]
            # Nível p/ a waveform da UI.
            self._on_level(float(np.abs(mono).mean()) * 8.0)

            pcm16 = np.clip(mono, -1.0, 1.0)
            pcm16 = (pcm16 * 32767).astype(np.int16).tobytes()
            b64 = base64.b64encode(pcm16).decode("ascii")
            try:
                self._ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": b64,
                }))
            except Exception:
                pass

        self._stream = sd.InputStream(
            samplerate=STREAM_RATE,
            channels=1,
            dtype="float32",
            device=config.INPUT_DEVICE,
            blocksize=int(STREAM_RATE * 0.1),  # blocos de 100ms
            callback=callback,
        )
        self._stream.start()
