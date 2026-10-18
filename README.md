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

O painel mostra o tempo do ditado e uma animação que acompanha o volume da voz.
Arraste a faixa superior para posicionar o painel; a posição é mantida durante
a execução. As animações são suspensas enquanto o painel está oculto.

## Histórico

Cada ciclo de F9 vira uma transcrição salva em `data/history.db` (só o texto,
sem áudio; fica fora do git). Cada trecho é salvo assim que chega, antes de
colar: se a colagem ou a conexão falhar, o texto continua lá, marcado como
"incompleta".

`Ctrl+F9` (ou a setinha no canto do painel) abre o histórico abaixo do cartão.
Em cada transcrição: **copiar** ou **inserir** direto na janela onde você está
escrevendo (o painel nunca rouba o foco). Mantém as 500 mais recentes.
O atalho e o limite ficam em `HISTORY_HOTKEY` e `HISTORY_LIMIT` no `config.py`.

Pra iniciar com o Windows, crie uma Scheduled Task "ao fazer logon" que rode
`pythonw.exe main.py` (pasta de trabalho = a do projeto). Evite a pasta Startup:
ela fica atrás da fila lenta de apps do Run e pode demorar minutos. Isso é por
máquina, não vem pelo git. Os logs ficam em `.tmp/transcriber.log`, tanto com
`python` quanto com `pythonw`.

## Diagnóstico de erros e travamentos

- `.tmp/transcriber.log`: horários, identificador de cada ditado, conexão,
  duração, falhas de microfone, rede e colagem, com traceback. O arquivo gira
  a cada 2 MB e mantém três cópias anteriores.
- `.tmp/faults.log`: pilhas de execução em falhas nativas e quando a interface
  passa mais de 8 segundos sem responder.
- `.tmp/last-run.json`: indica se a execução anterior encerrou normalmente.
  Um encerramento forçado é avisado no próximo início.

Os logs de diagnóstico não salvam áudio, chave da API ou texto ditado.

F9 inicia a captura enquanto a conexão é preparada. F9 novamente mostra
“Finalizando…” e espera os trechos finais antes de fechar a conexão. Durante
essa finalização, novos toques são ignorados para evitar ditados sobrepostos.
Se a rede ou o microfone falhar, aparece um aviso e F9 permite tentar novamente.
Uma gravação contínua finaliza aos 55 minutos, antes do limite do servidor.

Para acompanhar os erros:

```powershell
Get-Content .tmp/transcriber.log -Tail 80 -Wait
```

Para rodar os testes de falhas, ordenação de trechos, limpeza do microfone
e resposta da interface (sem chamadas à API nem colagem real):

```powershell
python -m unittest discover -s tests -v
```

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
