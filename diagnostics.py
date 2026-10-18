"""Diagnóstico persistente, inclusive com pythonw e em travamentos nativos."""

import faulthandler
import logging
import json
from logging.handlers import RotatingFileHandler
from pathlib import Path
import platform
import os
import sys
import threading
import time

LOG_DIR = Path(__file__).resolve().parent / ".tmp"
_fault_file = None


def mark_run(clean=False):
    marker = LOG_DIR / "last-run.json"
    if not clean and marker.exists():
        try:
            previous = json.loads(marker.read_text(encoding="utf-8"))
            if not previous.get("clean"):
                logging.warning("Execução anterior terminou sem encerramento normal: pid=%s start=%s",
                                previous.get("pid"), previous.get("time"))
        except (ValueError, OSError):
            logging.exception("Não foi possível ler estado da execução anterior")
    marker.write_text(json.dumps({"pid": os.getpid(), "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                  "clean": clean}), encoding="utf-8")


class _LogWriter:
    def __init__(self, level):
        self.level = level

    def write(self, text):
        if text.strip():
            logging.getLogger("console").log(self.level, text.strip())
        return len(text)

    def flush(self):
        pass


def setup_logging():
    global _fault_file
    LOG_DIR.mkdir(exist_ok=True)
    handler = RotatingFileHandler(LOG_DIR / "transcriber.log", maxBytes=2_000_000,
                                  backupCount=3, encoding="utf-8")
    handlers = [handler]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s [%(process)d:%(threadName)s] %(name)s: %(message)s",
                        force=True)
    if sys.stdout is None:
        sys.stdout = _LogWriter(logging.INFO)
    if sys.stderr is None:
        sys.stderr = _LogWriter(logging.ERROR)
    _fault_file = open(LOG_DIR / "faults.log", "a", buffering=1, encoding="utf-8")
    faulthandler.enable(file=_fault_file, all_threads=True)
    # Também cobre travamentos durante imports e criação do QApplication.
    faulthandler.dump_traceback_later(10, file=_fault_file)

    def uncaught(exc_type, exc_value, traceback):
        logging.getLogger("crash").critical("Exceção não tratada", exc_info=(exc_type, exc_value, traceback))

    sys.excepthook = uncaught
    threading.excepthook = lambda args: uncaught(args.exc_type, args.exc_value, args.exc_traceback)
    logging.info("Inicializando Python=%s Windows=%s", platform.python_version(), platform.release())


def install_qt_diagnostics(app):
    from PySide6.QtCore import QTimer, qInstallMessageHandler

    faulthandler.cancel_dump_traceback_later()

    def qt_message(kind, context, message):
        logging.getLogger("qt").warning("%s: %s", kind, message)

    qInstallMessageHandler(qt_message)
    stopped = threading.Event()
    last_tick = [time.monotonic()]
    timer = QTimer(app)
    timer.setInterval(1000)
    timer.timeout.connect(lambda: last_tick.__setitem__(0, time.monotonic()))
    timer.start()
    app.aboutToQuit.connect(stopped.set)

    def watchdog():
        dumped = False
        while not stopped.wait(2):
            delay = time.monotonic() - last_tick[0]
            if delay > 8 and not dumped:
                logging.error("Interface sem responder há %.1fs; pilhas em .tmp/faults.log", delay)
                _fault_file.write(f"\nUI sem responder: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                faulthandler.dump_traceback(file=_fault_file, all_threads=True)
                dumped = True
            elif delay <= 8:
                dumped = False

    threading.Thread(target=watchdog, name="ui-watchdog", daemon=True).start()
