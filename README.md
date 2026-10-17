# Transcriber

Ditado por voz. Aperte um atalho global (F9), fale, aperte de novo e o texto
é colado onde o cursor estiver.

Por padrão usa a API da OpenAI (streaming ao vivo, precisa de internet e de
chave). Também dá pra rodar 100% offline com faster-whisper local — veja
`TRANSCRIBE_MODE` em `config.py`.

## Configurar (em cada máquina nova)

```powershell
pip install -r requirements.txt
```

1. Copie `.env.example` para `.env` e cole sua chave:
   ```
   OPENAI_API_KEY=sk-...
   ```
2. Descubra qual é o seu microfone:
   ```powershell
   python testar_mic.py
   ```
   Ponha um trecho do nome do mic que captou áudio em `INPUT_DEVICE_NAME`
   (`config.py`). Nome, não índice: os índices mudam quando você pluga algo.

## Usar

```powershell
python main.py
```

1. Em **qualquer janela**, aperte **F9** → aparece o pop-up "Ouvindo…"
2. Fale.
3. Aperte **F9** de novo → "Finalizando…" → o texto é colado no cursor.

`Ctrl+C` no terminal para sair.

Pra iniciar com o Windows, crie uma Scheduled Task "ao fazer logon" que rode
`pythonw.exe main.py` (pasta de trabalho = a do projeto). Evite a pasta Startup:
ela fica atrás da fila lenta de apps do Run e pode demorar minutos. Isso é por
máquina, não vem pelo git. Sob `pythonw` os erros vão para `.tmp/transcriber.log`.

## Ajustes (config.py)

| Quero… | Mude |
|---|---|
| Rodar 100% offline (sem OpenAI) | `TRANSCRIBE_MODE = "local"` |
| Mais velocidade (modo local) | `WHISPER_MODEL = "small"` |
| Outro atalho | `HOTKEY = "<ctrl>+<alt>+d"` |
| Fixar idioma (modo local) | `WHISPER_LANGUAGE = "pt"` |
| Só copiar (sem colar) | `AUTO_PASTE = False` |
| Outro microfone | `INPUT_DEVICE_NAME = "trecho do nome"` (veja com `python testar_mic.py`) |

## Notas

- O atalho global usa `RegisterHotKey` do Windows (não um hook de baixo
  nível), então convive bem com anti-cheats como o Vanguard (Riot Games),
  que bloqueiam hooks de teclado de outros processos.
- Modo local (`TRANSCRIBE_MODE = "local"`): sem GPU NVIDIA, roda em CPU.
  `medium` é preciso porém lento (~6-12s/frase); `small` é quase instantâneo.
- `INPUT_DEVICE_NAME` é específico de cada máquina — sempre rode `testar_mic.py`
  depois de clonar em um computador novo.
