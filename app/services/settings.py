# -*- coding: utf-8 -*-
"""Настройки приложения: хранение и значения по умолчанию."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "KPGEN ESTP"


def app_data_dir() -> Path:
    """Папка настроек: %APPDATA%\\KPGEN ESTP (кроссплатформенно)."""
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME.lower().replace(' ', '-')}"


def default_output_dir() -> Path:
    """Папка результатов: Документы\\KPGEN ESTP."""
    docs = Path.home() / "Documents"
    if not docs.exists():
        docs = Path.home()
    return docs / APP_NAME


def bundled_templates_dir() -> Path:
    """Шаблоны, поставляемые вместе с программой."""
    return Path(__file__).resolve().parents[2] / "templates"


@dataclass
class Manager:
    """Подпись менеджера в КП и на последнем слайде."""
    full_name: str = "Грищенко Максим Юрьевич"
    position: str = "Менеджер по работе с клиентами"
    phone_1: str = "+7-965-764-77-91"
    phone_2: str = "+7-495-212-14-55 (доб. 162)"
    phone_3: str = "+7 (800) 555-20-83 (доб. 162) — звонок бесплатный"
    email: str = "m.grishenko@estp.ru"
    site: str = "estp.ru"


@dataclass
class Settings:
    manager: Manager = field(default_factory=Manager)

    dadata_token: str = "96c3d3809f1d1d92e157cdca9d9a44ed610e0109"

    whisper_model: str = "medium"
    ollama_model: str = "qwen2.5:7b"
    ollama_url: str = "http://localhost:11434"
    use_ai: bool = True

    kp_template: str = ""
    presentation_template: str = ""
    output_dir: str = ""

    def __post_init__(self) -> None:
        if not self.kp_template:
            self.kp_template = str(bundled_templates_dir() / "kp_template.docx")
        if not self.presentation_template:
            self.presentation_template = str(
                bundled_templates_dir() / "presentation_template.pptx")
        if not self.output_dir:
            self.output_dir = str(default_output_dir())

    # --- сериализация -------------------------------------------------
    @classmethod
    def load(cls) -> "Settings":
        path = app_data_dir() / "settings.json"
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Повреждённый файл настроек не должен мешать запуску.
            return cls()
        manager = Manager(**raw.pop("manager", {}))
        known = {f for f in cls.__dataclass_fields__ if f != "manager"}
        return cls(manager=manager, **{k: v for k, v in raw.items() if k in known})

    def save(self) -> Path:
        directory = app_data_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "settings.json"
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path
