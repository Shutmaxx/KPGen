# -*- coding: utf-8 -*-
"""Фоновая обработка разговора, чтобы окно оставалось отзывчивым."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from ..services import analyze, docgen, normalize, transcribe
from ..services.dadata import Company
from ..services.settings import Settings


@dataclass
class ProcessRequest:
    audio_path: str
    company: Company
    logo_path: str | None
    settings: Settings


@dataclass
class ProcessResult:
    files: docgen.GeneratedFiles
    analysis: analyze.CallAnalysis
    transcript: str
    duration: float


class ProcessWorker(QObject):
    """Выполняет весь конвейер: распознавание → анализ → документы."""

    # процент, заголовок шага, пояснение
    progress = Signal(int, str, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, request: ProcessRequest) -> None:
        super().__init__()
        self._request = request
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        request = self._request
        settings = request.settings

        try:
            # --- 1. Распознавание речи (0–55 %) ---
            def on_transcribe(percent: int, text: str) -> None:
                if self._cancelled:
                    return
                self.progress.emit(
                    int(percent * 0.55), "Распознавание речи", text[:90])

            self.progress.emit(1, "Распознавание речи",
                               "Подготовка модели, это может занять минуту…")
            result = transcribe.transcribe(
                request.audio_path,
                model_name=settings.whisper_model,
                progress=on_transcribe,
            )
            if self._cancelled:
                return

            # --- 2. Нормализация (55–60 %) ---
            self.progress.emit(57, "Обработка текста",
                               "Исправляю ошибки распознавания…")
            text = normalize.normalize(
                result.plain_text,
                normalize.company_aliases(request.company.display_name),
            )

            # --- 3. Анализ (60–90 %) ---
            def on_analyze(percent: int, message: str) -> None:
                if self._cancelled:
                    return
                self.progress.emit(60 + int(percent * 0.30), "Анализ разговора", message)

            analysis = analyze.analyze_call(
                text, request.company,
                use_ai=settings.use_ai,
                base_url=settings.ollama_url,
                model=settings.ollama_model,
                progress=on_analyze,
            )
            if self._cancelled:
                return

            # --- 4. Документы (90–100 %) ---
            self.progress.emit(92, "Сборка документов",
                               "Формирую КП и презентацию…")
            files = docgen.generate_all(
                request.company, analysis, settings.manager,
                settings.kp_template, settings.presentation_template,
                settings.output_dir,
                logo_path=request.logo_path,
                transcript=result.text_with_timecodes,
            )

            self.progress.emit(100, "Готово", "Документы сформированы")
            self.finished.emit(ProcessResult(
                files=files,
                analysis=analysis,
                transcript=text,
                duration=result.duration,
            ))

        except (transcribe.TranscriptionError,
                docgen.DocumentGenerationError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # непредвиденное — показываем понятно
            self.failed.emit(
                f"Непредвиденная ошибка при обработке: {exc}"
            )


class ProcessController(QObject):
    """Владеет потоком обработки и пробрасывает сигналы в интерфейс."""

    progress = Signal(int, str, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: ProcessWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self, request: ProcessRequest) -> None:
        if self.is_running:
            return

        self._thread = QThread()
        self._worker = ProcessWorker(request)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)

        self._thread.start()

    def cancel(self) -> None:
        if self._worker:
            self._worker.cancel()

    def _cleanup(self) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)
        self._thread = None
        self._worker = None

    def _on_finished(self, result: ProcessResult) -> None:
        self._cleanup()
        self.finished.emit(result)

    def _on_failed(self, message: str) -> None:
        self._cleanup()
        self.failed.emit(message)
