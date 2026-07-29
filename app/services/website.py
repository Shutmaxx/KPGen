# -*- coding: utf-8 -*-
"""Поиск корпоративного сайта компании.

Сведения о сайте в базовом тарифе DaData недоступны, поэтому адрес
подбирается по названию. Найденный домен обязательно проверяется:
на странице должно упоминаться название компании или её ИНН.
Без такой проверки в коммерческое предложение легко попадёт чужой сайт.
"""
from __future__ import annotations

import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

TIMEOUT = 6
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")

# Приставки организационно-правовых форм, которые не входят в домен.
OPF_PREFIXES = ("ООО", "АО", "ЗАО", "ПАО", "ОАО", "ИП", "НАО", "МУП", "ГУП",
                "ФГУП", "ТОО", "НКО", "АНО", "УК", "ТД", "МТД", "ПКФ", "НПО",
                "НПП", "ГК", "КБ")

# Слова, которые встречаются в сотнях названий и потому не могут
# служить признаком принадлежности сайта конкретной компании.
GENERIC_WORDS = {
    "фирма", "компания", "завод", "фабрика", "групп", "группа", "холдинг",
    "торговый", "дом", "центр", "сервис", "строй", "пром", "трейд",
    "инвест", "проект", "система", "системы", "технологии", "продакшн",
    "производство", "предприятие", "объединение", "корпорация", "агро",
    "нефть", "газ", "банк", "плюс", "союз", "мастер", "партнер", "партнёр",
    "русь", "россия", "рос", "рус", "сити", "лайн", "стар", "стандарт",
}

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


@dataclass
class WebsiteLookup:
    """Результат поиска сайта."""
    url: str = ""
    confirmed: bool = False
    note: str = ""

    @property
    def found(self) -> bool:
        return bool(self.url) and self.confirmed


def _core_name(company_name: str) -> str:
    """Оставляет от названия только смысловую часть."""
    name = company_name.upper()
    name = re.sub(r'["«»\']', " ", name)
    words = [w for w in name.split() if w and w not in OPF_PREFIXES]
    return " ".join(words).strip()


def transliterate(text: str) -> str:
    """Переводит русское название в латиницу для доменного имени."""
    result = []
    for char in text.lower():
        if char in TRANSLIT:
            result.append(TRANSLIT[char])
        elif char.isalnum():
            result.append(char)
    return "".join(result)


def _spelling_variants(stem: str) -> list[str]:
    """Варианты написания домена.

    Компании часто выбирают английское написание бренда, отличное от
    прямой транслитерации: «канонфарма» → canonpharma, «фанагория» → fanagoria.
    """
    variants = [stem]

    def add(value: str) -> None:
        if value and value not in variants:
            variants.append(value)

    # Окончания: «-ия» пишут и как -iya, и как -ia.
    for base in list(variants):
        if base.endswith("iya"):
            add(base[:-3] + "ia")
            add(base[:-3] + "ya")
        elif base.endswith("ya"):
            add(base[:-2] + "ia")
            add(base[:-2] + "a")

    # Замены букв применяются и по отдельности, и вместе:
    # «канонфарма» встречается как kanonfarma и как canonpharma.
    for base in list(variants):
        if base.startswith("k"):
            add("c" + base[1:])
    for base in list(variants):
        if "f" in base:
            add(base.replace("f", "ph", 1))

    return variants


def domain_candidates(company_name: str) -> list[str]:
    """Возможные адреса сайта компании."""
    core = _core_name(company_name)
    if not core:
        return []

    words = core.split()
    # Короткие аббревиатуры вроде «АПФ» в домен обычно не входят,
    # а общие слова («фирма», «завод») не отличают компанию от других.
    meaningful = [w for w in words
                  if len(w) > 3 and w.lower() not in GENERIC_WORDS]
    if not meaningful:
        meaningful = [w for w in words if len(w) > 3] or words

    # Первое значимое слово — обычно и есть бренд, поэтому проверяем его
    # раньше склейки всего названия.
    stems: list[str] = []
    for source in (*meaningful, "".join(meaningful)):
        stem = transliterate(source)
        if len(stem) >= 4 and stem not in stems:
            stems.append(stem)

    candidates: list[str] = []
    for stem in stems:
        for variant in _spelling_variants(stem):
            candidates.extend([f"{variant}.ru", f"{variant}.com"])

    if len(meaningful) > 1:
        dashed = transliterate("-".join(meaningful))
        candidates.append(f"{dashed}.ru")

    cyrillic = "".join(meaningful).lower()
    if len(cyrillic) >= 4:
        candidates.append(f"{cyrillic}.рф")

    # Убираем дубли, сохраняя порядок, и ограничиваем перебор.
    seen: set[str] = set()
    unique = [c for c in candidates if not (c in seen or seen.add(c))]
    return unique[:20]


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        raw = response.read(200_000)
    for encoding in ("utf-8", "windows-1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def _page_mentions_company(html: str, company_name: str, inn: str) -> bool:
    """Проверяет, что страница действительно принадлежит компании.

    Сравнение идёт по всем значимым словам названия — и в кириллице,
    и в латинском написании, потому что бренд на сайте часто написан
    по-английски.
    """
    text = re.sub(r"<[^>]+>", " ", html).lower()
    text = re.sub(r"\s+", " ", text)
    compact = text.replace(" ", "")

    if inn and inn in compact:
        return True

    core = _core_name(company_name).lower()
    if not core:
        return False

    for word in core.split():
        # Общие слова совпадут на любом сайте — они ничего не подтверждают.
        if len(word) < 4 or word in GENERIC_WORDS:
            continue
        if word in text:
            return True
        # Латинские варианты того же слова.
        for variant in _spelling_variants(transliterate(word)):
            if len(variant) >= 4 and variant in compact:
                return True
    return False


def find_website(company_name: str, inn: str = "") -> WebsiteLookup:
    """Подбирает сайт компании и подтверждает принадлежность.

    Возвращает результат даже при неудаче — с пояснением для интерфейса.
    """
    candidates = domain_candidates(company_name)
    if not candidates:
        return WebsiteLookup(note="Не удалось составить адрес по названию компании")

    unreachable = 0
    for domain in candidates:
        for scheme in ("https", "http"):
            url = f"{scheme}://{domain}"
            try:
                html = _fetch(url)
            except (urllib.error.URLError, urllib.error.HTTPError,
                    socket.timeout, OSError, ValueError):
                unreachable += 1
                continue

            if _page_mentions_company(html, company_name, inn):
                return WebsiteLookup(url=domain, confirmed=True,
                                     note=f"Сайт найден: {domain}")
            # Домен живой, но принадлежит кому-то другому — не берём.
            break

    if unreachable:
        return WebsiteLookup(note="Сайт компании не найден автоматически")
    return WebsiteLookup(note="Сайт компании не подтверждён")
