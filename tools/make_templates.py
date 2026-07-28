# -*- coding: utf-8 -*-
"""Готовит шаблоны с плейсхолдерами из рабочих файлов менеджера.

Запускается один раз (и повторно, если менеджер изменит исходные файлы).
Оформление, бланк, логотипы и стили остаются нетронутыми — меняется
только текст в тех местах, которые зависят от клиента и разговора.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from docx import Document

from app.services.docx_utils import set_paragraph_text, replace_in_paragraph

ROOT = Path(__file__).resolve().parents[2]          # D:\Петров
PKG = Path(__file__).resolve().parents[1]           # kpgen
TEMPLATES = PKG / "templates"

SRC_KP = ROOT / "КП_Фанагория_обновленное.docx"
SRC_PRES = ROOT / "Презентация_для_Акрон_Холдинг.pptx"
DST_KP = TEMPLATES / "kp_template.docx"
DST_PRES = TEMPLATES / "presentation_template.pptx"

# Абзац -> плейсхолдер. Индексы выверены по исходному файлу.
PARAGRAPH_PLACEHOLDERS = {
    2: "{{ОПИСАНИЕ_КОМПАНИИ}}",
    3: "{{КОНТЕКСТ_РАЗГОВОРА}}",
    18: "{{ИТОГ_РАЗГОВОРА}}",
    20: "{{МЕНЕДЖЕР_ФИО}}",
    21: "{{МЕНЕДЖЕР_ДОЛЖНОСТЬ}}",
    22: "{{МЕНЕДЖЕР_ТЕЛЕФОН_1}}",
    23: "{{МЕНЕДЖЕР_ТЕЛЕФОН_2}}",
    24: "{{МЕНЕДЖЕР_ТЕЛЕФОН_3}}",
    25: "{{МЕНЕДЖЕР_EMAIL}}",
    26: "{{МЕНЕДЖЕР_САЙТ}}",
}

# Точечные замены упоминаний конкретного клиента в статичных блоках.
# Абзац 18 сюда не входит: он целиком заменяется на {{ИТОГ_РАЗГОВОРА}}.
INLINE_REPLACEMENTS = [
    ("корпоративный портал «Фанагории»", "корпоративный портал {{КОМПАНИЯ_КРАТКО}}"),
]


def build_kp_template() -> None:
    if not SRC_KP.exists():
        raise FileNotFoundError(f"Не найден исходный файл КП: {SRC_KP}")
    TEMPLATES.mkdir(parents=True, exist_ok=True)

    doc = Document(str(SRC_KP))
    paragraphs = doc.paragraphs

    for index, placeholder in PARAGRAPH_PLACEHOLDERS.items():
        if index >= len(paragraphs):
            raise IndexError(f"В шаблоне КП нет абзаца №{index}")
        set_paragraph_text(paragraphs[index], placeholder)

    for old, new in INLINE_REPLACEMENTS:
        for paragraph in paragraphs:
            replace_in_paragraph(paragraph, old, new)

    doc.save(str(DST_KP))
    print(f"КП-шаблон: {DST_KP}")


def build_presentation_template() -> None:
    if not SRC_PRES.exists():
        raise FileNotFoundError(f"Не найден исходный файл презентации: {SRC_PRES}")
    TEMPLATES.mkdir(parents=True, exist_ok=True)
    # Презентация правится в приложении по тексту слайда,
    # поэтому шаблон копируется как есть — дизайн сохраняется полностью.
    shutil.copy2(SRC_PRES, DST_PRES)
    print(f"Шаблон презентации: {DST_PRES}")


def main() -> None:
    build_kp_template()
    build_presentation_template()

    # Контроль: плейсхолдеры должны присутствовать в готовом шаблоне.
    doc = Document(str(DST_KP))
    text = "\n".join(p.text for p in doc.paragraphs)
    missing = [ph for ph in PARAGRAPH_PLACEHOLDERS.values() if ph not in text]
    missing += [new for _, new in INLINE_REPLACEMENTS if new not in text]
    if missing:
        print("ВНИМАНИЕ, не найдены плейсхолдеры:", ", ".join(missing))
    else:
        print("Все плейсхолдеры на месте.")


if __name__ == "__main__":
    main()
