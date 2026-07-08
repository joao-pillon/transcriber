"""Testador de microfone.

Uso:
    python testar_mic.py           -> lista dispositivos e testa o INPUT_DEVICE do config
    python testar_mic.py 3         -> testa o índice 3 (ignora o config)

Grava 3 segundos, mostra o nível de volume e diz se captou voz.
"""

import sys

import numpy as np
import sounddevice as sd

import config


def listar():
    print("=== Microfones disponíveis ===")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            api = sd.query_hostapis(d["hostapi"])["name"]
            print(f"  [{i}] {d['name']}  ({api})")
    print()


def testar(idx):
    nome = sd.query_devices(idx)["name"]
    print(f"Testando [{idx}] {nome}")
    print("Fale agora por 3 segundos...")

    dur = 3
    try:
        audio = sd.rec(
            int(dur * config.SAMPLE_RATE),
            samplerate=config.SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=idx,
        )
        sd.wait()
    except Exception as e:
        print(f"  ERRO ao abrir este dispositivo: {e}")
        print("  -> tente outro índice da lista acima.")
        return

    nivel = float(np.abs(audio).mean())
    pico = float(np.abs(audio).max())
    barra = "#" * min(int(nivel * 2000), 50)

    print(f"  nível médio: {nivel:.5f}  pico: {pico:.3f}")
    print(f"  [{barra:<50}]")
    if nivel < 0.001:
        print("  -> SILÊNCIO. Este não é o mic certo (ou está mudo). Tente outro índice.")
    else:
        print("  -> CAPTOU ÁUDIO! Use este índice em config.py: INPUT_DEVICE =", idx)


if __name__ == "__main__":
    listar()
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else config.INPUT_DEVICE
    if idx is None:
        idx = sd.default.device[0]
    testar(idx)
