"""DEED-0035 and design § The parts, `app`: start-up loads the compiled
translation for the system's language from `ui/translations/`, and a
right-to-left language turns the whole app right-to-left.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLocale, Qt
from PySide6.QtWidgets import QApplication

import paperkist.ui
from paperkist.__main__ import TRANSLATIONS, install_translation

TS = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="{lang}">
<context><name>{context}</name>
<message><source>{source}</source><translation>{translation}</translation></message>
</context>
</TS>
"""


def compile_qm(folder: Path, lang: str, context: str, source: str, text: str) -> None:
    lrelease = shutil.which("pyside6-lrelease")
    assert lrelease, "pyside6-lrelease (ships with PySide6) is not on PATH"
    ts = folder / f"paperkist_{lang}.ts"
    ts.write_text(
        TS.format(lang=lang, context=context, source=source, translation=text),
        encoding="utf-8",
    )
    subprocess.run(  # noqa: S603 — Qt's own compiler, our own file
        [lrelease, str(ts), "-qm", str(folder / f"paperkist_{lang}.qm")],
        check=True,
        capture_output=True,
    )


def test_translations_live_in_the_ui_package():
    assert Path(paperkist.ui.__file__).parent / "translations" == TRANSLATIONS
    assert TRANSLATIONS.is_dir()


def test_the_system_language_is_loaded(qt, tmp_path):
    compile_qm(tmp_path, "af", "Check", "Hello", "Hallo")
    translator = install_translation(qt, QLocale("af_ZA"), tmp_path)
    try:
        assert translator is not None
        assert QCoreApplication.translate("Check", "Hello") == "Hallo"
    finally:
        QCoreApplication.removeTranslator(translator)


def test_a_language_with_no_translation_stays_in_english(qt, tmp_path):
    assert install_translation(qt, QLocale("af_ZA"), tmp_path) is None
    assert QCoreApplication.translate("Check", "Hello") == "Hello"


def test_a_right_to_left_language_turns_the_app_around(qt, tmp_path):
    # Qt reads the direction from this one string in each translation.
    compile_qm(tmp_path, "ar", "QGuiApplication", "QT_LAYOUT_DIRECTION", "RTL")
    translator = install_translation(qt, QLocale("ar_EG"), tmp_path)
    try:
        QApplication.processEvents()
        assert QApplication.layoutDirection() == Qt.LayoutDirection.RightToLeft
    finally:
        QCoreApplication.removeTranslator(translator)
        QApplication.processEvents()
    assert QApplication.layoutDirection() == Qt.LayoutDirection.LeftToRight
