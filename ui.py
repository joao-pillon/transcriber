"""Painel flutuante nativo. Animações só rodam enquanto ele está visível."""

from datetime import date, datetime, timedelta
import math
import time

from PySide6.QtCore import Qt, QTimer, Signal, QPointF, QRectF
from PySide6.QtGui import QColor, QCursor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QAbstractButton, QHBoxLayout, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

import config

MUTED = "#8a9d96"
DIM = "#6f837c"


def _alpha(color, opacity):
    result = QColor(color)
    result.setAlpha(opacity)
    return result


def _font(size, weight=QFont.Normal, mono=False, spacing=0):
    font = QFont("Cascadia Mono" if mono else "Segoe UI", size)
    font.setWeight(weight)
    if spacing:
        font.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return font


def _key_label(spec):
    """"<ctrl>+<f9>" -> "Ctrl+F9"."""
    keys = [k.strip().strip("<>") for k in spec.split("+")]
    return "+".join(k.upper() if len(k) == 1 or (k[:1].lower() == "f" and k[1:].isdigit()) else k.capitalize()
                    for k in keys)


def _two_lines(text, metrics, width):
    """Quebra por palavras em até duas linhas; a segunda termina em reticências."""
    words = text.split()
    first = ""
    for i, word in enumerate(words):
        candidate = f"{first} {word}" if first else word
        if metrics.horizontalAdvance(candidate) > width:
            if not first:
                return [metrics.elidedText(" ".join(words), Qt.ElideRight, width)]
            return [first, metrics.elidedText(" ".join(words[i:]), Qt.ElideRight, width)]
        first = candidate
    return [first]


def _when(timestamp):
    moment = datetime.fromtimestamp(timestamp)
    today = date.today()
    if moment.date() == today:
        day = "hoje"
    elif moment.date() == today - timedelta(days=1):
        day = "ontem"
    else:
        day = moment.strftime("%d/%m")
    return moment.strftime("%H:%M"), day


class IconButton(QAbstractButton):
    """Controle sem foco: o cursor de texto continua na janela do usuário."""

    def __init__(self, kind, size=28, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(size, size)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.color = QColor(config.COLOR_TEXT)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hover = self.underMouse()
        if hover or self.isDown():
            p.setPen(QPen(_alpha(self.color, 40), 1))
            p.setBrush(_alpha(self.color, 34 if self.isDown() else 16))
            p.drawRoundedRect(QRectF(0.5, 0.5, self.width()-1, self.height()-1), 8, 8)
        p.translate((self.width()-16) / 2, (self.height()-16) / 2)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(_alpha(self.color, 255 if hover else 150), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        path = QPainterPath()
        if self.kind == "copy":
            p.drawRoundedRect(QRectF(2.5, 5.5, 8, 8.5), 2, 2)
            path.moveTo(5.5, 3.5)
            path.quadTo(5.5, 2.5, 6.5, 2.5)
            path.lineTo(12.5, 2.5)
            path.quadTo(13.5, 2.5, 13.5, 3.5)
            path.lineTo(13.5, 10)
            path.quadTo(13.5, 11, 12.5, 11)
        elif self.kind == "insert":
            path.moveTo(13, 2.5)
            path.lineTo(13, 8)
            path.quadTo(13, 10, 11, 10)
            path.lineTo(3.5, 10)
            path.moveTo(6.5, 7)
            path.lineTo(3.5, 10)
            path.lineTo(6.5, 13)
        elif self.isChecked():  # chevron para cima: recolhe
            path.moveTo(4.5, 9.5)
            path.lineTo(8, 6)
            path.lineTo(11.5, 9.5)
        else:
            path.moveTo(4.5, 6.5)
            path.lineTo(8, 10)
            path.lineTo(11.5, 6.5)
        p.drawPath(path)


class Waveform(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(54, 54)
        self._state = "connecting"
        self._color = QColor(config.COLOR_RECORDING)
        self._level = 0.0
        self._phase = 0.0
        self._heights = [0.08] * 9

    def animate(self, phase, level):
        self._phase = phase
        self._level += (level - self._level) * 0.28
        for i in range(9):
            envelope = math.sin((i+1) / 10 * math.pi)
            motion = 0.5 + 0.5 * math.sin(phase * 7 + i * 0.85)
            target = 0.1 + envelope * (0.1 + self._level * 0.8) * motion
            self._heights[i] += (target - self._heights[i]) * 0.3
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(_alpha(self._color, 13))
        p.setPen(QPen(_alpha(self._color, 36), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, 53, 53), 16, 16)
        p.setPen(QPen(self._color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        if self._state in ("connecting", "working"):
            p.setPen(QPen(_alpha(self._color, 35), 2))
            p.drawEllipse(QRectF(17, 17, 20, 20))
            p.setPen(QPen(self._color, 2, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(17, 17, 20, 20), int(-self._phase * 210 * 16), 100*16)
        elif self._state == "done":
            path = QPainterPath(QPointF(18, 27))
            path.lineTo(24, 33)
            path.lineTo(36, 21)
            p.drawPath(path)
        elif self._state == "error":
            p.drawEllipse(QRectF(17, 17, 20, 20))
            p.drawLine(QPointF(27, 22), QPointF(27, 28))
            p.drawPoint(QPointF(27, 32))
        else:
            p.setPen(Qt.NoPen)
            for i, height in enumerate(self._heights):
                h = max(3, height * 32)
                x = 10 + i * 4
                p.setBrush(_alpha(self._color, 36))
                p.drawRoundedRect(QRectF(x-1, 26-h/2, 4, h+2), 2, 2)
                p.setBrush(self._color)
                p.drawRoundedRect(QRectF(x, 27-h/2, 2, h), 1, 1)


class HistoryRow(QWidget):
    HEIGHT = 58

    def __init__(self, entry, on_copy, on_insert, last=False):
        super().__init__()
        self.entry = entry
        self._last = last
        self._copied_until = 0.0
        self.setFixedHeight(self.HEIGHT)
        self.setToolTip(entry["text"])
        self.copy_button = IconButton("copy", parent=self)
        self.copy_button.setToolTip("Copiar")
        self.copy_button.clicked.connect(lambda: on_copy(self))
        self.insert_button = IconButton("insert", parent=self)
        self.insert_button.setToolTip("Inserir na janela ativa")
        self.insert_button.clicked.connect(lambda: on_insert(self))

    def flash_copied(self):
        self._copied_until = time.monotonic() + 1.2
        self.update()
        QTimer.singleShot(1250, self.update)

    def resizeEvent(self, event):
        y = (self.HEIGHT - 28) // 2
        self.insert_button.move(self.width() - 14 - 28, y)
        self.copy_button.move(self.width() - 14 - 28 - 4 - 28, y)
        super().resizeEvent(event)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        if self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(200, 235, 222, 9))
            p.drawRoundedRect(QRectF(8, 3, w-16, self.HEIGHT-6), 11, 11)
        if not self._last:
            p.setPen(QPen(QColor(170, 210, 196, 16), 1))
            p.drawLine(QPointF(20, self.HEIGHT-0.5), QPointF(w-20, self.HEIGHT-0.5))
        clock, day = _when(self.entry["created"])
        day_color = DIM
        if time.monotonic() < self._copied_until:
            day, day_color = "copiado", config.COLOR_DONE
        elif self.entry["status"] == "live":
            day, day_color = "gravando", config.COLOR_RECORDING
        elif self.entry["status"] == "error":
            day, day_color = "incompleta", config.COLOR_ERROR
        p.setFont(_font(8, mono=True))
        p.setPen(QColor("#a9bbb5"))
        p.drawText(QRectF(20, 12, 54, 16), Qt.AlignLeft | Qt.AlignVCenter, clock)
        p.setFont(_font(7))
        p.setPen(QColor(day_color))
        p.drawText(QRectF(20, 30, 54, 14), Qt.AlignLeft | Qt.AlignVCenter, day)
        left, right = 82, w - 14 - 28*2 - 4 - 12
        p.setFont(_font(9))
        p.setPen(QColor(config.COLOR_TEXT))
        lines = _two_lines(self.entry["text"], p.fontMetrics(), right - left)
        line_h = 18
        top = (self.HEIGHT - line_h * len(lines)) / 2
        for i, line in enumerate(lines):
            p.drawText(QRectF(left, top + i*line_h, right - left, line_h), Qt.AlignLeft | Qt.AlignVCenter, line)


class HistoryDrawer(QWidget):
    HEADER = 40
    BOTTOM = 8
    EMPTY = 64
    copy_requested = Signal(str)
    insert_requested = Signal(str)

    def __init__(self, width, parent=None):
        super().__init__(parent)
        self.setFixedWidth(width)
        self._count = 0
        self.rows = []
        self._scroll = QScrollArea(self)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFocusPolicy(Qt.NoFocus)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; margin: 6px 3px 6px 0; }"
            "QScrollBar::handle:vertical { background: rgba(200, 235, 222, 38); border-radius: 1px; min-height: 28px; }"
            "QScrollBar::handle:vertical:hover { background: rgba(200, 235, 222, 70); }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }")
        self._list = QWidget()
        self._list.setObjectName("historyList")
        self._list.setStyleSheet("#historyList { background: transparent; }")
        self._layout = QVBoxLayout(self._list)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._scroll.setWidget(self._list)
        self.load([])

    def load(self, entries):
        for row in self.rows:
            row.deleteLater()
        while self._layout.count():
            self._layout.takeAt(0)
        self.rows = [HistoryRow(e, self._copy, self._insert, last=i == len(entries)-1)
                     for i, e in enumerate(entries)]
        for row in self.rows:
            self._layout.addWidget(row)
        self._layout.addStretch(1)
        self._count = len(entries)
        visible = min(len(entries), config.UI_HISTORY_ROWS)
        body = visible * HistoryRow.HEIGHT if entries else self.EMPTY
        self.setFixedHeight(self.HEADER + body + self.BOTTOM)
        self._scroll.setGeometry(0, self.HEADER, self.width(), body)
        self._scroll.setVisible(bool(entries))
        self._scroll.verticalScrollBar().setValue(0)
        self.update()

    def _copy(self, row):
        self.copy_requested.emit(row.entry["text"])
        row.flash_copied()

    def _insert(self, row):
        self.insert_requested.emit(row.entry["text"])

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(_font(7, QFont.DemiBold, spacing=1.6))
        p.setPen(QColor("#9baea9"))
        p.drawText(QRectF(24, 0, 200, self.HEADER), Qt.AlignLeft | Qt.AlignVCenter, "HISTÓRICO")
        p.setFont(_font(7, mono=True))
        p.setPen(QColor(DIM))
        count = "1 salva" if self._count == 1 else f"{self._count} salvas"
        p.drawText(QRectF(0, 0, self.width()-24, self.HEADER), Qt.AlignRight | Qt.AlignVCenter, count)
        p.setPen(QPen(QColor(170, 210, 196, 18), 1))
        p.drawLine(QPointF(20, self.HEADER-0.5), QPointF(self.width()-20, self.HEADER-0.5))
        if not self._count:
            p.setFont(_font(9))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(0, self.HEADER, self.width(), self.EMPTY), Qt.AlignCenter,
                       f"Nada salvo ainda. Aperte {_key_label(config.HOTKEY)} e fale.")


class Popup(QWidget):
    show_recording = Signal()
    show_connecting = Signal()
    show_working = Signal()
    show_done = Signal(str)
    show_error = Signal(str)
    update_text = Signal(str)
    update_level = Signal(float)
    history_changed = Signal()
    toggle_history = Signal()
    insert_requested = Signal(str)

    _GAP = 10

    def __init__(self, history=None):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)
        self.setWindowTitle("Transcriber")
        self._history = history
        self._pad = 20
        self._W = config.UI_WIDTH
        self._H = config.UI_HEIGHT
        self._expanded = False
        self._state = "idle"
        self._accent = QColor(config.COLOR_RECORDING)
        self._target_accent = QColor(self._accent)
        self._hover = 0.0
        self._hovered = False
        self._level = 0.0
        self._level_at = 0.0
        self._started = time.monotonic()
        self._phase = 0.0
        self._drag_origin = None
        self._manual_position = None
        self._full_text = ""
        self._live_text = False
        self._build()
        self._apply_size()
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._auto_hide)
        self._animation = QTimer(self)
        self._animation.setInterval(33)
        self._animation.timeout.connect(self._tick)
        self.show_recording.connect(self._on_recording)
        self.show_connecting.connect(self._on_connecting)
        self.show_working.connect(self._on_working)
        self.show_done.connect(self._on_done)
        self.show_error.connect(self._on_error)
        self.update_text.connect(self._on_text)
        self.update_level.connect(self._on_level)
        self.history_changed.connect(self._on_history_changed)
        self.toggle_history.connect(self._on_toggle_history)

    def _build(self):
        self._card = QWidget(self)
        self._card.setGeometry(self._pad, self._pad, self._W, self._H)
        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(24, 14, 18, 22)
        layout.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self._brand = self._make_label("TRANSCRIBER", 7, "#9baea9", QFont.DemiBold, spacing=1.6)
        self._brand.setToolTip("Arraste por esta faixa para mover")
        self._brand.setAttribute(Qt.WA_TransparentForMouseEvents)
        header.addWidget(self._brand)
        header.addStretch()
        self._status = self._make_label("CONECTANDO", 7, config.COLOR_RECORDING, QFont.DemiBold, spacing=0.8)
        header.addWidget(self._status)
        self._elapsed = self._make_label("00:00", 8, "#83958f", mono=True)
        self._elapsed.setFixedWidth(40)
        self._elapsed.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self._elapsed)
        self._history_button = IconButton("chevron", size=24, parent=self._card)
        self._history_button.setCheckable(True)
        self._history_button.color = QColor("#a9bbb5")
        tip = "Histórico"
        if config.HISTORY_HOTKEY:
            tip += f" · {_key_label(config.HISTORY_HOTKEY)}"
        self._history_button.setToolTip(tip)
        self._history_button.setAccessibleName("Histórico de transcrições")
        self._history_button.clicked.connect(self._on_toggle_history)
        header.addWidget(self._history_button)
        layout.addLayout(header)
        layout.addSpacing(12)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 6, 0)
        body.setSpacing(15)
        self._wave = Waveform()
        body.addWidget(self._wave)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        copy.addStretch(1)
        self._label = self._make_label("Pode falar.", 13, config.COLOR_TEXT, QFont.DemiBold)
        self._label.setMinimumWidth(0)
        self._label.setFixedHeight(25)
        copy.addWidget(self._label)
        self._subtitle = self._make_label("Sua voz, em texto. Em qualquer janela.", 8, MUTED)
        self._subtitle.setMinimumWidth(0)
        self._subtitle.setFixedHeight(20)
        copy.addWidget(self._subtitle)
        copy.addStretch(1)
        body.addLayout(copy, 1)
        layout.addLayout(body)
        layout.addStretch(1)
        self._drawer = HistoryDrawer(self._W, self)
        self._drawer.move(self._pad, self._pad + self._H + self._GAP)
        self._drawer.hide()
        self._drawer.copy_requested.connect(self._copy)
        self._drawer.insert_requested.connect(self._insert)

    def _make_label(self, text, size, color, weight=QFont.Normal, mono=False, spacing=0):
        label = QLabel(text)
        label.setFont(_font(size, weight, mono, spacing))
        label.setTextFormat(Qt.PlainText)
        label.setStyleSheet(f"color: {color}; background: transparent;")
        return label

    def _tick(self):
        self._phase += 0.033
        self._hover += ((1 if self._hovered else 0) - self._hover) * 0.18
        c, target = self._accent, self._target_accent
        self._accent = QColor(*[int(a + (b-a)*0.18) for a, b in
                               zip((c.red(), c.green(), c.blue()), (target.red(), target.green(), target.blue()))])
        self._wave._color = QColor(self._accent)
        level = self._level if time.monotonic() - self._level_at < 0.3 else 0
        self._wave.animate(self._phase, level)
        if self._state in ("connecting", "recording"):
            seconds = int(time.monotonic() - self._started)
            self._elapsed.setText(f"{seconds//60:02d}:{seconds%60:02d}")
        self.update()

    def _paint_panel(self, p, rect, radius):
        bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
        bg.setColorAt(0, QColor("#16201e"))
        bg.setColorAt(0.55, QColor(config.COLOR_BG))
        bg.setColorAt(1, QColor("#0c1213"))
        p.setBrush(bg)
        p.setPen(QPen(QColor(211, 245, 231, int(29+self._hover*18)), 1))
        p.drawRoundedRect(rect, radius, radius)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        card = QRectF(self._pad, self._pad, self._W, self._H)
        drawer = QRectF(self._drawer.geometry()) if self._expanded else None
        shadow = card.united(drawer) if drawer is not None else card
        p.setPen(Qt.NoPen)
        for spread in (14, 10, 6, 3):
            p.setBrush(QColor(0, 0, 0, 16))
            p.drawRoundedRect(shadow.adjusted(-spread, -spread+5, spread, spread+5), 22+spread, 22+spread)
        if drawer is not None:
            self._paint_panel(p, drawer, 18)
        self._paint_panel(p, card, 22)
        # Luz contida no cartão, sem desfoque que exija composição extra.
        clip = QPainterPath()
        clip.addRoundedRect(card.adjusted(1, 1, -1, -1), 21, 21)
        p.setClipPath(clip)
        sheen = QLinearGradient(card.topLeft(), QPointF(card.right(), card.top()+50))
        sheen.setColorAt(0, _alpha(self._accent, 10))
        sheen.setColorAt(0.6, _alpha(self._accent, 0))
        p.fillRect(card, sheen)
        p.setPen(QPen(QColor(172, 215, 198, 9), 1))
        for x in range(int(card.right())-130, int(card.right()), 16):
            p.drawLine(QPointF(x, card.top()), QPointF(x, card.top()+68))
        for y in range(int(card.top())+12, int(card.top())+69, 16):
            p.drawLine(QPointF(card.right()-130, y), QPointF(card.right(), y))
        top = QLinearGradient(card.topLeft(), card.topRight())
        top.setColorAt(0, _alpha(self._accent, 0))
        top.setColorAt(0.32, _alpha(self._accent, 140))
        top.setColorAt(0.8, _alpha(self._accent, 0))
        p.setPen(QPen(top, 1))
        p.drawLine(QPointF(card.left()+22, card.top()+0.5), QPointF(card.right()-22, card.top()+0.5))
        if self._state in ("connecting", "working"):
            # Segmento móvel na base indica espera sem inventar uma porcentagem.
            x = card.left()+40 + (self._W-116) * (0.5 + 0.5*math.sin(self._phase*1.9))
            p.setPen(QPen(_alpha(self._accent, 120), 1.4, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(x, card.bottom()-1), QPointF(x+36, card.bottom()-1))
        p.end()

    def _set_text(self, text, live=False):
        self._full_text = text
        self._live_text = live
        self._label.setToolTip(text)
        width = max(50, self._label.width())
        # Ao vivo mostra o fim da fala; avisos e títulos mostram o começo.
        mode = Qt.ElideLeft if live else Qt.ElideRight
        self._label.setText(self._label.fontMetrics().elidedText(text, mode, width))

    def _transition(self, state, color, status, title, subtitle):
        self._state = state
        self._target_accent = QColor(color)
        self._wave._state = state
        self._status.setText(status)
        self._status.setStyleSheet(f"color: {color}; background: transparent;")
        self._set_text(title)
        self._subtitle.setText(subtitle)
        self._hide_timer.stop()
        self._reposition()
        self.show()
        # Refaz a elipse após calcular o layout real na primeira abertura.
        self._card.layout().activate()
        self._set_text(title)

    def _on_connecting(self):
        self._started = time.monotonic()
        self._elapsed.setText("00:00")
        self._level = 0
        self._transition("connecting", config.COLOR_CONNECTING, "PREPARANDO", "Preparando seu ditado…",
                         "O microfone está se conectando.")

    def _on_recording(self):
        if self._state != "connecting":
            self._started = time.monotonic()
        self._transition("recording", config.COLOR_RECORDING, "● AO VIVO", "Pode falar.",
                         "Sua voz, em texto. Em qualquer janela.")

    def _on_idle(self):
        self._elapsed.setText("")
        self._transition("idle", config.COLOR_ACCENT, "PRONTO", "Suas transcrições",
                         f"{_key_label(config.HOTKEY)} para ditar. Copie ou insira qualquer uma.")

    def _on_text(self, text):
        if not text or self._state not in ("connecting", "recording", "working"):
            return
        self._set_text(text, live=True)
        if self._state != "working":
            self._subtitle.setText("Transcrevendo enquanto você fala.")

    def _on_level(self, level):
        self._level = max(0, min(1, level)) if math.isfinite(level) else 0
        self._level_at = time.monotonic()

    def _on_working(self):
        self._transition("working", config.COLOR_WORKING, "PROCESSANDO", "Concluindo seu texto…",
                         "Só um instante. Cuidando das últimas palavras.")

    def _on_done(self, text):
        self._transition("done", config.COLOR_DONE, "CONCLUÍDO", text.strip() or "Tudo pronto.",
                         "Texto entregue. Continue de onde parou.")
        self._hide_after(config.UI_FADE_OUT_MS if text.strip() else 0)

    def _on_error(self, message):
        self._transition("error", config.COLOR_ERROR, "ATENÇÃO", message,
                         f"Aperte {_key_label(config.HOTKEY)} para tentar de novo.")
        self._hide_after(6500)

    def _hide_after(self, delay_ms):
        if delay_ms <= 0:
            self._auto_hide()
        else:
            self._hide_timer.start(delay_ms)

    def _auto_hide(self):
        # Com o histórico aberto o painel só fecha pelo usuário.
        if not self._expanded:
            self.hide()

    # ─── Histórico ────────────────────────────────────────────────────────
    def _apply_size(self):
        height = self._H + 2*self._pad
        if self._expanded:
            height += self._GAP + self._drawer.height()
        self.setFixedSize(self._W + 2*self._pad, height)

    def _set_expanded(self, expanded):
        self._expanded = expanded
        if expanded:
            self._reload_history()
        self._drawer.setVisible(expanded)
        self._history_button.setChecked(expanded)
        self._apply_size()
        if self.isVisible():
            self._reposition()
        self.update()

    def _reload_history(self):
        self._drawer.load(self._history.recent(50) if self._history is not None else [])

    def _on_history_changed(self):
        if self._expanded:
            self._reload_history()
            self._apply_size()
            self._reposition()

    def _on_toggle_history(self):
        if not self.isVisible():
            self._set_expanded(True)
            self._on_idle()
        elif self._expanded:
            self._set_expanded(False)
            if self._state in ("idle", "done", "error"):
                self.hide()
        else:
            self._set_expanded(True)

    def _copy(self, text):
        QApplication.clipboard().setText(text)

    def _insert(self, text):
        # O painel nunca recebe foco: a colagem cai na janela onde o usuário estava.
        self.insert_requested.emit(text)
        if self._state in ("idle", "done", "error"):
            self.hide()

    # ─── Janela ───────────────────────────────────────────────────────────
    def _reposition(self):
        if self._manual_position is not None and QApplication.screenAt(self._manual_position) is not None:
            area = QApplication.screenAt(self._manual_position).availableGeometry()
            position = self._manual_position
            # Abrir o histórico perto da base sobe o painel só o necessário.
            self.move(position.x(), min(position.y(), area.bottom()-self.height()+self._pad))
            return
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        # A base do painel fica sempre na mesma altura; o histórico empurra o cartão para cima.
        self.move(area.x()+(area.width()-self.width())//2,
                  area.bottom()-self.height()-config.UI_MARGIN_BOTTOM+self._pad)

    def showEvent(self, event):
        self._animation.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._animation.stop()
        self._hovered = False
        self._hover = 0
        if self._expanded:
            self._expanded = False
            self._drawer.hide()
            self._history_button.setChecked(False)
            self._apply_size()
        super().hideEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        super().leaveEvent(event)

    def _in_drag_zone(self, y):
        return self._pad <= y < self._pad+45

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._in_drag_zone(event.position().y()):
            self._drag_origin = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None:
            position = event.globalPosition().toPoint() - self._drag_origin
            screen = QApplication.screenAt(event.globalPosition().toPoint()) or QApplication.primaryScreen()
            area = screen.availableGeometry()
            position.setX(max(area.left()-self._pad, min(position.x(), area.right()-self.width()+self._pad)))
            position.setY(max(area.top()-self._pad, min(position.y(), area.bottom()-self.height()+self._pad)))
            self.move(position)
            self._manual_position = position
        else:
            self.setCursor(Qt.OpenHandCursor if self._in_drag_zone(event.position().y()) else Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_origin = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)
