"""Realtime com captura não bloqueante e socket controlado por uma única thread."""

import base64
import json
import logging
import queue
import threading
import time
import uuid

import numpy as np
import sounddevice as sd
import websocket

import config
from mic import describe, resolve_input_device

log = logging.getLogger(__name__)
WS_URL = "wss://api.openai.com/v1/realtime?intent=transcription"
STREAM_RATE = 24000


class StreamingSession:
    """Uma instância por ditado. Só a thread de trabalho acessa/fecha o socket."""

    def __init__(self, on_delta=None, on_final=None, on_level=None,
                 on_ready=None, on_done=None, on_error=None):
        self._on_delta = on_delta or (lambda t: None)
        self._on_final = on_final or (lambda t: None)
        self._on_level = on_level or (lambda l: None)
        self._on_ready = on_ready or (lambda: None)
        self._on_done = on_done or (lambda: None)
        self._on_error = on_error or (lambda t: None)
        self._stop = threading.Event()
        self._abort = threading.Event()
        # Soluço do PortAudio só é contado: perder 100 ms é melhor que abortar o ditado.
        self._glitches = 0
        self._dropped = 0
        self._audio = queue.Queue(maxsize=100)  # no máximo 10s
        self._thread = None
        self._stream = None
        self._order = []
        self._partials = {}
        self._completed = {}
        self._delivered = set()
        self._id = uuid.uuid4().hex[:8]

    def start(self):
        if self._thread is not None:
            raise RuntimeError("Sessão já iniciada")
        if not config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY não encontrada no .env")
        self._thread = threading.Thread(target=self._run, name=f"ditado-{self._id}", daemon=True)
        self._thread.start()

    def stop(self):
        # Na UI: nenhuma chamada de rede/PortAudio ou join.
        self._stop.set()

    def close(self):
        self._abort.set()
        self._stop.set()

    def _capture(self, indata, frames, time_info, status):
        if self._stop.is_set() or self._abort.is_set():
            return
        if status:
            self._glitches += 1
        try:
            self._audio.put_nowait(indata[:, 0].copy())
        except queue.Full:
            self._dropped += 1

    def _open_mic(self):
        device = resolve_input_device()
        log.info("session=%s mic=%s", self._id, describe(device))
        self._stream = sd.InputStream(
            samplerate=STREAM_RATE, channels=1, dtype="float32", device=device,
            blocksize=2400, callback=self._capture,
        )
        self._stream.start()

    def _close_mic(self):
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

    @staticmethod
    def _settings(vad=True):
        return {"type": "session.update", "session": {
            "type": "transcription", "audio": {"input": {
                "format": {"type": "audio/pcm", "rate": STREAM_RATE},
                "transcription": {
                    "model": config.OPENAI_REALTIME_MODEL,
                    **({"language": config.WHISPER_LANGUAGE} if config.WHISPER_LANGUAGE else {}),
                },
                "turn_detection": {"type": "server_vad"} if vad else None,
            }},
        }}

    def _event(self, event):
        kind = event.get("type", "")
        item = event.get("item_id")
        if kind == "input_audio_buffer.committed":
            if item not in self._order and item not in self._delivered:
                self._order.append(item)
        elif kind.endswith("input_audio_transcription.delta"):
            self._partials[item] = self._partials.get(item, "") + event.get("delta", "")
            self._on_delta(self._partials[item])
        elif kind.endswith("input_audio_transcription.completed"):
            self._completed[item] = event.get("transcript", "").strip()
        elif kind.endswith("input_audio_transcription.failed"):
            raise RuntimeError("A API não conseguiu transcrever o trecho")
        elif kind == "error":
            err = event.get("error", {})
            code = err.get("code", "unknown")
            if code == "input_audio_buffer_commit_empty":
                return "empty"
            log.error("session=%s API code=%s", self._id, code)
            raise RuntimeError(f"Erro da API ({code})")
        while self._order and self._order[0] in self._completed:
            item = self._order.pop(0)
            text = self._completed.pop(item)
            if item not in self._delivered:
                self._on_final(text)
                self._delivered.add(item)
                log.info("session=%s trecho final chars=%d", self._id, len(text))
            self._partials.pop(item, None)
        return kind

    def _run(self):
        ws = None
        started = time.monotonic()
        sent = 0
        phase = "connect"
        deadline = started + config.STREAM_CONNECT_TIMEOUT
        commit_ack = False
        ping_at = started
        pong_deadline = None
        try:
            log.info("session=%s iniciando model=%s", self._id, config.OPENAI_REALTIME_MODEL)
            if self._stop.is_set():
                return
            # Guarda a primeira palavra enquanto o TLS conecta.
            self._open_mic()
            if self._stop.is_set():
                return
            ws = websocket.create_connection(
                WS_URL, header=[f"Authorization: Bearer {config.OPENAI_API_KEY}"],
                timeout=config.STREAM_CONNECT_TIMEOUT,
            )
            ws.send(json.dumps(self._settings()))
            while not self._abort.is_set():
                now = time.monotonic()
                if self._stream is not None and not self._stream.active:
                    raise RuntimeError("Microfone desconectado; reconecte e aperte F9")
                if now - started >= config.STREAM_MAX_SECONDS:
                    self._stop.set()
                if self._stop.is_set() and self._stream is not None:
                    self._close_mic()
                    log.info("session=%s captura encerrada seconds=%.2f", self._id, now - started)
                if phase == "capture":
                    ws.settimeout(config.STREAM_IO_TIMEOUT)
                    for _ in range(10):
                        try:
                            mono = self._audio.get_nowait()
                        except queue.Empty:
                            break
                        self._on_level(float(np.abs(mono).mean()) * 8.0)
                        pcm = (np.clip(mono, -1, 1) * 32767).astype("<i2").tobytes()
                        ws.send(json.dumps({"type": "input_audio_buffer.append",
                                            "audio": base64.b64encode(pcm).decode("ascii")}))
                        sent += len(mono)
                    if self._stop.is_set() and self._audio.empty():
                        # Confirma VAD desligado antes do commit: um commit automático
                        # antigo não pode confirmar o último trecho por engano.
                        ws.send(json.dumps(self._settings(vad=False)))
                        phase = "disable_vad"
                        deadline = time.monotonic() + config.STREAM_FINAL_TIMEOUT
                if now - ping_at >= 15:
                    ws.settimeout(config.STREAM_IO_TIMEOUT)
                    ws.ping(self._id)
                    ping_at = now
                    pong_deadline = now + 10
                if pong_deadline is not None and now > pong_deadline:
                    raise TimeoutError("Conexão sem resposta; aperte F9 para reconectar")
                if phase != "capture" and now > deadline:
                    raise TimeoutError("Tempo de conexão/transcrição esgotado; tente F9 novamente")
                ws.settimeout(0.05)
                try:
                    opcode, frame = ws.recv_data_frame(control_frame=True)
                except websocket.WebSocketTimeoutException:
                    continue
                if opcode == websocket.ABNF.OPCODE_CLOSE:
                    raise ConnectionError("Conexão encerrada; aperte F9 para reconectar")
                if opcode == websocket.ABNF.OPCODE_PONG:
                    pong_deadline = None
                    continue
                if opcode != websocket.ABNF.OPCODE_TEXT:
                    continue
                kind = self._event(json.loads(frame.data))
                if phase == "connect" and kind in ("session.updated", "transcription_session.updated"):
                    phase = "capture"
                    log.info("session=%s conexão pronta ms=%.0f", self._id, (time.monotonic()-started)*1000)
                    if not self._stop.is_set():
                        self._on_ready()
                elif phase == "disable_vad" and kind in ("session.updated", "transcription_session.updated"):
                    if sent < STREAM_RATE // 10:
                        commit_ack = True
                    else:
                        ws.settimeout(config.STREAM_IO_TIMEOUT)
                        ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                    phase = "finalize"
                elif phase == "finalize" and kind in ("input_audio_buffer.committed", "empty"):
                    commit_ack = True
                if phase == "finalize" and commit_ack and not self._order:
                    break
        except Exception as exc:
            log.exception("session=%s falha phase=%s", self._id, phase)
            self._on_error(str(exc) if isinstance(exc, (RuntimeError, TimeoutError, ConnectionError))
                           else "Falha de conexão ou microfone — tente F9 novamente")
        finally:
            try:
                self._close_mic()
            except Exception:
                log.exception("session=%s falha ao fechar mic", self._id)
            if ws is not None:
                try:
                    ws.close(timeout=0)
                except Exception:
                    log.exception("session=%s falha ao fechar conexão", self._id)
            log.info("session=%s encerrada seconds=%.2f audio_seconds=%.2f", self._id,
                     time.monotonic() - started, sent / STREAM_RATE)
            if self._glitches or self._dropped:
                log.warning("session=%s captura instável status=%d blocos_perdidos=%d",
                            self._id, self._glitches, self._dropped)
            self._on_done()
