"""The main window: the document list beside the viewer (DEED-0005).

Files are added by dragging them onto the window, or with Add documents. The
vault closes, and its key is dropped, when the window closes (design § State).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDate, QLocale, QMimeDatabase, QModelIndex, Qt
from PySide6.QtGui import QAction, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from paperkist.errors import PaperkistError
from paperkist.ui import APP_NAME
from paperkist.ui.messages import message_for
from paperkist.ui.viewer import DocumentViewer
from paperkist.vault import Vault

ID = Qt.ItemDataRole.UserRole


class MainWindow(QMainWindow):
    def __init__(self, vault: Vault, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vault = vault
        self.setWindowTitle(APP_NAME)
        self.setAcceptDrops(True)

        self._model = QStandardItemModel(0, 3, self)
        self._model.setHorizontalHeaderLabels(
            [self.tr("Name"), self.tr("Added"), self.tr("Size")]
        )
        self._list = QTableView()
        self._list.setObjectName("documents")
        self._list.setModel(self._model)
        self._list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._list.verticalHeader().hide()
        header = self._list.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self._list.selectionModel().currentRowChanged.connect(self._show)

        hint = QLabel(self.tr("Drag documents onto this window to add them."))
        hint.setWordWrap(True)
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.addWidget(hint)
        side_layout.addWidget(self._list)

        self._viewer = DocumentViewer()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(side)
        splitter.addWidget(self._viewer)
        splitter.setStretchFactor(0, 1)  # the list gets a third of the width
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

        add = QAction(self.tr("Add documents…"), self)
        add.triggered.connect(self._choose_files)
        toolbar = self.addToolBar(self.tr("Documents"))
        toolbar.setObjectName("toolbar")
        toolbar.addAction(add)

        self._reload()
        damaged = len(vault.damaged())
        if damaged:
            self._tell(
                self.tr(
                    "%n document(s) in this vault could not be read and were "
                    "left untouched.",
                    "",
                    damaged,
                )
            )

    # Adding --------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802 — Qt's name
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 — Qt's name
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 — Qt's name
        paths = [
            Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()
        ]
        event.acceptProposedAction()
        self.add_files(paths)

    def _choose_files(self) -> None:
        chosen, _ = QFileDialog.getOpenFileNames(self, self.tr("Add documents"))
        self.add_files([Path(p) for p in chosen])

    def add_files(self, paths: list[Path]) -> None:
        mime = QMimeDatabase()
        problems = []
        for path in paths:
            if not path.is_file():
                problems.append(
                    self.tr("{name} is not a file, so it was not added.").format(
                        name=path.name
                    )
                )
                continue
            try:
                self._vault.add(path, mime.mimeTypeForFile(str(path)).name())
            except (PaperkistError, OSError) as error:
                problems.append(f"{path.name}: {message_for(error)}")
        self._reload()
        if problems:
            self._tell("\n".join(problems))

    # Listing and viewing ---------------------------------------------------

    def _reload(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        locale = QLocale()
        documents = sorted(self._vault.documents(), key=lambda d: d["filename"].lower())
        for doc in documents:
            name = QStandardItem(doc["filename"])
            name.setData(doc["id"], ID)
            added = QDate.fromString(doc["added"], Qt.DateFormat.ISODate)
            row = [
                name,
                QStandardItem(locale.toString(added, QLocale.FormatType.ShortFormat)),
                QStandardItem(locale.formattedDataSize(doc["size"])),
            ]
            for item in row:
                item.setEditable(False)
            self._model.appendRow(row)

    def _show(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            self._viewer.clear()
            return
        doc_id = self._model.index(current.row(), 0).data(ID)
        try:
            data = self._vault.read(doc_id)
            mime_type = self._vault.metadata(doc_id)["type"]
        except PaperkistError as error:
            self._viewer.show_message(message_for(error))
            return
        self._viewer.show_document(data, mime_type)

    def _tell(self, text: str) -> None:
        box = QMessageBox(QMessageBox.Icon.Warning, APP_NAME, text, parent=self)
        box.open()

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt's name
        self._viewer.clear()
        self._vault.close()
        super().closeEvent(event)
