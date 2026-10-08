"""One plain-language message per error (design § What every part does the
same way, Errors). Each string is written out in full in its translate call so
Qt's string extractor finds it."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication

from paperkist import errors
from paperkist.ui import APP_NAME


def message_for(error: BaseException) -> str:
    """What to tell the user about `error`. Never its internal details."""
    tr = QCoreApplication.translate
    if isinstance(error, errors.NotAVault):
        return tr(
            "messages",
            "This folder does not hold a vault. Choose the folder you created "
            "the vault in.",
        )
    if isinstance(error, errors.VaultExists):
        return tr(
            "messages",
            "That folder already has files in it. Choose an empty folder, or a "
            "new one, for the vault.",
        )
    if isinstance(error, errors.WrongPassword):
        return tr(
            "messages",
            "That password does not open this vault. Check it and try again.",
        )
    if isinstance(error, errors.VaultCorrupt):
        return tr(
            "messages",
            "Part of the vault could not be read. It may be damaged.",
        )
    if isinstance(error, errors.NotEnoughMemory):
        return tr(
            "messages",
            "There is not enough free memory to unlock the vault. Close some "
            "other programs and try again.",
        )
    if isinstance(error, errors.VaultTooNew):
        return tr(
            "messages",
            "This vault was made by a newer version of {app}. Install the newer "
            "version to open it.",
        ).format(app=APP_NAME)
    if isinstance(error, errors.VaultInUse):
        return tr(
            "messages",
            "This vault is already open in another {app} window. Close it there first.",
        ).format(app=APP_NAME)
    if isinstance(error, errors.DocumentMissing):
        return tr("messages", "That document is no longer in the vault.")
    if isinstance(error, errors.PaperkistError):
        return tr("messages", "Something went wrong with the vault.")
    if isinstance(error, OSError):
        return tr(
            "messages",
            "A file could not be read or written. Check that it still exists "
            "and that you are allowed to open it.",
        )
    return tr("messages", "Something went wrong.")
