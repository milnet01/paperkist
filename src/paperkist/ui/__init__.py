"""Every window and dialog, one file each (docs/design.md § The parts, `ui`)."""

from __future__ import annotations

from PySide6.QtCore import QSettings

# The app's name, in one place: a rename changes this line (DEED-0023).
APP_NAME = "Paperkist"

LAST_VAULT = "vault/last_folder"


def settings() -> QSettings:
    """The one settings file, in the user's app-data folder (design § Settings)."""
    return QSettings(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, APP_NAME, APP_NAME
    )
