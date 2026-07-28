# -*- coding: utf-8 -*-
"""Переиспользуемые элементы интерфейса."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy,
                               QVBoxLayout, QWidget)

from ..services.transcribe import SUPPORTED_SUFFIXES
from . import theme


class Card(QFrame):
    """Карточка с рамкой — базовый контейнер интерфейса."""

    def __init__(self, parent: QWidget | None = None, padding: int = 20) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(12)
        self.body = layout


class Separator(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("separator")
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


class StepIndicator(QWidget):
    """Полоса шагов мастера сверху окна."""

    def __init__(self, steps: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._labels: list[QLabel] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for index, title in enumerate(steps):
            label = QLabel(f"{index + 1}. {title}")
            label.setObjectName("stepBadge")
            self._labels.append(label)
            layout.addWidget(label)
            if index < len(steps) - 1:
                arrow = QLabel("→")
                arrow.setObjectName("dim")
                layout.addWidget(arrow)
        layout.addStretch()

    def set_active(self, index: int) -> None:
        for position, label in enumerate(self._labels):
            label.setObjectName("stepBadgeActive" if position == index else "stepBadge")
            label.style().unpolish(label)
            label.style().polish(label)


class InfoRow(QWidget):
    """Строка «подпись — значение» для карточки компании."""

    def __init__(self, caption: str, value: str = "—",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._caption = QLabel(caption)
        self._caption.setObjectName("muted")
        self._caption.setFixedWidth(150)
        self._caption.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self._value = QLabel(value)
        self._value.setWordWrap(True)
        self._value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout.addWidget(self._caption)
        layout.addWidget(self._value, 1)

    def set_value(self, value: str) -> None:
        self._value.setText(value or "—")


class DropZone(QFrame):
    """Зона перетаскивания аудиофайла."""

    file_selected = Signal(str)
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(190)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        icon = QLabel("🎧")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 40px;")

        self._title = QLabel("Перетащите запись разговора")
        self._title.setObjectName("h2")
        self._title.setAlignment(Qt.AlignCenter)

        hint = QLabel("или нажмите, чтобы выбрать файл  ·  "
                      + ", ".join(sorted(s.lstrip(".") for s in SUPPORTED_SUFFIXES)))
        hint.setObjectName("dim")
        hint.setAlignment(Qt.AlignCenter)

        layout.addWidget(icon)
        layout.addWidget(self._title)
        layout.addWidget(hint)

    # --- перетаскивание -------------------------------------------------
    def _is_supported(self, path: str) -> bool:
        return Path(path).suffix.lower() in SUPPORTED_SUFFIXES

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if urls and self._is_supported(urls[0].toLocalFile()):
            event.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, event) -> None:
        self._set_active(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_active(False)
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if self._is_supported(path):
            self.file_selected.emit(path)
            event.acceptProposedAction()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def _set_active(self, active: bool) -> None:
        self.setObjectName("dropZoneActive" if active else "dropZone")
        self.style().unpolish(self)
        self.style().polish(self)

    def show_file(self, path: str) -> None:
        self._title.setText(Path(path).name)


class StatusBadge(QLabel):
    """Цветная метка состояния (ИИ включён, режим без ИИ и т. п.)."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.set_kind("muted")

    def set_kind(self, kind: str) -> None:
        colors = {
            "success": theme.SUCCESS,
            "warning": theme.WARNING,
            "danger": theme.DANGER,
            "muted": theme.TEXT_MUTED,
        }
        color = colors.get(kind, theme.TEXT_MUTED)
        self.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: 600;"
            f"background: transparent; padding: 2px 0;"
        )
