"""DEED-0005: creating and unlocking a vault.

The owner's decisions (2026-09-28, on DEED-0005): Create stays disabled until
the owner ticks that a forgotten password cannot be recovered (S2); a new
password is 12 or more characters, typed twice, with no other rules; a new
vault defaults to a Paperkist-named folder in Documents. Design § What every
part does the same way: `ui` turns each error into one plain-language message.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QLineEdit, QPushButton

from paperkist import errors
from paperkist.errors import VaultExists, WrongPassword
from paperkist.ui import APP_NAME
from paperkist.ui.create_dialog import CreateDialog
from paperkist.ui.messages import message_for
from paperkist.ui.start_dialog import StartDialog
from paperkist.vault import Vault

GOOD = "twelve chars"  # exactly 12 characters


def fill_create(dialog, folder, password, confirm, tick):
    dialog.findChild(QLineEdit, "folder").setText(str(folder))
    QTest.keyClicks(dialog.findChild(QLineEdit, "password"), password)
    QTest.keyClicks(dialog.findChild(QLineEdit, "confirm"), confirm)
    dialog.findChild(QCheckBox, "understood").setChecked(tick)


@pytest.mark.parametrize(
    ("password", "confirm", "tick", "folder", "enabled"),
    [
        (GOOD, GOOD, True, True, True),
        ("eleven char", "eleven char", True, True, False),
        (GOOD, GOOD + "x", True, True, False),
        (GOOD, GOOD, False, True, False),
        (GOOD, GOOD, True, False, False),
        ("", "", False, True, False),
    ],
    ids=["all-met", "11-chars", "mismatch", "not-ticked", "no-folder", "empty"],
)
def test_create_enabled_only_when_rules_met(
    qt, tmp_path, password, confirm, tick, folder, enabled
):
    dialog = CreateDialog()
    fill_create(dialog, tmp_path / "vault" if folder else "", password, confirm, tick)
    assert dialog.findChild(QPushButton, "create").isEnabled() is enabled


def test_default_folder_is_named_for_the_app_in_documents(qt):
    documents = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    dialog = CreateDialog()
    folder = dialog.findChild(QLineEdit, "folder").text()
    assert Path(folder) == Path(documents) / APP_NAME


def test_create_makes_a_vault_that_opens_with_the_password(qt, tmp_path):
    folder = tmp_path / "vault"
    dialog = CreateDialog()
    fill_create(dialog, folder, GOOD, GOOD, True)
    QTest.mouseClick(dialog.findChild(QPushButton, "create"), Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert isinstance(dialog.vault, Vault)
    dialog.vault.close()
    Vault.open(folder, GOOD).close()


def test_create_in_a_used_folder_shows_a_message_and_writes_nothing(qt, tmp_path):
    folder = tmp_path / "used"
    folder.mkdir()
    (folder / "mine.txt").write_text("someone's file")
    dialog = CreateDialog()
    fill_create(dialog, folder, GOOD, GOOD, True)
    QTest.mouseClick(dialog.findChild(QPushButton, "create"), Qt.MouseButton.LeftButton)
    assert dialog.vault is None
    assert dialog.findChild(QLabel, "message").text() == message_for(
        VaultExists(str(folder))
    )
    assert [p.name for p in folder.iterdir()] == ["mine.txt"]


def unlock(folder, password):
    dialog = StartDialog()
    dialog.findChild(QLineEdit, "folder").setText(str(folder))
    QTest.keyClicks(dialog.findChild(QLineEdit, "password"), password)
    QTest.mouseClick(dialog.findChild(QPushButton, "unlock"), Qt.MouseButton.LeftButton)
    return dialog


def test_wrong_password_shows_the_plain_message(qt, tmp_path):
    folder = tmp_path / "vault"
    Vault.create(folder, GOOD).close()
    dialog = unlock(folder, "not the password")
    assert dialog.vault is None
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.findChild(QLabel, "message").text() == message_for(WrongPassword())


def test_unlock_opens_the_vault_and_remembers_its_folder(qt, tmp_path):
    folder = tmp_path / "vault"
    Vault.create(folder, GOOD).close()
    dialog = unlock(folder, GOOD)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert isinstance(dialog.vault, Vault)
    dialog.vault.close()
    again = StartDialog()
    remembered = again.findChild(QLineEdit, "folder").text()
    assert Path(remembered) == folder


def test_every_error_type_has_its_own_message(qt):
    types = [
        t
        for t in vars(errors).values()
        if isinstance(t, type) and issubclass(t, errors.PaperkistError)
    ]
    texts = [message_for(t("detail")) for t in types]
    assert all(isinstance(t, str) and t.strip() for t in texts)
    assert len(set(texts)) == len(texts)
    assert "detail" not in "".join(texts)  # the message is plain words, not internals
    assert message_for(OSError("x")).strip()
