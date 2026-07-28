# -*- coding: utf-8 -*-
"""Точка входа KPGEN ESTP."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.ui.main_window import MainWindow
    from app.ui import theme
else:
    from .ui.main_window import MainWindow
    from .ui import theme


def build_application(argv: list[str]) -> QApplication:
    application = QApplication(argv)
    application.setApplicationName("KPGEN ESTP")
    application.setOrganizationName("ESTP")
    application.setStyle("Fusion")

    # Тёмная палитра нужна для системных элементов (меню, диалоги выбора файла).
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(theme.BACKGROUND))
    palette.setColor(QPalette.WindowText, QColor(theme.TEXT))
    palette.setColor(QPalette.Base, QColor(theme.SURFACE))
    palette.setColor(QPalette.AlternateBase, QColor(theme.CARD))
    palette.setColor(QPalette.Text, QColor(theme.TEXT))
    palette.setColor(QPalette.Button, QColor(theme.CARD))
    palette.setColor(QPalette.ButtonText, QColor(theme.TEXT))
    palette.setColor(QPalette.Highlight, QColor(theme.ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor("#06232B"))
    palette.setColor(QPalette.ToolTipBase, QColor(theme.CARD))
    palette.setColor(QPalette.ToolTipText, QColor(theme.TEXT))
    palette.setColor(QPalette.PlaceholderText, QColor(theme.TEXT_DIM))
    application.setPalette(palette)

    return application


def main() -> int:
    application = build_application(sys.argv)
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
