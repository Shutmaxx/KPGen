# -*- coding: utf-8 -*-
"""Главное окно KPGEN ESTP."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QProgressBar,
                               QPushButton, QSizePolicy, QStackedWidget,
                               QTextEdit, QVBoxLayout, QWidget)

from ..services import analyze
from ..services.dadata import Company, DaDataError, find_by_inn, validate_inn
from ..services.settings import Settings
from ..services.transcribe import SUPPORTED_SUFFIXES
from . import theme
from .settings_dialog import SettingsDialog
from .widgets import Card, DropZone, InfoRow, Separator, StatusBadge, StepIndicator
from .worker import ProcessController, ProcessRequest, ProcessResult

STEPS = ["Запись", "Компания", "Обработка", "Результат"]


class CompanyLookupThread(QThread):
    """Поиск компании в отдельном потоке, чтобы окно не подвисало."""

    found = Signal(object)
    failed = Signal(str)

    def __init__(self, inn: str, token: str) -> None:
        super().__init__()
        self._inn = inn
        self._token = token

    def run(self) -> None:
        try:
            self.found.emit(find_by_inn(self._inn, self._token))
        except DaDataError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Не удалось получить данные компании: {exc}")


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("KPGEN ESTP — подготовка КП по записи разговора")
        self.setMinimumSize(940, 720)
        self.setStyleSheet(theme.STYLESHEET)

        self.settings = Settings.load()
        self.audio_path: str | None = None
        self.company: Company | None = None
        self.logo_path: str | None = None
        self.result: ProcessResult | None = None

        self._lookup_thread: CompanyLookupThread | None = None
        self.controller = ProcessController(self)
        self.controller.progress.connect(self._on_progress)
        self.controller.finished.connect(self._on_finished)
        self.controller.failed.connect(self._on_failed)

        self._build_ui()
        QTimer.singleShot(400, self._check_ai_status)

    # ==================================================================
    # Построение интерфейса
    # ==================================================================
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        root.addLayout(self._build_header())

        self.steps = StepIndicator(STEPS)
        root.addWidget(self.steps)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_upload_page())
        self.pages.addWidget(self._build_company_page())
        self.pages.addWidget(self._build_process_page())
        self.pages.addWidget(self._build_result_page())
        root.addWidget(self.pages, 1)

        self._go_to(0)

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("KPGEN ESTP")
        title.setObjectName("h1")
        subtitle = QLabel("Коммерческое предложение и презентация по записи разговора")
        subtitle.setObjectName("muted")
        titles.addWidget(title)
        titles.addWidget(subtitle)

        self.ai_badge = StatusBadge("Проверяю ИИ…")

        settings_button = QPushButton("Настройки")
        settings_button.clicked.connect(self._open_settings)

        layout.addLayout(titles)
        layout.addStretch()
        layout.addWidget(self.ai_badge)
        layout.addSpacing(12)
        layout.addWidget(settings_button)
        return layout

    # --- шаг 1: запись -------------------------------------------------
    def _build_upload_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = Card()
        heading = QLabel("Шаг 1. Загрузите запись разговора")
        heading.setObjectName("h2")
        card.body.addWidget(heading)

        note = QLabel("Файл обрабатывается на этом компьютере "
                      "и никуда не передаётся.")
        note.setObjectName("muted")
        card.body.addWidget(note)

        self.drop_zone = DropZone()
        self.drop_zone.file_selected.connect(self._set_audio)
        self.drop_zone.clicked.connect(self._choose_audio)
        card.body.addWidget(self.drop_zone)

        self.audio_info = QLabel("")
        self.audio_info.setObjectName("dim")
        card.body.addWidget(self.audio_info)

        layout.addWidget(card)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.to_company_button = QPushButton("Далее")
        self.to_company_button.setObjectName("primary")
        self.to_company_button.setEnabled(False)
        self.to_company_button.clicked.connect(lambda: self._go_to(1))
        buttons.addWidget(self.to_company_button)
        layout.addLayout(buttons)
        return page

    # --- шаг 2: компания ------------------------------------------------
    def _build_company_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = Card()
        heading = QLabel("Шаг 2. Для какой компании готовим документы?")
        heading.setObjectName("h2")
        card.body.addWidget(heading)

        hint = QLabel("Введите ИНН — данные подтянутся из реестра.")
        hint.setObjectName("muted")
        card.body.addWidget(hint)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self.inn_edit = QLineEdit()
        self.inn_edit.setObjectName("inn")
        self.inn_edit.setPlaceholderText("ИНН: 10 или 12 цифр")
        self.inn_edit.setMaxLength(12)
        # Высота задаётся явно: крупный шрифт с отступами иначе обрезается.
        self.inn_edit.setMinimumHeight(54)
        self.inn_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.inn_edit.returnPressed.connect(self._lookup_company)

        self.lookup_button = QPushButton("Найти")
        self.lookup_button.setObjectName("primary")
        self.lookup_button.setMinimumHeight(54)
        self.lookup_button.setMinimumWidth(130)
        self.lookup_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.lookup_button.clicked.connect(self._lookup_company)
        search_row.addWidget(self.inn_edit, 1)
        search_row.addWidget(self.lookup_button)
        card.body.addLayout(search_row)

        self.lookup_status = StatusBadge("")
        card.body.addWidget(self.lookup_status)

        card.body.addWidget(Separator())

        self.company_rows = {
            "name": InfoRow("Наименование"),
            "inn": InfoRow("ИНН / КПП"),
            "address": InfoRow("Адрес"),
            "okved": InfoRow("Вид деятельности"),
            "head": InfoRow("Руководитель"),
            "status": InfoRow("Статус"),
        }
        for row in self.company_rows.values():
            card.body.addWidget(row)

        layout.addWidget(card)

        logo_card = Card()
        logo_heading = QLabel("Логотип клиента (необязательно)")
        logo_heading.setObjectName("h2")
        logo_card.body.addWidget(logo_heading)
        logo_note = QLabel("Ставится на титульный слайд презентации. "
                           "Если не выбрать — место останется пустым.")
        logo_note.setObjectName("muted")
        logo_note.setWordWrap(True)
        logo_card.body.addWidget(logo_note)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        self.logo_label = QLabel("Файл не выбран")
        self.logo_label.setObjectName("dim")
        choose_logo = QPushButton("Выбрать логотип…")
        choose_logo.clicked.connect(self._choose_logo)
        clear_logo = QPushButton("Убрать")
        clear_logo.setObjectName("ghost")
        clear_logo.clicked.connect(self._clear_logo)
        logo_row.addWidget(choose_logo)
        logo_row.addWidget(clear_logo)
        logo_row.addWidget(self.logo_label, 1)
        logo_card.body.addLayout(logo_row)

        layout.addWidget(logo_card)
        layout.addStretch()

        buttons = QHBoxLayout()
        back = QPushButton("Назад")
        back.setObjectName("ghost")
        back.clicked.connect(lambda: self._go_to(0))
        buttons.addWidget(back)
        buttons.addStretch()
        self.start_button = QPushButton("Сформировать документы")
        self.start_button.setObjectName("primary")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._start_processing)
        buttons.addWidget(self.start_button)
        layout.addLayout(buttons)
        return page

    # --- шаг 3: обработка -----------------------------------------------
    def _build_process_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = Card(padding=28)
        self.process_title = QLabel("Обработка записи")
        self.process_title.setObjectName("h2")
        card.body.addWidget(self.process_title)

        self.process_detail = QLabel("Подготовка…")
        self.process_detail.setObjectName("muted")
        self.process_detail.setWordWrap(True)
        self.process_detail.setMinimumHeight(44)
        self.process_detail.setAlignment(Qt.AlignTop)
        card.body.addWidget(self.process_detail)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        card.body.addWidget(self.progress)

        self.process_percent = QLabel("0 %")
        self.process_percent.setObjectName("dim")
        card.body.addWidget(self.process_percent)

        card.body.addWidget(Separator())
        tip = QLabel("Распознавание идёт локально: 10 минут записи "
                     "обрабатываются примерно 5–7 минут.")
        tip.setObjectName("dim")
        tip.setWordWrap(True)
        card.body.addWidget(tip)

        layout.addWidget(card)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = QPushButton("Отменить")
        self.cancel_button.setObjectName("ghost")
        self.cancel_button.clicked.connect(self._cancel_processing)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        return page

    # --- шаг 4: результат ------------------------------------------------
    def _build_result_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        summary_card = Card()
        row = QHBoxLayout()
        heading = QLabel("Итог звонка для CRM")
        heading.setObjectName("h2")
        row.addWidget(heading)
        row.addStretch()
        self.summary_badge = StatusBadge("")
        row.addWidget(self.summary_badge)
        summary_card.body.addLayout(row)

        note = QLabel("Текст можно поправить перед копированием.")
        note.setObjectName("muted")
        summary_card.body.addWidget(note)

        self.summary_edit = QTextEdit()
        self.summary_edit.setMinimumHeight(130)
        summary_card.body.addWidget(self.summary_edit)

        copy_row = QHBoxLayout()
        self.copy_button = QPushButton("Копировать в буфер обмена")
        self.copy_button.setObjectName("primary")
        self.copy_button.clicked.connect(self._copy_summary)
        self.copy_status = StatusBadge("")
        copy_row.addWidget(self.copy_button)
        copy_row.addWidget(self.copy_status, 1)
        summary_card.body.addLayout(copy_row)

        layout.addWidget(summary_card)

        files_card = Card()
        files_heading = QLabel("Готовые файлы")
        files_heading.setObjectName("h2")
        files_card.body.addWidget(files_heading)

        self.files_path_label = QLabel("")
        self.files_path_label.setObjectName("dim")
        self.files_path_label.setWordWrap(True)
        self.files_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        files_card.body.addWidget(self.files_path_label)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)
        self.open_kp_button = QPushButton("Открыть КП")
        self.open_kp_button.clicked.connect(
            lambda: self._open_path(self.result.files.kp_path if self.result else None))
        self.open_pres_button = QPushButton("Открыть презентацию")
        self.open_pres_button.clicked.connect(
            lambda: self._open_path(
                self.result.files.presentation_path if self.result else None))
        self.open_folder_button = QPushButton("Открыть папку")
        self.open_folder_button.clicked.connect(
            lambda: self._open_path(
                self.result.files.kp_path.parent if self.result else None))
        buttons_row.addWidget(self.open_kp_button)
        buttons_row.addWidget(self.open_pres_button)
        buttons_row.addWidget(self.open_folder_button)
        buttons_row.addStretch()
        files_card.body.addLayout(buttons_row)

        layout.addWidget(files_card)

        self.notes_label = QLabel("")
        self.notes_label.setObjectName("muted")
        self.notes_label.setWordWrap(True)
        layout.addWidget(self.notes_label)

        layout.addStretch()

        buttons = QHBoxLayout()
        restart = QPushButton("Обработать следующую запись")
        restart.clicked.connect(self._reset)
        buttons.addWidget(restart)
        buttons.addStretch()
        layout.addLayout(buttons)
        return page

    # ==================================================================
    # Логика шагов
    # ==================================================================
    def _go_to(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.steps.set_active(index)

    def _check_ai_status(self) -> None:
        if not self.settings.use_ai:
            self.ai_badge.set_kind("muted")
            self.ai_badge.setText("Режим без ИИ")
            return
        if not analyze.ollama_available(self.settings.ollama_url):
            self.ai_badge.set_kind("warning")
            self.ai_badge.setText("Ollama не запущена — тексты по правилам")
            return
        if self.settings.ollama_model not in analyze.installed_models(
                self.settings.ollama_url):
            self.ai_badge.set_kind("warning")
            self.ai_badge.setText(f"Нет модели {self.settings.ollama_model}")
            return
        self.ai_badge.set_kind("success")
        self.ai_badge.setText(f"ИИ готов · {self.settings.ollama_model}")

    # --- шаг 1 -----------------------------------------------------------
    def _choose_audio(self) -> None:
        patterns = " ".join(f"*{s}" for s in sorted(SUPPORTED_SUFFIXES))
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите запись разговора", str(Path.home()),
            f"Аудиозаписи ({patterns});;Все файлы (*.*)")
        if path:
            self._set_audio(path)

    def _set_audio(self, path: str) -> None:
        file = Path(path)
        if not file.exists():
            self._error("Файл не найден", f"Не удалось открыть файл: {path}")
            return

        self.audio_path = path
        self.drop_zone.show_file(path)
        size_mb = file.stat().st_size / 1024 / 1024
        self.audio_info.setText(f"{file.parent}  ·  {size_mb:.1f} МБ")
        self.to_company_button.setEnabled(True)

    # --- шаг 2 -----------------------------------------------------------
    def _lookup_company(self) -> None:
        raw = self.inn_edit.text().strip()
        try:
            validate_inn(raw)
        except DaDataError as exc:
            self.lookup_status.set_kind("danger")
            self.lookup_status.setText(str(exc))
            return

        self.lookup_button.setEnabled(False)
        self.lookup_status.set_kind("muted")
        self.lookup_status.setText("Ищу компанию в реестре…")

        self._lookup_thread = CompanyLookupThread(raw, self.settings.dadata_token)
        self._lookup_thread.found.connect(self._on_company_found)
        self._lookup_thread.failed.connect(self._on_company_failed)
        self._lookup_thread.finished.connect(
            lambda: self.lookup_button.setEnabled(True))
        self._lookup_thread.start()

    def _on_company_found(self, company: Company) -> None:
        self.company = company
        self.company_rows["name"].set_value(company.name_full or company.display_name)
        self.company_rows["inn"].set_value(
            f"{company.inn} / {company.kpp}" if company.kpp else company.inn)
        self.company_rows["address"].set_value(company.address)
        self.company_rows["okved"].set_value(
            f"{company.okved} — {company.industry_phrase()}"
            if company.okved else company.industry_phrase())
        self.company_rows["head"].set_value(
            f"{company.manager_name}, {company.manager_post}"
            if company.manager_name else "—")

        if company.is_active:
            self.company_rows["status"].set_value("Действующая")
            self.lookup_status.set_kind("success")
            self.lookup_status.setText("Компания найдена")
        else:
            self.company_rows["status"].set_value(f"Внимание: {company.status}")
            self.lookup_status.set_kind("warning")
            self.lookup_status.setText(
                "Компания найдена, но не является действующей")

        self.start_button.setEnabled(True)

    def _on_company_failed(self, message: str) -> None:
        self.company = None
        self.start_button.setEnabled(False)
        self.lookup_status.set_kind("danger")
        self.lookup_status.setText(message)

    def _choose_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите логотип клиента", str(Path.home()),
            "Изображения (*.png *.jpg *.jpeg *.gif *.bmp)")
        if path:
            self.logo_path = path
            self.logo_label.setText(Path(path).name)

    def _clear_logo(self) -> None:
        self.logo_path = None
        self.logo_label.setText("Файл не выбран")

    # --- шаг 3 -----------------------------------------------------------
    def _start_processing(self) -> None:
        if not self.audio_path or not self.company:
            return

        self.progress.setValue(0)
        self.process_title.setText("Обработка записи")
        self.process_detail.setText("Подготовка…")
        self.process_percent.setText("0 %")
        self.cancel_button.setEnabled(True)
        self._go_to(2)

        self.controller.start(ProcessRequest(
            audio_path=self.audio_path,
            company=self.company,
            logo_path=self.logo_path,
            settings=self.settings,
        ))

    def _cancel_processing(self) -> None:
        self.controller.cancel()
        self.cancel_button.setEnabled(False)
        self.process_detail.setText("Отмена после текущего шага…")

    def _on_progress(self, percent: int, title: str, detail: str) -> None:
        self.progress.setValue(percent)
        self.process_title.setText(title)
        self.process_detail.setText(detail)
        self.process_percent.setText(f"{percent} %")

    def _on_finished(self, result: ProcessResult) -> None:
        self.result = result
        self.summary_edit.setPlainText(result.analysis.summary)

        if result.analysis.used_ai:
            self.summary_badge.set_kind("success")
            self.summary_badge.setText(f"Составлено ИИ · {self.settings.ollama_model}")
        else:
            self.summary_badge.set_kind("warning")
            self.summary_badge.setText("Составлено по правилам, без ИИ")

        self.files_path_label.setText(str(result.files.kp_path.parent))
        self.notes_label.setText(
            "  ·  ".join(result.analysis.notes) if result.analysis.notes else "")
        self.copy_status.setText("")
        self._go_to(3)

    def _on_failed(self, message: str) -> None:
        self._go_to(1)
        self._error("Не удалось обработать запись", message)

    # --- шаг 4 -----------------------------------------------------------
    def _copy_summary(self) -> None:
        text = self.summary_edit.toPlainText().strip()
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        self.copy_status.set_kind("success")
        self.copy_status.setText("Скопировано — можно вставлять в CRM")
        QTimer.singleShot(4000, lambda: self.copy_status.setText(""))

    def _open_path(self, path: Path | None) -> None:
        if path is None or not Path(path).exists():
            self._error("Файл недоступен",
                        "Файл не найден. Возможно, он был перемещён или удалён.")
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except OSError as exc:
            self._error("Не удалось открыть файл", str(exc))

    def _reset(self) -> None:
        self.audio_path = None
        self.company = None
        self.logo_path = None
        self.result = None

        self.drop_zone.show_file("Перетащите запись разговора")
        self.audio_info.setText("")
        self.to_company_button.setEnabled(False)
        self.inn_edit.clear()
        self.lookup_status.setText("")
        for row in self.company_rows.values():
            row.set_value("—")
        self.start_button.setEnabled(False)
        self._clear_logo()
        self._go_to(0)

    # ------------------------------------------------------------------
    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = Settings.load()
            self._check_ai_status()

    def _error(self, title: str, message: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(message)
        box.setStyleSheet(theme.STYLESHEET)
        box.exec()

    def closeEvent(self, event) -> None:
        if self.controller.is_running:
            answer = QMessageBox.question(
                self, "Обработка не завершена",
                "Идёт обработка записи. Закрыть программу?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer == QMessageBox.No:
                event.ignore()
                return
            self.controller.cancel()
        event.accept()
