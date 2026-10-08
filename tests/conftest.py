"""Shared fixtures for the window tests (DEED-0005).

Qt runs without a display (`offscreen`), so the window tests run headless on
all three systems in CI, like every other test.
"""

from __future__ import annotations

import functools
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def qt(qapp, tmp_path, monkeypatch):
    """A Qt application whose settings live in this test's folder, and whose
    new vaults use the cheapest key derivation, so a test is fast and never
    reads or writes the real user's settings."""
    import nacl.pwhash.argon2id as argon2id
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from paperkist.vault import Vault

    settings = str(tmp_path / "settings")
    for fmt in (QSettings.Format.IniFormat, QSettings.Format.NativeFormat):
        QSettings.setPath(fmt, QSettings.Scope.UserScope, settings)
    fast = {"opslimit": argon2id.OPSLIMIT_MIN, "memlimit": argon2id.MEMLIMIT_MIN}
    monkeypatch.setattr(Vault, "create", functools.partial(Vault.create, **fast))
    yield qapp
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QApplication.processEvents()
