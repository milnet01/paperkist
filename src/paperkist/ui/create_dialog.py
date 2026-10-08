"""Creating a vault (DEED-0005).

The owner's decisions (2026-09-28): Create stays disabled until the user ticks
that a forgotten password cannot be recovered (S2); a password is 12 or more
characters, typed twice, with no other rules; the folder defaults to a
Paperkist-named one in Documents, and any folder can be chosen.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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
from paperkist.ui.messages import message_for
from paperkist.vault import Vault

MIN_LENGTH = 12


def default_folder() -> Path:
    documents = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    return Path(documents) / APP_NAME


class CreateDialog(QDialog):
    """Asks for a folder and a new password. `vault` holds the result."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault: Vault | None = None
        self.setWindowTitle(self.tr("Create a vault"))

        intro = QLabel(
            self.tr(
                "Your documents are locked with one password. Nobody can open "
                "the vault without it, not even you: if you forget it, your "
                "documents are lost for good."
            )
        )
        intro.setWordWrap(True)

        self._folder = QLineEdit(str(default_folder()))
        self._folder.setObjectName("folder")
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
        self._password.setPlaceholderText(self.tr("At least 12 characters"))
        self._confirm = QLineEdit()
        self._confirm.setObjectName("confirm")
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)

        self._understood = QCheckBox(
            self.tr(
                "I understand my documents cannot be recovered without this password"
            )
        )
        self._understood.setObjectName("understood")

        self._hint = QLabel()
        self._hint.setObjectName("hint")
        self._hint.setWordWrap(True)
        self._message = QLabel()
        self._message.setObjectName("message")
        self._message.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._create = buttons.addButton(
            self.tr("Create"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._create.setObjectName("create")
        buttons.accepted.connect(self._create_vault)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow(self.tr("Folder:"), folder_row)
        form.addRow(self.tr("Password:"), self._password)
        form.addRow(self.tr("Password again:"), self._confirm)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self._understood)
        layout.addWidget(self._hint)
        layout.addWidget(self._message)
        layout.addStretch()  # keep the fields together when the window grows
        layout.addWidget(buttons)

        for edit in (self._folder, self._password, self._confirm):
            edit.textChanged.connect(self._update)
        self._understood.toggled.connect(self._update)
        self._update()

    def _update(self) -> None:
        password, confirm = self._password.text(), self._confirm.text()
        long_enough = len(password) >= MIN_LENGTH
        same = password == confirm
        if password and not long_enough:
            self._hint.setText(self.tr("The password needs at least 12 characters."))
        elif confirm and not same:
            self._hint.setText(self.tr("The two passwords are different."))
        else:
            self._hint.clear()
        ready = (
            bool(self._folder.text().strip())
            and long_enough
            and same
            and self._understood.isChecked()
        )
        self._create.setEnabled(ready)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, self.tr("Choose a folder"))
        if chosen:
            self._folder.setText(chosen)

    def _create_vault(self) -> None:
        if not self._create.isEnabled():
            return
        folder = Path(self._folder.text().strip()).expanduser()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.vault = Vault.create(folder, self._password.text())
        except (PaperkistError, OSError) as error:
            self._message.setText(message_for(error))
            return
        finally:
            QApplication.restoreOverrideCursor()
        settings().setValue(LAST_VAULT, str(folder))
        self.accept()
