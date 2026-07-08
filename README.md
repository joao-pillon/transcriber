# Transcriber

Ditado por voz com Whisper local. Aperte um atalho global, fale, aperte de novo
e o texto é colado onde o cursor estiver. Tudo offline, sem custo, privado.

## Instalar

```powershell
pip install -r requirements.txt
```

## Usar

```powershell
python main.py
```

1. Em **qualquer janela**, aperte **Ctrl+B** → aparece o pop-up "🔴 Gravando…"
2. Fale.
3. Aperte **Ctrl+B** de novo → "⏳ Transcrevendo…" → o texto é colado no cursor.

`Ctrl+C` no terminal para sair.

> Na **primeira execução** o modelo Whisper é baixado (~1.5 GB para `medium`).
> Depois fica em cache e abre rápido.

## Ajustes (config.py)

| Quero… | Mude |
|---|---|
| Mais velocidade | `WHISPER_MODEL = "small"` |
| Outro atalho | `HOTKEY = "<ctrl>+<alt>+d"` |
| Fixar idioma | `WHISPER_LANGUAGE = "pt"` |
| Só copiar (sem colar) | `AUTO_PASTE = False` |
| Outro microfone | `INPUT_DEVICE = <índice>` (veja com `python -m sounddevice`) |

## Notas

- Sem GPU NVIDIA, roda em CPU. `medium` é preciso porém lento (~6-12s/frase).
  Se quiser instantâneo, use `small`.
- O atalho global pode exigir rodar o terminal **como administrador** caso a
  janela ativa seja um app elevado.
