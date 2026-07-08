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
2. Descubra o índice do seu microfone (varia por máquina/driver):
   ```powershell
   python testar_mic.py
   ```
   Anote o índice que captou áudio e ajuste `INPUT_DEVICE` em `config.py`.

## Usar

```powershell
python main.py
```

1. Em **qualquer janela**, aperte **F9** → aparece o pop-up "Ouvindo…"
2. Fale.
3. Aperte **F9** de novo → "Finalizando…" → o texto é colado no cursor.

`Ctrl+C` no terminal para sair.

Pra não precisar abrir o terminal toda vez, crie um atalho para
`pythonw.exe main.py` na pasta Startup do Windows
(`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`) — isso é por
máquina, não vem pelo git.

## Ajustes (config.py)

| Quero… | Mude |
|---|---|
| Rodar 100% offline (sem OpenAI) | `TRANSCRIBE_MODE = "local"` |
| Mais velocidade (modo local) | `WHISPER_MODEL = "small"` |
| Outro atalho | `HOTKEY = "<ctrl>+<alt>+d"` |
| Fixar idioma (modo local) | `WHISPER_LANGUAGE = "pt"` |
| Só copiar (sem colar) | `AUTO_PASTE = False` |
| Outro microfone | `INPUT_DEVICE = <índice>` (veja com `python testar_mic.py`) |

## Notas

- O atalho global usa `RegisterHotKey` do Windows (não um hook de baixo
  nível), então convive bem com anti-cheats como o Vanguard (Riot Games),
  que bloqueiam hooks de teclado de outros processos.
- Modo local (`TRANSCRIBE_MODE = "local"`): sem GPU NVIDIA, roda em CPU.
  `medium` é preciso porém lento (~6-12s/frase); `small` é quase instantâneo.
- `INPUT_DEVICE` é específico de cada máquina — sempre rode `testar_mic.py`
  depois de clonar em um computador novo.
