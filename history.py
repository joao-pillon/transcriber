"""Histórico local: cada ciclo de F9 vira uma transcrição salva (só texto, sem áudio)."""

import logging
from pathlib import Path
import sqlite3
import threading
import time

import config

log = logging.getLogger(__name__)


class History:
    """Seguro entre threads: os trechos chegam pela thread do ditado, a lista é lida pela UI."""

    def __init__(self, path=None, limit=None):
        self._path = Path(path or config.HISTORY_PATH)
        self._limit = limit or config.HISTORY_LIMIT
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self._path, check_same_thread=False, timeout=2)
        with self._lock, self._db:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("""CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created REAL NOT NULL,
                updated REAL NOT NULL,
                text TEXT NOT NULL,
                status TEXT NOT NULL)""")
            # Ditado em andamento quando o app caiu: o texto salvo continua acessível.
            self._db.execute("UPDATE transcriptions SET status='error' WHERE status='live'")

    def save(self, text, entry_id=None, status="done"):
        """Cria (entry_id=None) ou atualiza a transcrição. Falha de disco nunca derruba o ditado."""
        text = text.strip()
        if not text:
            return entry_id
        now = time.time()
        try:
            with self._lock, self._db:
                if entry_id is None:
                    entry_id = self._db.execute(
                        "INSERT INTO transcriptions(created, updated, text, status) VALUES (?, ?, ?, ?)",
                        (now, now, text, status)).lastrowid
                    self._db.execute("DELETE FROM transcriptions WHERE id <= ?", (entry_id - self._limit,))
                else:
                    self._db.execute("UPDATE transcriptions SET updated=?, text=?, status=? WHERE id=?",
                                     (now, text, status, entry_id))
        except sqlite3.Error:
            log.exception("Falha ao salvar histórico")
        return entry_id

    def finish(self, entry_id, ok=True):
        if entry_id is None:
            return
        try:
            with self._lock, self._db:
                self._db.execute("UPDATE transcriptions SET status=? WHERE id=?",
                                 ("done" if ok else "error", entry_id))
        except sqlite3.Error:
            log.exception("Falha ao finalizar histórico")

    def recent(self, limit=50):
        try:
            with self._lock:
                rows = self._db.execute(
                    "SELECT id, created, text, status FROM transcriptions ORDER BY id DESC LIMIT ?",
                    (limit,)).fetchall()
        except sqlite3.Error:
            log.exception("Falha ao ler histórico")
            return []
        return [{"id": r[0], "created": r[1], "text": r[2], "status": r[3]} for r in rows]

    def close(self):
        with self._lock:
            self._db.close()
