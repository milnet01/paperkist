"""Shows one document inside the window, from memory (DEED-0005).

Design rule 4: no decrypted temporary file. A PDF is handed to Qt's PDF
reader through an in-memory buffer; an image is decoded from bytes. v1 shows
PDFs and common image types only (design § The stack).
"""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QLabel, QScrollArea, QStackedWidget, QWidget


def _centred_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


class DocumentViewer(QStackedWidget):
    """One page per kind of content; the decrypted bytes live only here."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("viewer")

        self._empty = _centred_label(self.tr("Choose a document to see it here."))
        self._empty.setObjectName("empty")
        self._no_preview = _centred_label(
            self.tr(
                "This kind of file cannot be shown here. It is stored safely "
                "in the vault."
            )
        )
        self._no_preview.setObjectName("no_preview")

        self._pdf = QPdfDocument(self)
        self._pdf_view = QPdfView()
        self._pdf_view.setDocument(self._pdf)
        self._pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._buffer: QBuffer | None = None

        self._image = QImage()
        self._image_label = _centred_label()
        self._image_label.setObjectName("image_view")
        self._image_area = QScrollArea()
        self._image_area.setWidgetResizable(True)
        self._image_area.setWidget(self._image_label)

        for page in (self._empty, self._no_preview, self._pdf_view, self._image_area):
            self.addWidget(page)

    def show_document(self, data: bytes, mime_type: str) -> None:
        self.clear()
        if mime_type == "application/pdf":
            self._buffer = QBuffer(self)
            self._buffer.setData(QByteArray(data))
            self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self._pdf.load(self._buffer)
            if self._pdf.status() != QPdfDocument.Status.Error:
                self.setCurrentWidget(self._pdf_view)
                return
        elif mime_type.startswith("image/"):
            self._image = QImage.fromData(data)
            if not self._image.isNull():
                self.setCurrentWidget(self._image_area)
                self._fit_image()
                return
        self.clear()
        self.setCurrentWidget(self._no_preview)

    def show_message(self, text: str) -> None:
        self.clear()
        self._empty.setText(text)

    def clear(self) -> None:
        """Drop the shown document's bytes and go back to the empty page."""
        self._pdf.close()
        if self._buffer is not None:
            self._buffer.close()
            self._buffer.deleteLater()
            self._buffer = None
        self._image = QImage()
        self._image_label.clear()
        self._empty.setText(self.tr("Choose a document to see it here."))
        self.setCurrentWidget(self._empty)

    def resizeEvent(self, event) -> None:  # noqa: N802 — Qt's name
        super().resizeEvent(event)
        self._fit_image()

    def _fit_image(self) -> None:
        """Shrink a large image to the visible width; never enlarge a small one."""
        if self._image.isNull():
            return
        width = max(1, self._image_area.viewport().width())
        image = self._image
        if image.width() > width:
            image = image.scaledToWidth(
                width, Qt.TransformationMode.SmoothTransformation
            )
        self._image_label.setPixmap(QPixmap.fromImage(image))
