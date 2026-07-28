# -*- coding: utf-8 -*-
"""Исправление типичных ошибок распознавания речи.

Whisper уверенно ошибается на названиях и терминах отрасли: «ЕСТП» слышится
как «ЕСПП», «Bidzaar» — как «Бизар», «Фанагория» — как «Фонагория».
Без нормализации эти ошибки попадают в КП и в CRM.
"""
from __future__ import annotations

import re

# Порядок важен: более длинные варианты идут первыми.
REPLACEMENTS: list[tuple[str, str]] = [
    # Название площадки
    (r"\bЕ\s?С\s?П\s?П\b", "ЕСТП"),
    (r"\bЕСПП\b", "ЕСТП"),
    (r"\bЕ\s?Т\s?П\b(?!\w)", "ЕСТП"),
    (r"\bэ\s?с\s?т\s?п\b", "ЕСТП"),
    # Конкурент
    (r"\bБидзаар\w*", "Bidzaar"),
    (r"\bБизаар\w*", "Bidzaar"),
    (r"\bБизар\w*", "Bidzaar"),
    (r"\bбизар\w*", "Bidzaar"),
    # Отраслевые термины
    (r"\bЭ\s?Ц\s?П\b", "ЭЦП"),
    (r"\bай\s?фрейм\b", "i-frame"),
    (r"\bайфрейм\b", "i-frame"),
    (r"\bтендор\w*", "тендер"),
    (r"\bзакупк[иа]х?\s+44\s*ФЗ", "закупках 44-ФЗ"),
]


def normalize(text: str, extra: list[tuple[str, str]] | None = None) -> str:
    """Приводит расшифровку к корректным написаниям."""
    result = text
    for pattern, replacement in REPLACEMENTS + list(extra or []):
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def company_aliases(short_name: str) -> list[tuple[str, str]]:
    """Правила для названия конкретной компании.

    Whisper часто искажает название клиента. Зная его из ЕГРЮЛ,
    исправляем близкие по звучанию варианты в расшифровке.
    """
    core = re.sub(r'^(ОАО|ООО|АО|ПАО|ЗАО|ИП)\s*', "", short_name, flags=re.IGNORECASE)
    core = core.strip('"«»\' ')
    if len(core) < 4:
        return []

    stem = core[:4]
    # Слово, начинающееся так же, но написанное иначе, — вероятная ошибка.
    pattern = rf"\b{re.escape(stem)}\w*"
    return [(pattern, core)]


def strip_timecodes(transcript: str) -> str:
    """Убирает метки времени — модели они только мешают."""
    return re.sub(r"^\[\d{2}:\d{2}\]\s*", "", transcript, flags=re.MULTILINE)
