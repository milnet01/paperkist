"""DEED-0005: add by dragging files in, list the documents, and view PDFs and
images inside the window.

Design rule 4: no part writes a decrypted temporary file, not for viewing.
Design § The stack: v1 shows PDFs and common image types; anything else is
stored but not previewed. § State: the key is dropped when the vault closes.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QImage, QPainter, QPdfWriter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView, QApplication, QLabel, QWidget

from paperkist.ui.main_window import MainWindow
from paperkist.vault import Vault

PASSWORD = "twelve chars"  # noqa: S105 — a test vault's password, not a secret


def new_vault(tmp_path: Path) -> tuple[Path, Vault]:
    folder = tmp_path / "vault"
    return folder, Vault.create(folder, PASSWORD)


def make_pdf(path: Path) -> bytes:
    writer = QPdfWriter(str(path))
    painter = QPainter(writer)
    painter.drawText(100, 100, "A receipt for a kettle")
    painter.end()
    return path.read_bytes()


def make_png(path: Path) -> bytes:
    image = QImage(40, 30, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.darkCyan)
    assert image.save(str(path), "PNG")
    return path.read_bytes()


def open_window(vault: Vault) -> MainWindow:
    window = MainWindow(vault)
    window.resize(900, 600)
    window.show()
    QApplication.processEvents()
    return window


def drop(window: QWidget, paths: list[Path]) -> None:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    buttons, mods = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    enter = QDragEnterEvent(
        QPoint(10, 10), Qt.DropAction.CopyAction, mime, buttons, mods
    )
    QApplication.sendEvent(window, enter)
    assert enter.isAccepted(), "the window refuses a drag of files"
    event = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, buttons, mods)
    QApplication.sendEvent(window, event)
    QApplication.processEvents()


def listed(window: QWidget) -> list[str]:
    model = window.findChild(QAbstractItemView, "documents").model()
    return [str(model.index(r, 0).data()) for r in range(model.rowCount())]


def select(window: QWidget, filename: str) -> None:
    view = window.findChild(QAbstractItemView, "documents")
    model = view.model()
    row = listed(window).index(filename)
    view.setCurrentIndex(model.index(row, 0))
    QApplication.processEvents()


def copies_on_disk(root: Path, data: bytes, original: Path) -> list[Path]:
    """Every file under `root`, other than the original, holding `data`."""
    return [
        p
        for p in root.rglob("*")
        if p.is_file() and p != original and data in p.read_bytes()
    ]


# Every file Python opens for writing is recorded while a recording is open.
# This sees a write wherever it lands; the scans below see Qt's own writes
# into the temp folder and the current folder.
_RECORDINGS: list[list[str]] = []
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT


def _audit(event: str, args: tuple) -> None:
    if event != "open" or not _RECORDINGS:
        return
    path, mode, flags = args
    if (mode and any(c in mode for c in "wax+")) or (flags or 0) & _WRITE_FLAGS:
        _RECORDINGS[-1].append(str(path))


sys.addaudithook(_audit)


@contextlib.contextmanager
def writes_recorded():
    writes: list[str] = []
    _RECORDINGS.append(writes)
    try:
        yield writes
    finally:
        _RECORDINGS.remove(writes)


def private_temp(tmp_path, monkeypatch) -> Path:
    """Send temporary files, and the current folder, into this test's folder."""
    monkeypatch.chdir(tmp_path)
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setenv("TMPDIR", str(temp))
    monkeypatch.setenv("TEMP", str(temp))
    monkeypatch.setenv("TMP", str(temp))
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    return temp


def test_dropped_files_are_added_and_listed(qt, tmp_path):
    _, vault = new_vault(tmp_path)
    pdf, png = tmp_path / "kettle.pdf", tmp_path / "passport.png"
    make_pdf(pdf)
    make_png(png)
    window = open_window(vault)
    drop(window, [pdf, png])
    assert sorted(listed(window)) == ["kettle.pdf", "passport.png"]
    types = {d["filename"]: d["type"] for d in vault.documents()}
    assert types == {"kettle.pdf": "application/pdf", "passport.png": "image/png"}


def test_documents_already_in_the_vault_are_listed(qt, tmp_path):
    _, vault = new_vault(tmp_path)
    pdf = tmp_path / "policy.pdf"
    make_pdf(pdf)
    vault.add(pdf, "application/pdf")
    assert listed(open_window(vault)) == ["policy.pdf"]


def test_a_pdf_is_shown_without_a_readable_copy_on_disk(qt, tmp_path, monkeypatch):
    temp = private_temp(tmp_path, monkeypatch)
    _, vault = new_vault(tmp_path)
    source = tmp_path / "kettle.pdf"
    data = make_pdf(source)
    window = open_window(vault)
    drop(window, [source])
    with writes_recorded() as writes:
        select(window, "kettle.pdf")

    document = window.findChild(QPdfView).document()
    for _ in range(100):
        if document.status() == QPdfDocument.Status.Ready:
            break
        QTest.qWait(20)
    assert document.status() == QPdfDocument.Status.Ready
    assert document.pageCount() == 1
    assert writes == []
    window.close()  # releases the vault's lock, which Windows will not let us read
    QApplication.processEvents()
    assert copies_on_disk(tmp_path, data, source) == []
    assert list(temp.iterdir()) == []


def test_an_image_is_shown_without_a_readable_copy_on_disk(qt, tmp_path, monkeypatch):
    temp = private_temp(tmp_path, monkeypatch)
    _, vault = new_vault(tmp_path)
    source = tmp_path / "passport.png"
    data = make_png(source)
    window = open_window(vault)
    drop(window, [source])
    with writes_recorded() as writes:
        select(window, "passport.png")

    image = window.findChild(QLabel, "image_view")
    assert image.isVisible()
    assert not image.pixmap().isNull()
    assert writes == []
    window.close()  # releases the vault's lock, which Windows will not let us read
    QApplication.processEvents()
    assert copies_on_disk(tmp_path, data, source) == []
    assert list(temp.iterdir()) == []


def test_other_types_are_stored_but_not_previewed(qt, tmp_path):
    _, vault = new_vault(tmp_path)
    source = tmp_path / "notes.txt"
    source.write_bytes(b"tyre pressures: 2.2 bar")
    window = open_window(vault)
    drop(window, [source])
    select(window, "notes.txt")

    assert window.findChild(QWidget, "no_preview").isVisible()
    (doc,) = vault.documents()
    assert vault.read(doc["id"]) == b"tyre pressures: 2.2 bar"


def test_closing_the_window_closes_the_vault(qt, tmp_path):
    folder, vault = new_vault(tmp_path)
    window = open_window(vault)
    window.close()
    QApplication.processEvents()
    Vault.open(folder, PASSWORD).close()  # the lock was released
