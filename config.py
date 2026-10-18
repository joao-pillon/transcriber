"""Configuração central do Transcriber.

Mude aqui o modelo, idioma, atalho e cores — sem mexer no resto do código.
"""

import os

from dotenv import load_dotenv

# Carrega o .env do projeto (OPENAI_API_KEY etc.).
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ─── Modo de transcrição ──────────────────────────────────────────────────
# "openai" = API da nuvem (rápido, ~1-2s, precisa de internet e da chave).
# "local"  = faster-whisper na sua máquina (offline, grátis, mas lento em CPU).
TRANSCRIBE_MODE = "openai"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "whisper-1"            # usado no modo não-streaming (arquivo)
OPENAI_REALTIME_MODEL = "gpt-4o-transcribe"  # usado no streaming ao vivo

# Streaming: texto aparece enquanto você fala (via Realtime API).
# Se False, usa o modo arquivo (grava tudo, depois transcreve).
USE_STREAMING = True

# Limites de espera: falhas retornam ao estado pronto, sem bloquear a interface.
STREAM_CONNECT_TIMEOUT = 8.0
STREAM_IO_TIMEOUT = 2.0
STREAM_FINAL_TIMEOUT = 12.0
STREAM_MAX_SECONDS = 55 * 60  # finaliza antes do limite de 60 minutos do servidor
FILE_API_TIMEOUT = 30.0

# ─── Cache do modelo LOCAL ────────────────────────────────────────────────
# (só usado quando TRANSCRIBE_MODE == "local")
# O C: está cheio, então guardamos o modelo Whisper aqui no F:.
# Precisa ser definido ANTES de qualquer import do faster-whisper/huggingface.
_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(_MODELS_DIR, exist_ok=True)
os.environ["HF_HOME"] = _MODELS_DIR
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# ─── Whisper ──────────────────────────────────────────────────────────────
# Modelos (do mais leve ao mais pesado): tiny, base, small, medium, large-v3
# Em CPU, "medium" é preciso porém lento (~6-12s/frase).
# Se achar lento, troque para "small" — é só mudar esta linha.
WHISPER_MODEL = "small"

# Idioma: None = auto-detecta (PT/EN misturado). Ou fixe: "pt", "en"...
WHISPER_LANGUAGE = "pt"

# "cpu" ou "cuda". Você não tem GPU NVIDIA, então "cpu".
WHISPER_DEVICE = "cpu"

# Qualidade x velocidade da busca. 1 = mais rápido (bom p/ ditado curto),
# 5 = mais preciso porém mais lento.
WHISPER_BEAM_SIZE = 1

# Precisão dos cálculos. "int8" é o mais rápido em CPU sem perder muita qualidade.
WHISPER_COMPUTE_TYPE = "int8"

# ─── Áudio ────────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000          # Whisper espera 16kHz
CHANNELS = 1                 # mono
# Mic escolhido pelo NOME (trecho, sem diferenciar maiúsculas) — sobrevive a
# plugar/remover dispositivos, que embaralha os índices. "" = desliga a busca.
INPUT_DEVICE_NAME = "CORSAIR"    # headset Corsair HS80
INPUT_DEVICE = None          # fallback se o nome não for achado (índice ou
                             #   None = mic padrão do Windows)
                             #   liste opções com: python testar_mic.py

# ─── Atalho global ────────────────────────────────────────────────────────
# Combinação que liga/desliga a gravação (toggle). Sintaxe do pynput.
# Exemplos: "<ctrl>+b", "<ctrl>+<alt>+d", "<f9>"
HOTKEY = "<f9>"

# Abre/fecha o histórico de transcrições sem tirar o foco da janela. "" = desliga.
HISTORY_HOTKEY = "<ctrl>+<f9>"

# ─── Histórico ────────────────────────────────────────────────────────────
# Cada ciclo de F9 vira uma transcrição salva localmente (só o texto, sem áudio).
HISTORY_PATH = os.path.join(os.path.dirname(__file__), "data", "history.db")
HISTORY_LIMIT = 500          # mantém as N mais recentes
UI_HISTORY_ROWS = 4          # linhas visíveis no painel sem rolar

# ─── Comportamento de saída ───────────────────────────────────────────────
# Se True, cola o texto na janela ativa (simula Ctrl+V). Se False, só copia.
AUTO_PASTE = True

# ─── UI ───────────────────────────────────────────────────────────────────
UI_WIDTH = 500
UI_HEIGHT = 126
UI_MARGIN_BOTTOM = 80        # distância do rodapé da tela (px)
UI_FADE_OUT_MS = 0           # ms que o texto final fica na tela (0 = some na hora)

# Grafite + menta; azul na conexão, âmbar no processamento e coral nos erros.
COLOR_BG = "#101817"
COLOR_TEXT = "#e4efe9"
COLOR_CONNECTING = "#a2c4f2"
COLOR_RECORDING = "#75e3bf"
COLOR_WORKING = "#e6c98c"
COLOR_DONE = "#91ebc4"
COLOR_ACCENT = "#75e3bf"
COLOR_ERROR = "#f396a3"
