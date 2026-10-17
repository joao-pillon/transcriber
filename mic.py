"""Escolha do microfone.

Índice de dispositivo no Windows muda quando algo é plugado/removido (ex.: uma
webcam nova empurra o headset de [1] para [3]). Por isso o mic é achado pelo
NOME (config.INPUT_DEVICE_NAME) a cada gravação; o índice fixo é só fallback.

O PortAudio só enumera os dispositivos quando é inicializado, então a lista é
relida antes de cada busca — senão um headset sem fio ligado depois que o app
abriu nunca aparece.
"""

import sounddevice as sd

import config


def _refresh_devices():
    """Reinicia o PortAudio p/ reler a lista de dispositivos (~40ms).

    Só chamar sem stream aberto: o terminate derruba qualquer stream ativo.
    """
    try:
        sd._terminate()
    except Exception as e:
        print(f"[mic] não consegui atualizar a lista de dispositivos: {e}")
        return
    sd._initialize()


def resolve_input_device():
    """Devolve o índice do mic a usar (ou None = padrão do Windows)."""
    _refresh_devices()
    wanted = (config.INPUT_DEVICE_NAME or "").strip().lower()
    if wanted:
        devices = sd.query_devices()
        matches = [
            i for i, d in enumerate(devices)
            if d["max_input_channels"] > 0 and wanted in d["name"].lower()
        ]
        # Prefere a API MME (a mesma do mic padrão): aceita 16/24kHz sem frescura.
        mme = [i for i in matches
               if sd.query_hostapis(devices[i]["hostapi"])["name"] == "MME"]
        if mme or matches:
            return (mme or matches)[0]
        print(f"[mic] '{config.INPUT_DEVICE_NAME}' não encontrado — usando fallback.")
    return config.INPUT_DEVICE


def describe(idx) -> str:
    """Nome legível do dispositivo, p/ log."""
    if idx is None:
        idx = sd.default.device[0]
    return f"[{idx}] {sd.query_devices(idx)['name']}"
