"""The first window: unlock a vault, or create a new one (DEED-0005)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from paperkist.errors import PaperkistError
from paperkist.ui import APP_NAME, LAST_VAULT, settings
from paperkist.ui.create_dialog import CreateDialog
from paperkist.ui.messages import message_for
from paperkist.vault import Vault


class StartDialog(QDialog):
    """Opens a vault. `vault` holds it once the dialog is accepted."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault: Vault | None = None
        self.setWindowTitle(APP_NAME)

        intro = QLabel(self.tr("Unlock your vault, or create a new one."))
        intro.setWordWrap(True)

        self._folder = QLineEdit(str(settings().value(LAST_VAULT, "")))
        self._folder.setObjectName("folder")
        self._folder.setPlaceholderText(self.tr("The folder that holds your vault"))
        browse = QPushButton(self.tr("Choose…"))
        browse.clicked.connect(self._browse)
        folder_row = QWidget()
        row = QHBoxLayout(folder_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._folder)
        row.addWidget(browse)

        self._password = QLineEdit()
        self._password.setObjectName("password")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)

        self._message = QLabel()
        self._message.setObjectName("message")
        self._message.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        unlock = buttons.addButton(
            self.tr("Unlock"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        unlock.setObjectName("unlock")
        unlock.setDefault(True)
        create = buttons.addButton(
            self.tr("Create a new vault…"), QDialogButtonBox.ButtonRole.ActionRole
        )
        create.setObjectName("create_new")
        buttons.accepted.connect(self._unlock)
        buttons.rejected.connect(self.reject)
        create.clicked.connect(self._create)

        form = QFormLayout()
        form.addRow(self.tr("Vault folder:"), folder_row)
        form.addRow(self.tr("Password:"), self._password)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self._message)
        layout.addStretch()  # keep the fields together when the window grows
        layout.addWidget(buttons)

        if self._folder.text():
            self._password.setFocus()

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, self.tr("Choose your vault's folder")
        )
        if chosen:
            self._folder.setText(chosen)

    def _unlock(self) -> None:
        text = self._folder.text().strip()
        if not text:
            self._message.setText(self.tr("Choose the folder that holds your vault."))
            return
        folder = Path(text).expanduser()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.vault = Vault.open(folder, self._password.text())
        except (PaperkistError, OSError) as error:
            self._message.setText(message_for(error))
            self._password.clear()
            self._password.setFocus()
            return
        finally:
            QApplication.restoreOverrideCursor()
        settings().setValue(LAST_VAULT, str(folder))
        self.accept()

    def _create(self) -> None:
        dialog = CreateDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.vault = dialog.vault
            self.accept()
