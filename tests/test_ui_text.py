"""DEED-0035: every word on screen can be translated, and the windows mirror
for right-to-left languages.

Design § What every part does the same way, "Text on screen": every string
`ui` shows goes through Qt's translation mechanism, and every window lays out
correctly when mirrored. The app's name is the one string left untranslated.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QPoint, Qt, QTranslator
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QGroupBox,
    QLabel,
    QLineEdit,
    QWidget,
)

from paperkist.ui import APP_NAME
from paperkist.ui.create_dialog import CreateDialog
from paperkist.ui.main_window import MainWindow
from paperkist.ui.start_dialog import StartDialog
from paperkist.vault import Vault

OPEN, CLOSE = "⟪", "⟫"


class Marking(QTranslator):
    """Wraps every string Qt is asked to translate, so an untranslated one
    shows on screen without the marks."""

    def translate(self, context, source, disambiguation=None, n=-1):
        return f"{OPEN}{source}{CLOSE}"

    def isEmpty(self):  # noqa: N802 — Qt's name
        return False


def shown_text(window: QWidget) -> list[tuple[str, str]]:
    """(where, text) for every piece of text the window shows the user."""
    found = [("title", window.windowTitle())]
    for w in [window, *window.findChildren(QWidget)]:
        name = w.objectName() or type(w).__name__
        found.append((f"{name} tooltip", w.toolTip()))
        if isinstance(w, QLabel):
            found.append((name, w.text()))
        elif isinstance(w, QAbstractButton):
            found.append((name, w.text()))
        elif isinstance(w, QLineEdit):
            found.append((f"{name} placeholder", w.placeholderText()))
        elif isinstance(w, QGroupBox):
            found.append((name, w.title()))
        elif isinstance(w, QAbstractItemView) and w.model() is not None:
            model = w.model()
            for c in range(model.columnCount()):
                header = model.headerData(c, Qt.Orientation.Horizontal)
                found.append((f"{name} column {c}", str(header or "")))
    return [(where, t) for where, t in found if t and t != APP_NAME]


@pytest.fixture
def marked(qt):
    translator = Marking()
    QCoreApplication.installTranslator(translator)
    yield
    QCoreApplication.removeTranslator(translator)


def windows(tmp_path: Path) -> list[QWidget]:
    vault = Vault.create(tmp_path / "vault", "twelve chars")
    note = tmp_path / "note.txt"
    note.write_text("x")
    vault.add(note, "text/plain")
    main = MainWindow(vault)
    view = main.findChild(QAbstractItemView, "documents")
    view.setCurrentIndex(view.model().index(0, 0))  # shows the no-preview text
    return [StartDialog(), CreateDialog(), main]


def test_every_shown_string_goes_through_translation(marked, tmp_path):
    untranslated = [
        (type(w).__name__, where, text)
        for w in windows(tmp_path)
        for where, text in shown_text(w)
        if OPEN not in text
    ]
    assert untranslated == []


def centre_x(widget: QWidget, window: QWidget) -> int:
    return widget.mapTo(window, QPoint(widget.width() // 2, 0)).x()


@pytest.fixture(params=[Qt.LayoutDirection.LeftToRight, Qt.LayoutDirection.RightToLeft])
def direction(qt, request):
    QApplication.setLayoutDirection(request.param)
    yield request.param
    # Auto, not LeftToRight: an explicit direction stops Qt taking it from
    # the installed translation, which the app relies on (test_app.py).
    QApplication.setLayoutDirection(Qt.LayoutDirection.LayoutDirectionAuto)


def test_main_window_mirrors(direction, tmp_path):
    window = MainWindow(Vault.create(tmp_path / "vault", "twelve chars"))
    window.resize(900, 600)
    window.show()
    QApplication.processEvents()
    documents = centre_x(window.findChild(QAbstractItemView, "documents"), window)
    viewer = centre_x(window.findChild(QWidget, "viewer"), window)
    rtl = direction == Qt.LayoutDirection.RightToLeft
    assert (documents > viewer) is rtl  # the list sits where reading starts


def test_create_dialog_mirrors(direction):
    dialog = CreateDialog()
    dialog.show()
    QApplication.processEvents()
    field = dialog.findChild(QLineEdit, "password")
    (label,) = [w for w in dialog.findChildren(QLabel) if w.buddy() is field]
    rtl = direction == Qt.LayoutDirection.RightToLeft
    assert (centre_x(label, dialog) > centre_x(field, dialog)) is rtl
