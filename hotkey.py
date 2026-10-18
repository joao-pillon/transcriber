"""Atalho global (toggle) via RegisterHotKey nativo do Windows.

Não usamos um hook de teclado de baixo nível (como o do pynput) porque
anti-cheats com driver de kernel — caso do Vanguard (Riot Games), que fica
carregado o tempo todo, não só durante o jogo — bloqueiam esse tipo de hook
de outros processos. RegisterHotKey é o mesmo mecanismo que atalhos nativos
do Windows usam e não sofre esse bloqueio.
"""

import ctypes
import logging
import time
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

import config

user32 = ctypes.windll.user32

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312

_MOD_MAP = {"ctrl": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "cmd": MOD_WIN, "win": MOD_WIN}
_VK_FKEYS = {f"f{i}": 0x70 + (i - 1) for i in range(1, 25)}  # F1..F24


def _parse_hotkey(spec: str):
    """Converte a sintaxe estilo pynput do config.HOTKEY (ex: "<f9>",
    "<ctrl>+<alt>+d") em (modificadores, vk) para RegisterHotKey."""
    mods = 0
    vk = None
    for tok in spec.split("+"):
        key = tok.strip().strip("<>").lower()
        if key in _MOD_MAP:
            mods |= _MOD_MAP[key]
        elif key in _VK_FKEYS:
            vk = _VK_FKEYS[key]
        elif len(key) == 1:
            vk = ord(key.upper())
        else:
            raise ValueError(f"Tecla não reconhecida em HOTKEY: {tok!r}")
    if vk is None:
        raise ValueError(f"HOTKEY sem tecla principal: {spec!r}")
    return mods, vk


class _NativeFilter(QAbstractNativeEventFilter):
    """Escuta as mensagens nativas do Windows e detecta o WM_HOTKEY."""

    def __init__(self, callbacks):
        super().__init__()
        self._callbacks = callbacks  # id do atalho -> callback

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in self._callbacks:
                self._callbacks[msg.wParam]()
        return False, 0


class HotkeyListener:
    """Registra config.HOTKEY globalmente e dispara `on_toggle` a cada acionamento.
    `on_history` (opcional) fica em config.HISTORY_HOTKEY."""

    _HOTKEY_ID = 1
    _HISTORY_ID = 2
    _MIN_INTERVAL = 0.35  # ignora acionamentos repetidos vindos muito rápido (bounce)

    def __init__(self, on_toggle, on_history=None):
        self._on_toggle = on_toggle
        self._on_history = on_history
        self._hwnd = None
        self._filter = None
        self._registered = []
        self._last_trigger = {}

    def _debounced(self, hotkey_id, callback):
        def run():
            now = time.monotonic()
            if now - self._last_trigger.get(hotkey_id, 0.0) < self._MIN_INTERVAL:
                return
            self._last_trigger[hotkey_id] = now
            try:
                callback()
            except Exception:
                logging.getLogger(__name__).exception("Falha ao processar atalho")
        return run

    def start(self, widget):
        """`widget` é uma QWidget já construída — usamos o HWND nativo dela
        para registrar o atalho (precisa existir p/ receber o WM_HOTKEY)."""
        mods, vk = _parse_hotkey(config.HOTKEY)
        hwnd = int(widget.winId())
        if not user32.RegisterHotKey(hwnd, self._HOTKEY_ID, mods | MOD_NOREPEAT, vk):
            raise OSError(
                f"Não consegui registrar o atalho {config.HOTKEY!r} "
                "(outro programa já está usando essa combinação?)"
            )
        self._hwnd = hwnd
        self._registered.append(self._HOTKEY_ID)
        callbacks = {self._HOTKEY_ID: self._debounced(self._HOTKEY_ID, self._on_toggle)}
        if self._on_history and config.HISTORY_HOTKEY:
            # Atalho secundário: se outro app já usa, o ditado continua funcionando.
            try:
                mods, vk = _parse_hotkey(config.HISTORY_HOTKEY)
                if not user32.RegisterHotKey(hwnd, self._HISTORY_ID, mods | MOD_NOREPEAT, vk):
                    raise OSError("combinação em uso por outro programa")
                self._registered.append(self._HISTORY_ID)
                callbacks[self._HISTORY_ID] = self._debounced(self._HISTORY_ID, self._on_history)
            except (OSError, ValueError) as exc:
                logging.getLogger(__name__).warning(
                    "Atalho do histórico %r indisponível: %s", config.HISTORY_HOTKEY, exc)
        self._filter = _NativeFilter(callbacks)
        QCoreApplication.instance().installNativeEventFilter(self._filter)

    def stop(self):
        if self._filter is not None:
            QCoreApplication.instance().removeNativeEventFilter(self._filter)
            self._filter = None
        if self._hwnd is not None:
            for hotkey_id in self._registered:
                user32.UnregisterHotKey(self._hwnd, hotkey_id)
            self._registered = []
            self._hwnd = None
