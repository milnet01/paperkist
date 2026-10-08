"""Start-up: `python -m paperkist` (docs/design.md § The parts, `app`).

Builds the Qt application, loads the translation for the system's language
from `ui/translations/`, and opens the first window.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication, QDialog

import paperkist.ui
from paperkist.ui import APP_NAME
from paperkist.ui.main_window import MainWindow
from paperkist.ui.start_dialog import StartDialog

TRANSLATIONS = Path(paperkist.ui.__file__).parent / "translations"


def install_translation(
    app: QApplication, locale: QLocale, directory: Path = TRANSLATIONS
) -> QTranslator | None:
    """Install `paperkist_<language>.qm` for `locale`, if there is one.

    A right-to-left translation turns the whole app right-to-left: Qt reads
    the direction from the translation itself.
    """
    translator = QTranslator(app)
    if not translator.load(locale, "paperkist", "_", str(directory)):
        return None
    app.installTranslator(translator)
    return translator


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    install_translation(app, QLocale.system())
    start = StartDialog()
    if start.exec() != QDialog.DialogCode.Accepted:
        return 0
    window = MainWindow(start.vault)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
