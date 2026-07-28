# -*- coding: utf-8 -*-
"""Сквозная проверка конвейера на готовой расшифровке (без GUI)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.services import analyze, dadata, docgen, normalize
from app.services.settings import Settings

ROOT = Path(__file__).resolve().parents[2]

settings = Settings()
settings.output_dir = str(Path(__file__).resolve().parents[1] / "_test_output")

print("1) Поиск компании по ИНН…")
company = dadata.find_by_inn("2352002170", settings.dadata_token)
print("   ", company.display_name, "|", company.region, "|", company.industry_phrase())

print("2) Нормализация расшифровки…")
raw = (ROOT / "transcript_fanagoria.txt").read_text(encoding="utf-8")
transcript = normalize.normalize(
    normalize.strip_timecodes(raw),
    normalize.company_aliases(company.display_name),
)

print("3) Анализ разговора (Qwen)…")
t0 = time.time()
result = analyze.analyze_call(
    transcript, company,
    use_ai=settings.use_ai,
    base_url=settings.ollama_url,
    model=settings.ollama_model,
    progress=lambda p, m: print(f"     {p:3d}% {m}"),
)
print(f"   готово за {time.time() - t0:.0f} c | ИИ: {result.used_ai}")
print("   ВЫЖИМКА:", result.summary)
print("   предложений:", len(analyze.split_sentences(result.summary)))
if result.notes:
    print("   замечания:", result.notes)

print("4) Сборка документов…")
files = docgen.generate_all(
    company, result, settings.manager,
    settings.kp_template, settings.presentation_template,
    settings.output_dir, logo_path=None, transcript=transcript,
)
print("   КП         :", files.kp_path)
print("   Презентация:", files.presentation_path)
print("   Выжимка    :", files.summary_path)

print("5) Контроль подстановки…")
from docx import Document
doc = Document(str(files.kp_path))
left = [p.text for p in doc.paragraphs if "{{" in p.text]
print("   незаполненных плейсхолдеров:", len(left), left[:3])
for index in (2, 3, 18):
    print(f"   [{index}] {doc.paragraphs[index].text[:110]}")

from pptx import Presentation
pres = Presentation(str(files.presentation_path))
slide2 = list(pres.slides)[1]
texts = [s.text_frame.text.strip() for s in slide2.shapes
         if s.has_text_frame and s.text_frame.text.strip()]
print("   слайд 2:", texts)
