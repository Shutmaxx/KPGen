# -*- coding: utf-8 -*-
"""Снимает экраны всех шагов интерфейса для утверждения."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QTabWidget

from app.main import build_application
from app.services.dadata import Company
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog

OUT = Path(__file__).resolve().parents[1] / "_screenshots"
OUT.mkdir(exist_ok=True)

DEMO_COMPANY = Company(
    inn="2352002170",
    kpp="235201001",
    ogrn="1022304742074",
    name_short='ОАО "АПФ "ФАНАГОРИЯ"',
    name_full='ОТКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО "АГРОПРОМЫШЛЕННАЯ ФИРМА"ФАНАГОРИЯ"',
    address="Краснодарский край, Темрюкский р-н, поселок Сенной, ул Мира, д 49",
    region="Краснодарский край",
    okved="11.02",
    okved_name="",
    manager_name="Романишин Петр Евгеньевич",
    manager_post="Генеральный директор",
    status="ACTIVE",
)

DEMO_SUMMARY = (
    'Провёл разговор с Еленой из отдела снабжения ОАО "АПФ "ФАНАГОРИЯ" — '
    "закупки размещаются на площадке Bidzaar. От перехода отказались: в снабжении "
    "два человека, вести две площадки параллельно некому, плюс действует годовой "
    "договор с текущей площадкой. Договорились направить коммерческое предложение "
    "и вернуться к разговору после Нового года."
)


def grab(widget, name: str) -> None:
    widget.grab().save(str(OUT / f"{name}.png"))
    print("сохранён", name)


def main() -> int:
    application = build_application(sys.argv)
    window = MainWindow()
    window.resize(1000, 760)
    window.show()

    def shoot() -> None:
        # --- Шаг 1: загрузка записи ---
        window._go_to(0)
        window.drop_zone.show_file("CT4PUM5JT4000049.mp3")
        window.audio_info.setText(r"D:\Записи разговоров  ·  0.2 МБ")
        window.to_company_button.setEnabled(True)
        application.processEvents()
        grab(window, "1_zapis")

        # --- Шаг 2: компания ---
        window.audio_path = "CT4PUM5JT4000049.mp3"
        window._go_to(1)
        window.inn_edit.setText("2352002170")
        window._on_company_found(DEMO_COMPANY)
        window.logo_path = "fanagoria.png"
        window.logo_label.setText("fanagoria.png")
        application.processEvents()
        grab(window, "2_kompaniya")

        # --- Шаг 3: обработка ---
        window._go_to(2)
        window._on_progress(
            42, "Распознавание речи",
            "«У нас нет сотрудников, которые могут работать и там, и там»")
        application.processEvents()
        grab(window, "3_obrabotka")

        # --- Шаг 4: результат ---
        window._go_to(3)
        window.summary_edit.setPlainText(DEMO_SUMMARY)
        window.summary_badge.set_kind("success")
        window.summary_badge.setText("Составлено ИИ · qwen2.5:7b")
        window.files_path_label.setText(
            r"C:\Users\Максим\Documents\KPGEN ESTP\ОАО АПФ ФАНАГОРИЯ_2026-07-28")
        window.copy_status.set_kind("success")
        window.copy_status.setText("Скопировано — можно вставлять в CRM")
        application.processEvents()
        grab(window, "4_rezultat")

        # --- Настройки: все вкладки ---
        dialog = SettingsDialog(window.settings, window)
        dialog.resize(680, 580)
        dialog.show()
        application.processEvents()

        tabs = dialog.findChild(QTabWidget)
        for index, name in enumerate(("5_nastroyki_podpis",
                                      "6_nastroyki_shablony",
                                      "7_nastroyki_ii")):
            if tabs is not None:
                tabs.setCurrentIndex(index)
            application.processEvents()
            grab(dialog, name)

        dialog.close()
        application.quit()

    QTimer.singleShot(600, shoot)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
