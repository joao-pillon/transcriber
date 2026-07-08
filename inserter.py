"""Entrega o texto transcrito: copia para o clipboard e cola na janela ativa."""

import time

import pyperclip
from pynput.keyboard import Controller, Key

import config

_keyboard = Controller()


def deliver(text: str):
    """Copia o texto e, se AUTO_PASTE estiver ligado, simula Ctrl+V."""
    if not text:
        return

    pyperclip.copy(text)

    if not config.AUTO_PASTE:
        return

    # Pequena pausa para garantir que o clipboard foi atualizado
    # e que o foco voltou para a janela do usuário.
    time.sleep(0.15)

    with _keyboard.pressed(Key.ctrl):
        _keyboard.press("v")
        _keyboard.release("v")
