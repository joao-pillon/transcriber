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
INPUT_DEVICE = 1            # índice do mic do headset (entrada física, API MME).
                             #   None = mic padrão do Windows
                             #   liste opções com: python testar_mic.py

# ─── Atalho global ────────────────────────────────────────────────────────
# Combinação que liga/desliga a gravação (toggle). Sintaxe do pynput.
# Exemplos: "<ctrl>+b", "<ctrl>+<alt>+d", "<f9>"
HOTKEY = "<f9>"

# ─── Comportamento de saída ───────────────────────────────────────────────
# Se True, cola o texto na janela ativa (simula Ctrl+V). Se False, só copia.
AUTO_PASTE = True

# ─── UI ───────────────────────────────────────────────────────────────────
UI_WIDTH = 320
UI_HEIGHT = 90
UI_MARGIN_BOTTOM = 80        # distância do rodapé da tela (px)
UI_FADE_OUT_MS = 1200        # quanto tempo o "✅ Pronto" fica antes de sumir

# Paleta dark minimalista
COLOR_BG = "#1a1b26"
COLOR_TEXT = "#c0caf5"
COLOR_RECORDING = "#f7768e"  # vermelho/rosa
COLOR_WORKING = "#e0af68"    # âmbar
COLOR_DONE = "#9ece6a"       # verde
COLOR_ACCENT = "#7aa2f7"     # azul
