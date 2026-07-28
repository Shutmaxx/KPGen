# -*- coding: utf-8 -*-
"""Поиск сведений о компании по ИНН через DaData."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

FIND_BY_ID_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"

# Отрасль по первым цифрам ОКВЭД — для нейтрального описания в КП.
OKVED_SECTIONS: list[tuple[str, str]] = [
    ("01", "сельскохозяйственное предприятие"),
    ("02", "предприятие лесного хозяйства"),
    ("03", "рыбохозяйственное предприятие"),
    ("05", "предприятие добывающей отрасли"),
    ("06", "предприятие добывающей отрасли"),
    ("07", "предприятие добывающей отрасли"),
    ("08", "предприятие добывающей отрасли"),
    ("10", "предприятие пищевой промышленности"),
    ("11", "предприятие пищевой промышленности"),
    ("13", "предприятие лёгкой промышленности"),
    ("14", "предприятие лёгкой промышленности"),
    ("16", "деревообрабатывающее предприятие"),
    ("17", "предприятие целлюлозно-бумажной промышленности"),
    ("19", "предприятие нефтепереработки"),
    ("20", "предприятие химической промышленности"),
    ("21", "фармацевтическое предприятие"),
    ("22", "предприятие по производству резиновых и пластмассовых изделий"),
    ("23", "предприятие по производству строительных материалов"),
    ("24", "металлургическое предприятие"),
    ("25", "предприятие металлообработки"),
    ("26", "предприятие электронной промышленности"),
    ("27", "предприятие электротехнической промышленности"),
    ("28", "машиностроительное предприятие"),
    ("29", "предприятие автомобильной промышленности"),
    ("30", "предприятие транспортного машиностроения"),
    ("35", "энергетическое предприятие"),
    ("36", "предприятие водоснабжения"),
    ("37", "предприятие водоотведения"),
    ("38", "предприятие в сфере обращения с отходами"),
    ("41", "строительная компания"),
    ("42", "предприятие инфраструктурного строительства"),
    ("43", "строительная компания"),
    ("45", "предприятие автомобильной торговли"),
    ("46", "предприятие оптовой торговли"),
    ("47", "предприятие розничной торговли"),
    ("49", "транспортное предприятие"),
    ("50", "судоходная компания"),
    ("51", "авиационное предприятие"),
    ("52", "предприятие транспортной логистики"),
    ("53", "почтовое предприятие"),
    ("55", "предприятие гостиничного бизнеса"),
    ("56", "предприятие общественного питания"),
    ("58", "издательская компания"),
    ("59", "предприятие в сфере производства медиаконтента"),
    ("61", "телекоммуникационная компания"),
    ("62", "ИТ-компания"),
    ("63", "компания в сфере информационных услуг"),
    ("64", "финансовая организация"),
    ("65", "страховая организация"),
    ("68", "компания в сфере управления недвижимостью"),
    ("71", "проектная организация"),
    ("72", "научно-исследовательская организация"),
    ("84", "государственное учреждение"),
    ("85", "образовательное учреждение"),
    ("86", "медицинское учреждение"),
    ("87", "учреждение социального обслуживания"),
    ("90", "учреждение культуры"),
    ("91", "учреждение культуры"),
]


class DaDataError(Exception):
    """Ошибка обращения к сервису с понятным пользователю текстом."""


@dataclass
class Company:
    inn: str
    kpp: str
    ogrn: str
    name_short: str
    name_full: str
    address: str
    region: str
    okved: str
    okved_name: str
    manager_name: str
    manager_post: str
    status: str

    @property
    def is_active(self) -> bool:
        return self.status.upper() == "ACTIVE"

    @property
    def display_name(self) -> str:
        return self.name_short or self.name_full

    def industry_phrase(self) -> str:
        """Нейтральное описание отрасли по ОКВЭД — без оценок и выдумок."""
        code = (self.okved or "").split(".")[0].zfill(2)
        for prefix, phrase in OKVED_SECTIONS:
            if code == prefix:
                return phrase
        return "предприятие"


def validate_inn(inn: str) -> str:
    """Проверяет формат ИНН и возвращает очищенное значение."""
    digits = re.sub(r"\D", "", inn or "")
    if not digits:
        raise DaDataError("Укажите ИНН компании.")
    if len(digits) not in (10, 12):
        raise DaDataError(
            f"ИНН должен состоять из 10 цифр (организация) или 12 (ИП). "
            f"Введено цифр: {len(digits)}."
        )
    return digits


def find_by_inn(inn: str, token: str, timeout: int = 20) -> Company:
    """Находит компанию по ИНН."""
    digits = validate_inn(inn)
    if not token:
        raise DaDataError(
            "Не указан ключ DaData. Откройте настройки и введите ключ доступа."
        )

    request = urllib.request.Request(
        FIND_BY_ID_URL,
        data=json.dumps({"query": digits}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {token}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise DaDataError(
                "Ключ DaData отклонён сервисом. Проверьте ключ в настройках."
            ) from exc
        if exc.code == 429:
            raise DaDataError(
                "Исчерпан дневной лимит запросов к DaData. Попробуйте завтра "
                "или введите данные компании вручную."
            ) from exc
        raise DaDataError(
            f"Сервис DaData вернул ошибку {exc.code}. Попробуйте позже."
        ) from exc
    except urllib.error.URLError as exc:
        raise DaDataError(
            "Нет связи с сервисом DaData. Проверьте подключение к интернету "
            "или введите данные компании вручную."
        ) from exc
    except json.JSONDecodeError as exc:
        raise DaDataError("Сервис DaData вернул некорректный ответ.") from exc

    suggestions = payload.get("suggestions") or []
    if not suggestions:
        raise DaDataError(
            f"Компания с ИНН {digits} не найдена в реестре. "
            f"Проверьте номер или введите данные вручную."
        )

    item = suggestions[0]
    data = item.get("data", {})
    name = data.get("name", {}) or {}
    address = data.get("address", {}) or {}
    address_data = address.get("data", {}) or {}
    management = data.get("management") or {}
    state = data.get("state", {}) or {}

    return Company(
        inn=data.get("inn", digits),
        kpp=data.get("kpp") or "",
        ogrn=data.get("ogrn") or "",
        name_short=name.get("short_with_opf") or item.get("value") or "",
        name_full=name.get("full_with_opf") or "",
        address=address.get("value") or "",
        region=address_data.get("region_with_type") or "",
        okved=data.get("okved") or "",
        okved_name="",
        manager_name=management.get("name") or "",
        manager_post=(management.get("post") or "").capitalize(),
        status=state.get("status") or "",
    )
