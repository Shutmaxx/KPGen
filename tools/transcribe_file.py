# -*- coding: utf-8 -*-
"""Расшифровка отдельной записи (для проверки правок)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.services import normalize, transcribe

if len(sys.argv) < 2:
    print("Укажите путь к файлу записи")
    raise SystemExit(1)

source = Path(sys.argv[1])
output = Path(sys.argv[2]) if len(sys.argv) > 2 else source.with_suffix(".txt")

result = transcribe.transcribe(
    source, model_name="medium",
    progress=lambda p, t: print(f"{p:3d}% {t[:70]}", flush=True),
)

text = normalize.normalize(result.plain_text)
output.write_text(text, encoding="utf-8")
print("\nДлительность:", round(result.duration), "с")
print("Сохранено:", output)
print("-" * 60)
print(text)
