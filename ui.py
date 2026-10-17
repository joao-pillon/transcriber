"""Pílula flutuante glass — UI dark cyberpunk com waveform ao vivo.

A UI vive na thread principal. Outras threads falam com ela por sinais Qt
(thread-safe). Visual: glassmorphism dark neutro, cantos bem arredondados,
sombra suave, barras de áudio animadas e texto que cresce durante o streaming.
"""

import math

from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QVariantAnimation, QEasingCurve,
    QAbstractAnimation, QPointF,
)
from PySide6.QtGui import (
    QColor, QPainter, QBrush, QFont, QPen, QLinearGradient, QPainterPath,
)
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QApplication

import config


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
    )


class Waveform(QWidget):
    """Conjunto de barrinhas que pulsam com o nível do áudio — ou um ícone
    de aviso quando dá erro."""

    def __init__(self, n_bars=5):
        super().__init__()
        self.setFixedSize(40, 32)
        self._n = n_bars
        self._level = 0.0          # alvo (0..1)
        self._heights = [0.15] * n_bars
        self._phase = 0
        self._color = QColor(config.COLOR_RECORDING)
        self._active = False
        self._symbol: str | None = None   # None | "warning"

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(45)

    def set_level(self, lvl: float):
        self._level = max(0.0, min(1.0, lvl))

    def set_active(self, on: bool):
        self._active = on

    def set_color(self, color):
        self._color = color if isinstance(color, QColor) else QColor(color)
        self.update()

    def set_symbol(self, name: str | None):
        self._symbol = name
        self.update()

    def _tick(self):
        self._phase += 1
        for i in range(self._n):
            if self._active:
                # onda suave modulada pelo nível atual
                base = 0.3 + 0.7 * self._level
                wob = 0.5 + 0.5 * math.sin((self._phase / 3.0) + i * 0.9)
                target = 0.12 + base * wob
            else:
                target = 0.15
            # suaviza
            self._heights[i] += (target - self._heights[i]) * 0.35
        if self._active:
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._symbol:
            self._paint_symbol(p)
        else:
            self._paint_bars(p)

    def _paint_bars(self, p: QPainter):
        w, h = self.width(), self.height()
        bar_w = 4
        gap = (w - self._n * bar_w) / (self._n - 1)
        glow = QColor(self._color)
        glow.setAlpha(70)
        for i, hf in enumerate(self._heights):
            bh = max(4, hf * h)
            x = i * (bar_w + gap)
            y = (h - bh) / 2
            # halo suave atrás da barra (dá o efeito "glow")
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(glow))
            p.drawRoundedRect(int(x) - 1, int(y) - 2, bar_w + 2, int(bh) + 4, 3, 3)
            p.setBrush(QBrush(self._color))
            p.drawRoundedRect(int(x), int(y), bar_w, int(bh), 2, 2)

    def _paint_symbol(self, p: QPainter):
        cx, cy = self.width() / 2, self.height() / 2

        glow = QColor(self._color)
        glow.setAlpha(55)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(cx, cy), 15, 15)

        pen = QPen(self._color)
        pen.setWidthF(3.2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        if self._symbol == "warning":
            tri = QPainterPath()
            tri.moveTo(cx, cy - 10)
            tri.lineTo(cx - 10, cy + 8)
            tri.lineTo(cx + 10, cy + 8)
            tri.closeSubpath()
            p.drawPath(tri)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(self._color))
            p.drawRoundedRect(int(cx - 1.4), int(cy - 4), 3, 6, 1.5, 1.5)
            p.drawEllipse(QPointF(cx, cy + 5), 1.6, 1.6)


class Popup(QWidget):
    # Sinais (chamados de outras threads).
    show_recording = Signal()
    show_working = Signal()
    show_done = Signal(str)
    show_error = Signal(str)
    update_text = Signal(str)     # texto parcial ao vivo (streaming)
    update_level = Signal(float)  # nível do mic p/ waveform

    def __init__(self):
        super().__init__()
        self._build()
        self.show_recording.connect(self._on_recording)
        self.show_working.connect(self._on_working)
        self.show_done.connect(self._on_done)
        self.show_error.connect(self._on_error)
        self.update_text.connect(self._on_text)
        self.update_level.connect(self._on_level)

    # ─── Construção ──────────────────────────────────────────────────────
    def _build(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # margem extra ao redor p/ a sombra desenhada não ser cortada
        self._pad = 22
        self._radius = 22
        self._glass = QColor(9, 12, 12, 218)    # dark neutro translúcido (sem tom roxo)
        self._border = QColor(255, 255, 255, 26)
        self._accent = QColor(config.COLOR_RECORDING)

        # Tamanho FIXO da janela: evita redimensionar a janela layered a cada
        # frame (o que causava 'UpdateLayeredWindowIndirect failed' no Windows).
        self._W = 440
        self._H = 88
        self.setFixedSize(self._W + 2 * self._pad, self._H + 2 * self._pad)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(self._pad + 22, self._pad,
                               self._pad + 24, self._pad)
        lay.setSpacing(16)

        self._wave = Waveform()
        lay.addWidget(self._wave)

        self._label = QLabel("Gravando…")
        f = QFont("Segoe UI", 13)
        f.setWeight(QFont.DemiBold)
        f.setLetterSpacing(QFont.PercentageSpacing, 101.5)
        self._label.setFont(f)
        self._label.setStyleSheet(f"color: {config.COLOR_TEXT}; background: transparent;")
        self._label.setWordWrap(False)
        lay.addWidget(self._label, 1)

        # Uma animação de opacidade e um timer de sumir REUSADOS: assim um fade-in
        # novo cancela o fade-out pendente da gravação anterior (senão o popup
        # sumia no meio de uma gravação iniciada logo após outra).
        self._fading_out = False
        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._opacity_anim.finished.connect(self._on_fade_finished)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_fade_out)
        self._accent_anim: QVariantAnimation | None = None
        self._level = 0.0

        # oscilação contínua ciano↔teal enquanto "ativo" (ouvindo/finalizando) —
        # dá a sensação de gradiente vivo em vez de cor parada.
        self._osc_a = QColor("#00eaff")
        self._osc_b = QColor("#00c2a8")
        self._osc_phase = 0.0
        self._oscillating = False
        self._osc_timer = QTimer(self)
        self._osc_timer.timeout.connect(self._tick_oscillation)
        self._osc_timer.start(45)

    # fundo glass desenhado à mão: glow colorido + sombra + cartão + borda + accent.
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(self._pad, self._pad, -self._pad, -self._pad)

        # glow colorido (acompanha o estado atual) por baixo da sombra escura —
        # respira com o nível do mic enquanto a onda está ativa.
        boost = 1.0
        if self._wave._active:
            boost = 0.7 + 0.9 * self._level
        glow = QColor(self._accent)
        for i in range(4):
            spread = (4 - i) * 3
            glow.setAlpha(min(255, int((5 + i * 4) * boost)))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            gh = rect.adjusted(-spread, -spread + 4, spread, spread + 4)
            p.drawRoundedRect(gh, self._radius + spread, self._radius + spread)

        # sombra suave (várias camadas translúcidas em vez de QGraphicsEffect)
        for i in range(6):
            spread = (6 - i) * 2
            alpha = 12 + i * 6
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, alpha))
            sh = rect.adjusted(-spread, -spread + 4, spread, spread + 4)
            p.drawRoundedRect(sh, self._radius + spread, self._radius + spread)

        # cartão glass — leve gradiente vertical em vez de cor chapada
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        top = QColor(self._glass)
        top.setAlpha(min(255, top.alpha() + 15))
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, self._glass)
        p.setBrush(QBrush(grad))
        pen = QPen(self._border)
        pen.setWidth(1)
        p.setPen(pen)
        p.drawRoundedRect(rect, self._radius, self._radius)

        # sheen: reflexo sutil no topo, típico de glassmorphism
        sheen = QLinearGradient(rect.topLeft(), rect.topLeft() + type(rect.topLeft())(0, int(rect.height() * 0.45)))
        sheen.setColorAt(0.0, QColor(255, 255, 255, 22))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(sheen))
        p.drawRoundedRect(rect, self._radius, self._radius)

        # linha de destaque (accent) à esquerda, com halo
        accent_glow = QColor(self._accent)
        accent_glow.setAlpha(90)
        p.setBrush(QBrush(accent_glow))
        p.drawRoundedRect(rect.left() - 1, rect.center().y() - 15, 8, 30, 3, 3)
        p.setBrush(QBrush(self._accent))
        p.drawRoundedRect(rect.left() + 2, rect.center().y() - 12, 5, 24, 2.5, 2.5)

    def _reposition(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - config.UI_MARGIN_BOTTOM + self._pad
        self.move(x, y)

    def _enter_active(self):
        """Liga a oscilação contínua ciano↔teal (estado "vivo": ouvindo/finalizando)."""
        # crossfade p/ verde/vermelho ainda rodando brigaria com a oscilação
        self._stop_accent_anim()
        self._oscillating = True

    def _stop_accent_anim(self):
        if self._accent_anim is None:
            return
        try:
            self._accent_anim.stop()
        except RuntimeError:
            pass  # já terminou e foi deletada (DeleteWhenStopped)
        self._accent_anim = None

    def _tick_oscillation(self):
        if not self._oscillating:
            return
        self._osc_phase += 0.045
        t = (math.sin(self._osc_phase) + 1) / 2
        c = _lerp_color(self._osc_a, self._osc_b, t)
        self._accent = c
        self._wave.set_color(c)
        self.update()

    def _set_static_accent(self, color: str):
        """Para a oscilação e faz um crossfade suave até uma cor fixa
        (usado nos estados terminais: pronto / erro)."""
        self._oscillating = False
        self._stop_accent_anim()
        target = QColor(color)
        if target == self._accent:
            self._wave.set_color(target)
            return
        anim = QVariantAnimation(self)
        anim.setDuration(260)
        anim.setStartValue(self._accent)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def apply(c):
            self._accent = c
            self._wave.set_color(c)
            self.update()

        anim.valueChanged.connect(apply)
        anim.start(QAbstractAnimation.DeleteWhenStopped)
        self._accent_anim = anim

    def _on_level(self, lvl: float):
        self._level = max(0.0, min(1.0, lvl))
        self._wave.set_level(lvl)
        self.update()

    def _set_text(self, txt: str):
        # janela é fixa: mostramos o FINAL do texto (o mais recente no streaming),
        # elidindo pelo tamanho real da fonte em vez de um nº fixo de caracteres.
        avail = self._label.width() or (self._W - 40 - 16 - 6)
        elided = self._label.fontMetrics().elidedText(txt, Qt.ElideLeft, avail)
        self._label.setText(elided)

    # ─── Animações de entrada/saída ──────────────────────────────────────
    def _fade_in(self):
        self._hide_timer.stop()
        self._opacity_anim.stop()
        self._fading_out = False
        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()
        self._animate_opacity(1.0, 160, QEasingCurve.OutCubic)

    def _fade_out(self, delay_ms: int):
        self._hide_timer.start(delay_ms)

    def _start_fade_out(self):
        self._fading_out = True
        self._animate_opacity(0.0, 220, QEasingCurve.InCubic)

    def _animate_opacity(self, end: float, ms: int, curve):
        anim = self._opacity_anim
        anim.stop()
        anim.setDuration(ms)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(end)
        anim.setEasingCurve(curve)
        anim.start()

    def _on_fade_finished(self):
        if self._fading_out:
            self._fading_out = False
            self.hide()

    # ─── Reações ─────────────────────────────────────────────────────────
    def _on_recording(self):
        self._wave.set_symbol(None)
        self._enter_active()
        self._wave.set_active(True)
        self._set_text("Ouvindo…")
        self._reposition()
        self._fade_in()

    def _on_text(self, txt: str):
        if not txt:
            return
        self._wave.set_symbol(None)
        self._enter_active()
        self._wave.set_active(True)
        self._set_text(txt)

    def _on_working(self):
        self._wave.set_symbol(None)
        self._enter_active()
        self._wave.set_active(True)

    def _on_done(self, text: str):
        self._set_static_accent(config.COLOR_DONE)
        self._wave.set_active(False)
        preview = text.strip() or "(sem fala)"
        self._set_text(preview)
        self._fade_out(config.UI_FADE_OUT_MS)

    def _on_error(self, msg: str):
        self._set_static_accent(config.COLOR_ERROR)
        self._wave.set_active(False)
        self._wave.set_symbol("warning")
        self._set_text(msg)
        self._reposition()
        self._fade_in()
        self._fade_out(2800)
