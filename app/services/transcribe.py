# -*- coding: utf-8 -*-
"""Распознавание речи из аудиозаписи разговора (faster-whisper, локально)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

SUPPORTED_SUFFIXES = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".wma", ".flac", ".mp4"}

ProgressCallback = Callable[[int, str], None]


class TranscriptionError(Exception):
    """Ошибка распознавания с понятным пользователю описанием."""


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str

    @property
    def timecode(self) -> str:
        return f"[{int(self.start) // 60:02d}:{int(self.start) % 60:02d}]"


@dataclass
class TranscriptResult:
    segments: list[TranscriptSegment]
    duration: float
    language: str

    @property
    def plain_text(self) -> str:
        return "\n".join(segment.text for segment in self.segments)

    @property
    def text_with_timecodes(self) -> str:
        return "\n".join(f"{s.timecode} {s.text}" for s in self.segments)


_model_cache: dict[str, object] = {}


def _load_model(model_name: str):
    """Загружает модель один раз за сессию — повторная загрузка занимает минуту."""
    if model_name in _model_cache:
        return _model_cache[model_name]
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError(
            "Не установлен компонент распознавания речи (faster-whisper). "
            "Переустановите программу."
        ) from exc

    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
    except Exception as exc:
        raise TranscriptionError(
            f"Не удалось загрузить модель распознавания «{model_name}». "
            f"При первом запуске требуется интернет для её скачивания. "
            f"Техническая причина: {exc}"
        ) from exc

    _model_cache[model_name] = model
    return model


def transcribe(
    audio_path: str | Path,
    model_name: str = "medium",
    progress: ProgressCallback | None = None,
) -> TranscriptResult:
    """Расшифровывает запись разговора.

    progress получает процент выполнения и текст последнего распознанного куска.
    """
    path = Path(audio_path)
    if not path.exists():
        raise TranscriptionError(f"Файл не найден: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise TranscriptionError(
            f"Формат «{path.suffix}» не поддерживается. Допустимые форматы: {supported}"
        )
    if path.stat().st_size == 0:
        raise TranscriptionError(f"Файл пустой: {path.name}")

    if progress:
        progress(0, "Загрузка модели распознавания…")
    model = _load_model(model_name)

    try:
        segments_iter, info = model.transcribe(
            str(path),
            language="ru",
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False,
        )
    except Exception as exc:
        raise TranscriptionError(
            f"Не удалось прочитать аудиозапись «{path.name}». "
            f"Возможно, файл повреждён. Техническая причина: {exc}"
        ) from exc

    duration = float(getattr(info, "duration", 0.0) or 0.0)
    segments: list[TranscriptSegment] = []

    for segment in segments_iter:
        text = (segment.text or "").strip()
        if not text:
            continue
        segments.append(TranscriptSegment(segment.start, segment.end, text))
        if progress and duration > 0:
            percent = min(99, int(segment.end / duration * 100))
            progress(percent, text)

    if not segments:
        raise TranscriptionError(
            "В записи не распознана речь. Проверьте, что файл содержит разговор."
        )

    if progress:
        progress(100, "Распознавание завершено")

    return TranscriptResult(
        segments=segments,
        duration=duration,
        language=str(getattr(info, "language", "ru")),
    )
