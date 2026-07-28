# -*- coding: utf-8 -*-
"""Окно настроек: подпись менеджера, шаблоны, модели, папка результатов."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QTabWidget, QVBoxLayout, QWidget)

from ..services import analyze
from ..services.settings import Settings, bundled_templates_dir
from . import theme
from .widgets import StatusBadge


class PathPicker(QWidget):
    """Поле пути с кнопкой выбора."""

    def __init__(self, caption: str, file_filter: str = "",
                 directory: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._caption = caption
        self._filter = file_filter
        self._directory = directory

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.edit = QLineEdit()
        button = QPushButton("Обзор…")
        button.clicked.connect(self._choose)

        layout.addWidget(self.edit, 1)
        layout.addWidget(button)

    def _choose(self) -> None:
        current = self.edit.text().strip()
        start = current if current and Path(current).exists() else str(Path.home())
        if self._directory:
            path = QFileDialog.getExistingDirectory(self, self._caption, start)
        else:
            path, _ = QFileDialog.getOpenFileName(self, self._caption, start,
                                                  self._filter)
        if path:
            self.edit.setText(path)

    def value(self) -> str:
        return self.edit.text().strip()

    def set_value(self, value: str) -> None:
        self.edit.setText(value or "")


class SettingsDialog(QDialog):
    """Настройки приложения."""

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings

        self.setWindowTitle("Настройки")
        self.setMinimumSize(660, 560)
        self.setStyleSheet(theme.STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("Настройки")
        title.setObjectName("h1")
        root.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_manager_tab(), "Подпись")
        tabs.addTab(self._build_templates_tab(), "Шаблоны")
        tabs.addTab(self._build_engine_tab(), "Распознавание и ИИ")
        root.addWidget(tabs, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Сохранить")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        self._load()

    # ------------------------------------------------------------------
    def _build_manager_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft)

        self.full_name = QLineEdit()
        self.position = QLineEdit()
        self.phone_1 = QLineEdit()
        self.phone_2 = QLineEdit()
        self.phone_3 = QLineEdit()
        self.email = QLineEdit()
        self.site = QLineEdit()

        hint = QLabel("Эти данные подставляются в подпись КП "
                      "и на последний слайд презентации.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        form.addRow(hint)

        form.addRow("ФИО", self.full_name)
        form.addRow("Должность", self.position)
        form.addRow("Телефон 1", self.phone_1)
        form.addRow("Телефон 2", self.phone_2)
        form.addRow("Телефон 3", self.phone_3)
        form.addRow("E-mail", self.email)
        form.addRow("Сайт", self.site)
        return page

    def _build_templates_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        hint = QLabel(
            "Можно указать свои файлы — например, когда изменится текст КП.\n"
            "В шаблоне КП сохраняйте плейсхолдеры вида {{ОПИСАНИЕ_КОМПАНИИ}}: "
            "программа подставляет в них данные клиента."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.kp_template = PathPicker("Шаблон КП", "Документ Word (*.docx)")
        self.pres_template = PathPicker("Шаблон презентации",
                                        "Презентация PowerPoint (*.pptx)")
        self.output_dir = PathPicker("Папка для готовых файлов", directory=True)

        for caption, widget in (
            ("Шаблон коммерческого предложения", self.kp_template),
            ("Шаблон презентации", self.pres_template),
            ("Папка для готовых файлов", self.output_dir),
        ):
            label = QLabel(caption)
            layout.addWidget(label)
            layout.addWidget(widget)

        reset = QPushButton("Вернуть шаблоны по умолчанию")
        reset.clicked.connect(self._reset_templates)
        layout.addWidget(reset, 0, Qt.AlignLeft)

        layout.addStretch()
        return page

    def _build_engine_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)

        self.whisper_model = QComboBox()
        self.whisper_model.addItems(["tiny", "base", "small", "medium", "large-v3"])
        form.addRow("Модель распознавания речи", self.whisper_model)

        self.use_ai = QCheckBox("Использовать ИИ для выжимки и текста КП")
        form.addRow(self.use_ai)

        self.ollama_url = QLineEdit()
        form.addRow("Адрес Ollama", self.ollama_url)

        self.ollama_model = QComboBox()
        self.ollama_model.setEditable(True)
        form.addRow("Модель ИИ", self.ollama_model)

        self.dadata_token = QLineEdit()
        self.dadata_token.setEchoMode(QLineEdit.Password)
        form.addRow("Ключ DaData", self.dadata_token)

        layout.addLayout(form)

        check_row = QHBoxLayout()
        check = QPushButton("Проверить связь")
        check.clicked.connect(self._check_engine)
        self.engine_status = StatusBadge("")
        check_row.addWidget(check)
        check_row.addWidget(self.engine_status, 1)
        layout.addLayout(check_row)

        note = QLabel(
            "Без ИИ программа продолжит работать: тексты будут составлены "
            "по правилам, но получатся более шаблонными."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    def _reset_templates(self) -> None:
        folder = bundled_templates_dir()
        self.kp_template.set_value(str(folder / "kp_template.docx"))
        self.pres_template.set_value(str(folder / "presentation_template.pptx"))

    def _check_engine(self) -> None:
        url = self.ollama_url.text().strip()
        if not analyze.ollama_available(url):
            self.engine_status.set_kind("warning")
            self.engine_status.setText(
                "Ollama не отвечает — будет использован режим без ИИ")
            return

        models = analyze.installed_models(url)
        current = self.ollama_model.currentText().strip()
        self.ollama_model.clear()
        self.ollama_model.addItems(models)
        if current:
            self.ollama_model.setCurrentText(current)

        if current and current not in models:
            self.engine_status.set_kind("warning")
            self.engine_status.setText(
                f"Ollama работает, но модель «{current}» не установлена")
        else:
            self.engine_status.set_kind("success")
            self.engine_status.setText(f"Ollama работает, моделей: {len(models)}")

    # ------------------------------------------------------------------
    def _load(self) -> None:
        manager = self._settings.manager
        self.full_name.setText(manager.full_name)
        self.position.setText(manager.position)
        self.phone_1.setText(manager.phone_1)
        self.phone_2.setText(manager.phone_2)
        self.phone_3.setText(manager.phone_3)
        self.email.setText(manager.email)
        self.site.setText(manager.site)

        self.kp_template.set_value(self._settings.kp_template)
        self.pres_template.set_value(self._settings.presentation_template)
        self.output_dir.set_value(self._settings.output_dir)

        self.whisper_model.setCurrentText(self._settings.whisper_model)
        self.use_ai.setChecked(self._settings.use_ai)
        self.ollama_url.setText(self._settings.ollama_url)

        models = analyze.installed_models(self._settings.ollama_url)
        self.ollama_model.addItems(models or [self._settings.ollama_model])
        self.ollama_model.setCurrentText(self._settings.ollama_model)

        self.dadata_token.setText(self._settings.dadata_token)

    def _save(self) -> None:
        manager = self._settings.manager
        manager.full_name = self.full_name.text().strip()
        manager.position = self.position.text().strip()
        manager.phone_1 = self.phone_1.text().strip()
        manager.phone_2 = self.phone_2.text().strip()
        manager.phone_3 = self.phone_3.text().strip()
        manager.email = self.email.text().strip()
        manager.site = self.site.text().strip()

        self._settings.kp_template = self.kp_template.value()
        self._settings.presentation_template = self.pres_template.value()
        self._settings.output_dir = self.output_dir.value()

        self._settings.whisper_model = self.whisper_model.currentText()
        self._settings.use_ai = self.use_ai.isChecked()
        self._settings.ollama_url = self.ollama_url.text().strip()
        self._settings.ollama_model = self.ollama_model.currentText().strip()
        self._settings.dadata_token = self.dadata_token.text().strip()

        self._settings.save()
        self.accept()
