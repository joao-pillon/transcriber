import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from history import History
from ui import Popup

qt = QApplication.instance() or QApplication([])


class PopupInteractionTests(unittest.TestCase):
    def setUp(self):
        self.popup = Popup()
        self.addCleanup(self.popup.close)

    def test_late_transcript_does_not_reset_processing_or_error_state(self):
        self.popup.show_working.emit()
        self.popup.update_text.emit("Últimas palavras")
        self.assertEqual(self.popup._state, "working")
        self.popup.show_error.emit("Conexão interrompida")
        self.popup.update_text.emit("Resposta atrasada")
        self.assertEqual(self.popup._label.text(), "Conexão interrompida")

    def test_hidden_popup_stops_animation_and_new_session_cancels_old_timeout(self):
        self.popup.show_error.emit("offline")
        self.assertTrue(self.popup._hide_timer.isActive())
        self.popup.show_recording.emit()
        self.assertFalse(self.popup._hide_timer.isActive())
        self.assertTrue(self.popup._animation.isActive())
        self.popup.hide()
        self.assertFalse(self.popup._animation.isActive())

    def test_controls_do_not_accept_keyboard_focus(self):
        self.assertTrue(self.popup.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        self.assertEqual(self.popup._history_button.focusPolicy(), Qt.NoFocus)

    def test_error_shows_beginning_of_message(self):
        self.popup.show_error.emit("Conexão sem resposta; aperte F9 para reconectar e tentar de novo agora")
        self.assertTrue(self.popup._label.text().startswith("Conexão"))

    def test_dragged_position_survives_state_changes(self):
        self.popup.show_recording.emit()
        start = self.popup.pos()
        QTest.mousePress(self.popup, Qt.LeftButton, pos=QPoint(40, 36))
        QTest.mouseMove(self.popup, QPoint(70, 26))
        QTest.mouseRelease(self.popup, Qt.LeftButton, pos=QPoint(70, 26))
        self.assertIsNotNone(self.popup._manual_position)
        moved = self.popup.pos()
        self.assertNotEqual(start, moved)
        self.popup.show_working.emit()
        self.assertEqual(self.popup.pos(), moved)

    def test_completion_respects_instant_hide_preference(self):
        self.popup.show_recording.emit()
        with patch("config.UI_FADE_OUT_MS", 0):
            self.popup.show_done.emit("Texto pronto")
        self.assertFalse(self.popup.isVisible())



class HistoryTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.history = History(os.path.join(folder.name, "history.db"), limit=3)
        self.addCleanup(self.history.close)
        self.popup = Popup(self.history)
        self.addCleanup(self.popup.close)

    def test_entries_update_in_place_and_respect_limit(self):
        entry = self.history.save("primeiro", status="live")
        self.assertEqual(self.history.save("primeiro trecho", entry, status="live"), entry)
        self.history.finish(entry, ok=False)
        for text in ("b", "c", "d"):
            self.history.save(text)
        texts = [e["text"] for e in self.history.recent()]
        self.assertEqual(texts, ["d", "c", "b"])
        self.assertIsNone(self.history.save("   "))

    def test_live_entry_from_crash_is_marked_incomplete(self):
        path = self.history._path
        self.history.save("sem fim", status="live")
        reopened = History(path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.recent()[0]["status"], "error")

    def test_history_hotkey_opens_drawer_below_card_and_keeps_it_open(self):
        self.history.save("texto antigo")
        self.popup.toggle_history.emit()
        self.assertTrue(self.popup.isVisible())
        self.assertTrue(self.popup._drawer.isVisible())
        self.assertEqual(len(self.popup._drawer.rows), 1)
        self.assertGreater(self.popup._drawer.y(), self.popup._card.geometry().bottom())
        self.assertGreaterEqual(self.popup.height(),
                                self.popup._drawer.geometry().bottom() + self.popup._pad)
        # Ditado concluído não fecha um histórico aberto; a nova entrada aparece no topo.
        self.history.save("texto novo")
        self.popup.history_changed.emit()
        with patch("config.UI_FADE_OUT_MS", 0):
            self.popup.show_done.emit("texto novo")
        self.assertTrue(self.popup.isVisible())
        self.assertEqual(self.popup._drawer.rows[0].entry["text"], "texto novo")
        self.popup.toggle_history.emit()
        self.assertFalse(self.popup.isVisible())

    def test_copy_and_insert_from_history(self):
        self.history.save("copie isto")
        inserted = Mock()
        self.popup.insert_requested.connect(inserted)
        self.popup.toggle_history.emit()
        row = self.popup._drawer.rows[0]
        self.assertEqual(row.copy_button.focusPolicy(), Qt.NoFocus)
        QTest.mouseClick(row.copy_button, Qt.LeftButton)
        self.assertEqual(QApplication.clipboard().text(), "copie isto")
        QTest.mouseClick(row.insert_button, Qt.LeftButton)
        inserted.assert_called_once_with("copie isto")
        self.assertFalse(self.popup.isVisible())

    def test_empty_history_still_opens(self):
        self.popup.toggle_history.emit()
        self.assertEqual(self.popup._drawer.rows, [])
        self.assertTrue(self.popup._drawer.isVisible())


if __name__ == "__main__":
    unittest.main()
