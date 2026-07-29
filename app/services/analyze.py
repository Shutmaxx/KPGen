# -*- coding: utf-8 -*-
"""Анализ разговора: выжимка для CRM и блоки текста для КП.

Основной режим — локальная модель Qwen через Ollama.
Если Ollama недоступна, работает запасной режим по правилам:
текст получается шаблонным, но программа не останавливается.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from .dadata import Company

ProgressCallback = Callable[[int, str], None]


@dataclass
class CallAnalysis:
    """Результат разбора разговора."""
    summary: str              # выжимка для CRM (3 предложения)
    segment_value: str        # чем площадка полезна компании в её отрасли
    client_needs: str         # абзац КП: что клиенту нужно от продукта
    our_offer: str            # абзац КП: что мы готовы предложить
    benefits: list[str]       # преимущества для слайда презентации
    used_ai: bool             # True — писала модель, False — правила
    notes: list[str]          # предупреждения для интерфейса


# --------------------------------------------------------------------------
# Работа с Ollama
# --------------------------------------------------------------------------
def ollama_available(base_url: str, timeout: int = 3) -> bool:
    """Проверяет, запущена ли Ollama."""
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags",
                                    timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def installed_models(base_url: str, timeout: int = 5) -> list[str]:
    """Список моделей, установленных в Ollama."""
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags",
                                    timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return [m.get("name", "") for m in payload.get("models", [])]
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return []


def _ask_model(base_url: str, model: str, prompt: str,
               timeout: int = 600, max_tokens: int = 400) -> str:
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": max_tokens},
    }).encode("utf-8")

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return (payload.get("response") or "").strip()


# --------------------------------------------------------------------------
# Разбор текста
# --------------------------------------------------------------------------
def split_sentences(text: str) -> list[str]:
    """Делит текст на предложения."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z])", cleaned)
    return [p.strip() for p in parts if p.strip()]


def _clean_model_output(text: str) -> str:
    """Убирает вводные фразы и разметку, которые модель добавляет сама."""
    result = text.strip()
    result = re.sub(r"^```[a-z]*\s*|\s*```$", "", result, flags=re.MULTILINE)
    result = re.sub(r"^\*+|\*+$", "", result).strip()
    # Служебные вступления вида «Вот итог звонка:»
    result = re.sub(
        r"^(вот|итог|результат|итоги)[^:\n]{0,40}:\s*",
        "", result, flags=re.IGNORECASE,
    )
    result = re.sub(r"^[-–—•\d.)\s]+", "", result)
    return result.strip()


def _strip_salutation(text: str) -> str:
    """Удаляет обращение в начале абзаца.

    Обращение к адресату уже есть в начале письма, поэтому повторное
    «Уважаемые коллеги…» в середине КП выглядит ошибкой.
    """
    result = text.strip()
    pattern = (
        r"^(уважаем\w+|здравствуйте|добрый день|дорог\w+|коллеги)"
        r"[^.!?]{0,120}?[,!.]\s+"
    )
    result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    # После удаления обращения предложение должно начинаться с заглавной буквы.
    if result and result[0].islower():
        result = result[0].upper() + result[1:]
    return result.strip()


ANALYSIS_PROMPT = """Ты помогаешь менеджеру электронной торговой площадки ЕСТП.

РОЛИ В РАЗГОВОРЕ (это важно, не перепутай):
- менеджер ЕСТП — это НАША сторона, он звонит и предлагает площадку. Пиши от его лица.
- представитель компании «{company}» — это КЛИЕНТ, он отвечает на звонок.

Сфера деятельности клиента по реестру: {industry}.
{hints}

Разбери разговор и верни результат СТРОГО в формате JSON:

{{
  "summary": "итог звонка ровно тремя предложениями",
  "segment_value": "одна фраза: чем электронная торговая площадка полезна компании такого профиля",
  "client_needs": "абзац 2-3 предложения: что клиенту нужно и чего он ждёт",
  "our_offer": "абзац 2-3 предложения: что мы готовы для этого сделать",
  "benefits": ["преимущество 1", "преимущество 2", "преимущество 3", "преимущество 4"]
}}

Что писать в каждом поле:

СНАЧАЛА РАЗБЕРИСЬ, ЧЕМ ЗАКОНЧИЛСЯ ЗВОНОК. Возможны три исхода:
  А) КЛИЕНТ ПОПРОСИЛ ПРИСЛАТЬ ПРЕДЛОЖЕНИЕ («пишите на почту», «присылайте») —
     это интерес, а НЕ отказ. Так и пиши: отказа не было.
  Б) КЛИЕНТ ОТКАЗАЛСЯ и назвал причины (нет людей, действует договор, дорого).
  В) РЕШЕНИЕ ОТЛОЖЕНО до определённого срока.
  От исхода зависит тон всех текстов: при интересе не пиши про «причины отказа».

ЗАТЕМ НАЙДИ В РАЗГОВОРЕ:
  - на какой площадке клиент работает сейчас;
  - обсуждался ли формат: заменить площадку или добавить вторую параллельно;
  - какие аргументы приводил наш менеджер (например, что в отрасли клиента
    у нас уже работают конкретные компании) — их надо использовать;
  - какие компании упоминались как наши действующие клиенты;
  - когда договорились связаться снова.

Что писать в каждом поле:

summary — запись в CRM от лица нашего менеджера, ровно три предложения:
  1) с кем говорили, его роль и на какой площадке клиент работает сейчас;
  2) исход: при отказе — все причины; при интересе — что отказа не было
     и какие аргументы прозвучали;
  3) о чём договорились и когда следующий шаг (срок — дословно из разговора).
  Первое предложение начни с действия менеджера: «Дозвонился до…»,
  «Провёл разговор с…», «Связался с…». НЕ пиши «с нами говорил» — звонили мы.

segment_value — характеристика компании, 1-2 предложения.
  Опиши, чем компания РЕАЛЬНО занимается и какое место занимает на рынке.
  Формальная запись в реестре: {industry}. Но если по названию компании
  очевидна её настоящая деятельность (например, известная служба доставки
  числится как «почтовое предприятие»), пиши по сути дела, а не по реестру.
  Второе предложение — почему для такой компании закупки являются
  постоянным и ответственным процессом.
  Начни со слова «является» или с описания без глагола.
  НЕ упоминай регион, город и адрес.
  Без превосходных степеней и без выдуманных фактов: наград, оборотов,
  дат основания, численности сотрудников.

client_needs — что клиенту нужно от площадки, 2-3 предложения на «Вы».
  Опиши его ожидания так, как они прозвучали: интересна ли площадка как
  дополнительная или как замена, что для него важно увидеть в первую очередь,
  чего он опасается. Не превращай это в перечень возражений — это описание
  потребности, а не отказа.

our_offer — что мы готовы сделать именно под эти потребности, 2-3 предложения.
  Начни строго со слов «Также мы можем предложить». Пиши на «Вы», конкретно.
  ОБЯЗАТЕЛЬНО используй то, что прозвучало в разговоре:
  - если обсуждали работу параллельно с текущей площадкой — напиши, что
    переходить целиком не нужно и процессы перестраивать не придётся;
  - если менеджер называл наших клиентов из отрасли собеседника — упомяни,
    что в его сегменте у нас уже работают профильные поставщики;
  - если клиент просил показать функционал — предложи демонстрацию.
  Следи за согласованием слов: «быструю обработку», а не «быстрое обработку».

benefits — 3-4 коротких пункта (по 3-6 слов) для слайда презентации.
  Подбирай их ПОД ОТРАСЛЬ И ЗАДАЧИ ЭТОГО клиента, а не общий список:
  для логистической компании уместно «профильные поставщики в перевозках»,
  для производства — «поставщики сырья и комплектующих».
  Это НАШИ преимущества: акции, условия и возможности других площадок
  (B2B, Bidzaar и прочих) сюда писать нельзя. Без точек в конце.

ЧТО МЫ РЕАЛЬНО УМЕЕМ (бери отсюда, не выдумывай):
  размещение закупок силами наших специалистов; два личных менеджера;
  работа без электронной подписи; размещение тендера за 5 минут;
  дублирование закупок на агрегаторах; бесплатное участие поставщиков
  по стандартным тарифам; отсутствие комиссии с победителя торгов;
  стандартные тарифы на 3 и 6 месяцев и персональный тариф;
  раздел «Тендеры» на сайте клиента (i-frame модуль);
  приглашение поставщиков и телемаркетинг; техническая и юридическая
  поддержка; демонстрация функционала по запросу;
  работа параллельно с текущей площадкой клиента.

ОСОБО ВАЖНО — не путай, чьи это условия:
  в разговоре клиент рассказывает про ДРУГИЕ площадки, где он уже работает
  (B2B, Bidzaar и прочие). Их акции, скидки, бесплатные периоды и тарифы
  принадлежат ИМ, а не нам. Никогда не приписывай эти условия площадке ЕСТП
  ни в summary, ни в our_offer, ни в benefits. Мы акций не проводим.

Общие правила:
- СРОКИ И ДАТЫ переноси дословно, как прозвучали в разговоре: если сказано
  «до середины августа» — так и пиши, не заменяй на «до конца года» и не обобщай.
  Но помни: срок акции чужой площадки — это срок клиента, а не наше предложение;
- обращайся к клиенту на «Вы», тон уважительный, без давления;
- НЕ начинай абзацы с приветствия или обращения к компании
  («Уважаемые…», «Здравствуйте») — это середина письма, обращение уже есть выше;
- нигде не используй заголовки, списки и вводные слова;
- опирайся только на то, что реально прозвучало в разговоре, ничего не выдумывай;
- верни только JSON, без пояснений до и после.

РАСШИФРОВКА:
{transcript}"""


def extract_call_hints(transcript: str) -> dict[str, str]:
    """Достаёт из разговора детали, которые модель обычно упускает.

    Небольшая модель не выделяет сама ни упомянутых клиентов-референсов,
    ни реальную сферу деятельности собеседника, хотя в продаже это главные
    аргументы. Поэтому находим их правилами и передаём в подсказку явно.
    """
    hints: dict[str, str] = {}

    # Компании, названные менеджером как наши действующие клиенты.
    # Аббревиатуры вроде «ПЛК» короткие, поэтому порог длины низкий.
    reference_patterns = [
        r"(?:работает|пользуется|размещается|размещают)\s+"
        r"([А-ЯЁ][\w-]*(?:\s+[А-ЯЁ][\w-]*){0,3})",
        # Аббревиатура с расшифровкой: «ПЛК, Почтовая Логистическая Компания»
        r"[А-ЯЁ]{2,5},\s*([А-ЯЁ][\w-]+(?:\s+[А-ЯЁ][\w-]+){1,3})",
    ]
    references: list[str] = []
    for pattern in reference_patterns:
        for match in re.findall(pattern, transcript):
            value = match.strip(" ,.")
            if 2 < len(value) < 60 and value not in references:
                references.append(value)
    if references:
        # Полные названия информативнее аббревиатур — они идут первыми.
        references.sort(key=len, reverse=True)
        hints["references"] = ", ".join(references[:2])

    # Слова о деятельности клиента, прозвучавшие в разговоре.
    activity_words = [
        "грузоперевозк", "перевозк", "логистик", "доставк", "склад",
        "производств", "торговл", "строительств", "поставк",
        "медицин", "фарм", "энергетик", "транспорт", "снабжен",
    ]
    lowered = transcript.lower()
    found = [w for w in activity_words if w in lowered]
    if found:
        hints["activity"] = ", ".join(found[:5])

    # Формат сотрудничества, если он обсуждался.
    if re.search(r"дополнительн\w+\s+(?:площадк|как)", lowered):
        hints["format"] = "обсуждалась работа как на дополнительной площадке"

    return hints


def _extract_json(text: str) -> dict | None:
    """Достаёт объект JSON из ответа модели.

    Модель нередко оборачивает ответ в markdown или добавляет пояснения,
    поэтому берём фрагмент от первой «{» до последней «}».
    """
    cleaned = re.sub(r"```[a-z]*\s*|\s*```", "", text).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        payload = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_summary(text: str, notes: list[str]) -> str:
    """Приводит выжимку к трём предложениям."""
    sentences = split_sentences(_clean_model_output(text))
    if len(sentences) == 3:
        return " ".join(sentences)
    if len(sentences) > 3:
        notes.append("Модель вернула больше трёх предложений — текст сокращён.")
        return " ".join(sentences[:3])
    notes.append("Модель вернула меньше трёх предложений — проверьте текст.")
    return " ".join(sentences)


REQUIRED_FIELDS = ("summary", "segment_value", "client_needs", "our_offer")

# Названия площадок-конкурентов и формулировки их условий.
# Такие пункты не должны попадать в наши преимущества на слайде.
FOREIGN_BENEFIT_MARKERS = (
    "bidzaar", "бидзаар", "b2b", "ртс", "сбербанк-аст", "росэлторг",
    "етп", "их площадк", "текущей площадк", "другой площадк",
    "акци",  # у нас нет акций — это условие конкурента
    "промо", "тестовый период",
)


def _is_our_benefit(text: str) -> bool:
    """Отсеивает преимущества, которые на самом деле принадлежат конкуренту."""
    lowered = text.lower()
    return not any(marker in lowered for marker in FOREIGN_BENEFIT_MARKERS)


# Частые ошибки согласования у модели. Ключ — как пишет модель.
GRAMMAR_FIXES: list[tuple[str, str]] = [
    (r"\bбыстрое обработку\b", "быструю обработку"),
    (r"\bбыстрый обработку\b", "быструю обработку"),
    (r"\bрегулярное взаимодействия\b", "регулярное взаимодействие"),
    (r"\bэффективности процессов\b", "эффективности процесса"),
    (r"\bразмещения закупок на нашей платформе\b",
     "размещение закупок на нашей платформе"),
]


def fix_grammar(text: str) -> str:
    """Исправляет типичные ошибки согласования в тексте от модели."""
    result = text
    for pattern, replacement in GRAMMAR_FIXES:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    # Модель дублирует форму собственности: «АО "АО ДПД РУС"».
    result = re.sub(
        r"\b(ООО|АО|ЗАО|ПАО|ОАО)\s+([\"«])\s*\1\s+",
        r"\1 \2", result, flags=re.IGNORECASE,
    )
    return result


def ensure_offer_opening(text: str) -> str:
    """Гарантирует, что абзац с предложением начинается нужными словами."""
    stripped = text.strip()
    if not stripped:
        return stripped
    if stripped.lower().startswith(("также мы можем", "так же мы можем")):
        # Приводим к слитному написанию — «также» в этом значении пишется слитно.
        return re.sub(r"^так\s+же", "Также", stripped, flags=re.IGNORECASE)

    first = stripped[0].lower() + stripped[1:]
    return "Также " + first


def drop_foreign_offers(text: str) -> tuple[str, bool]:
    """Убирает из текста для клиента чужие акции и условия.

    Модель иногда переносит в наше предложение акцию другой площадки,
    услышанную в разговоре. Отправлять такое клиенту нельзя.
    Возвращает очищенный текст и признак, что правка потребовалась.
    """
    sentences = split_sentences(text)
    if not sentences:
        return text, False

    kept, changed = [], False
    for sentence in sentences:
        lowered = sentence.lower()
        if re.search(r"акци|промо|бесплатн\w+\s+период|тестов\w+\s+период", lowered):
            changed = True
            continue
        kept.append(sentence)

    if not kept:
        return text, False
    return " ".join(kept), changed


def _parse_payload(payload: dict) -> dict:
    """Приводит ответ модели к ожидаемому виду."""
    result = {field: str(payload.get(field, "")).strip() for field in REQUIRED_FIELDS}

    raw_benefits = payload.get("benefits") or []
    if isinstance(raw_benefits, str):
        raw_benefits = [line.strip(" -•\t") for line in raw_benefits.splitlines()]
    benefits = [str(item).strip(" -•.\t") for item in raw_benefits if str(item).strip()]

    benefits = [b for b in benefits if _is_our_benefit(b)]

    result["benefits"] = benefits[:4]
    return result


def _build_hints_block(transcript: str) -> str:
    """Готовит блок подсказок для промпта по деталям разговора."""
    hints = extract_call_hints(transcript)
    if not hints:
        return ""

    lines = ["", "НАЙДЕНО В РАЗГОВОРЕ (используй обязательно):"]
    if "references" in hints:
        lines.append(
            f"- наши действующие клиенты, названные менеджером: {hints['references']}."
            " Упомяни в our_offer, что в сегменте клиента у нас уже работают"
            " профильные компании."
        )
    if "activity" in hints:
        lines.append(
            f"- о деятельности клиента говорили так: {hints['activity']}."
            " Опиши в segment_value именно эту сферу, а не формулировку реестра."
        )
    if "format" in hints:
        lines.append(f"- {hints['format']}.")
    return "\n".join(lines)


def _generate_analysis(base_url: str, model: str, transcript: str,
                       company: str, industry: str) -> tuple[dict, list[str]]:
    """Один запрос к модели: выжимка, блоки КП и преимущества для слайда."""
    notes: list[str] = []
    base_prompt = ANALYSIS_PROMPT.format(
        company=company, industry=industry, transcript=transcript,
        hints=_build_hints_block(transcript))
    prompt = base_prompt
    best: dict | None = None

    for attempt in range(2):
        raw = _ask_model(base_url, model, prompt, max_tokens=1100)
        payload = _extract_json(raw)

        if payload is None:
            prompt = (
                base_prompt
                + "\n\nВАЖНО: предыдущий ответ не был корректным JSON. Верни только "
                  "объект JSON с полями summary, segment_value, client_needs, "
                  "our_offer, benefits."
            )
            continue

        parsed = _parse_payload(payload)

        if all(parsed[field] for field in REQUIRED_FIELDS):
            if len(split_sentences(parsed["summary"])) == 3:
                return parsed, notes
            best = parsed
            prompt = (
                base_prompt
                + f"\n\nВАЖНО: в поле summary было "
                  f"{len(split_sentences(parsed['summary']))} предложений. "
                  "Нужно ровно три предложения."
            )
            continue

        best = best or parsed

    if best is None:
        raise ValueError("Модель не вернула корректный ответ")

    best["summary"] = _normalize_summary(best["summary"], notes)
    return best, notes


# --------------------------------------------------------------------------
# Запасной режим без модели
# --------------------------------------------------------------------------
OBJECTION_RULES: list[tuple[str, str, str]] = [
    (r"нет сотрудник|некому|два человека|не хватает люд|нет ресурс",
     "нехватка сотрудников для работы с площадкой",
     "у Вас ограничен ресурс отдела снабжения"),
    (r"договор|контракт|оплатили|лицензи",
     "действующий договор с текущей площадкой",
     "у Вас действует договор с текущей площадкой"),
    (r"дорог|цена|стоимость|дешевл|скидк",
     "вопрос стоимости обслуживания",
     "для Вас важна стоимость обслуживания"),
    (r"подумаю|не сейчас|позже|перезвон",
     "решение отложено",
     "Вы просили вернуться к вопросу позже"),
    (r"не интересн|не нужно|отказ",
     "предложение не заинтересовало",
     "предложение пока не является для Вас приоритетным"),
]

COMPETITORS = ["Bidzaar", "РТС-тендер", "Сбербанк-АСТ", "B2B-Center", "Росэлторг", "ЕТП"]


def _find_deadline(text: str) -> str:
    """Находит срок, названный в разговоре, сохраняя формулировку."""
    patterns = [
        r"(?:до|в|к)\s+(?:середин\w+|начал\w+|конц\w+)\s+"
        r"(январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)\w*",
        r"(?:до|в|к)\s+"
        r"(январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)\w*",
        r"после\s+нового\s+года",
        r"в\s+следующ\w+\s+(?:месяц\w*|недел\w*|квартал\w*)",
        r"через\s+(?:недел\w+|месяц\w*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return ""


def _rule_based(transcript: str, company: str,
                industry: str = "") -> CallAnalysis:
    """Формирует тексты по ключевым словам, когда модель недоступна."""
    lowered = transcript.lower()

    found_competitors = [c for c in COMPETITORS if c.lower() in lowered]
    competitor = found_competitors[0] if found_competitors else ""

    objections: list[str] = []
    needs_parts: list[str] = []
    for pattern, objection, context in OBJECTION_RULES:
        if re.search(pattern, lowered):
            objections.append(objection)
            needs_parts.append(context)

    deadline = _find_deadline(transcript)

    # Выжимка
    first = f"Провёл разговор с представителем компании {company}"
    first += f", закупки размещаются на площадке {competitor}." if competitor else "."

    if objections:
        second = "Основные причины отказа: " + ", ".join(objections[:2]) + "."
    else:
        second = "Клиент взял предложение на рассмотрение."

    third = "Договорились направить коммерческое предложение"
    third += f" и вернуться к разговору {deadline}." if deadline else " на рассмотрение."

    # Абзацы для КП
    if needs_parts:
        needs = (
            "В разговоре Вы обозначили, что "
            + ", ".join(needs_parts[:2])
            + ". Для Вас важно, чтобы работа на площадке не требовала "
              "дополнительных ресурсов и была прозрачной по стоимости."
        )
    else:
        needs = (
            "В разговоре мы обсудили Ваш текущий порядок проведения закупок. "
            "Для Вас важно, чтобы площадка была удобной, понятной по стоимости "
            "и не требовала дополнительных ресурсов отдела снабжения."
        )

    offer = (
        "Мы готовы взять на себя размещение и сопровождение закупок, подобрать "
        "тариф под Ваш объём процедур и подключить площадку без нагрузки на "
        "Ваших сотрудников. По итоговым условиям готовы обсуждать индивидуальный "
        "тариф."
    )

    return CallAnalysis(
        summary=" ".join([first, second, third]),
        segment_value=(
            f"{industry}, для которого закупки товаров, работ и услуг "
            f"являются постоянным и ответственным процессом"
            if industry else
            "компания, для которой закупки являются постоянным процессом"
        ),
        client_needs=needs,
        our_offer=offer,
        benefits=[
            "Размещение закупок силами наших специалистов",
            "Работа без электронной подписи",
            "Бесплатное участие для поставщиков",
            "Персональный тариф под объём закупок",
        ],
        used_ai=False,
        notes=["Текст составлен по правилам без ИИ — проверьте формулировки."],
    )


# --------------------------------------------------------------------------
# Точка входа
# --------------------------------------------------------------------------
def analyze_call(
    transcript: str,
    company: Company | None,
    *,
    use_ai: bool,
    base_url: str,
    model: str,
    progress: ProgressCallback | None = None,
) -> CallAnalysis:
    """Разбирает разговор и готовит тексты."""
    company_name = company.display_name if company else "клиента"
    industry = company.industry_phrase() if company else "предприятие"

    if not use_ai:
        return _rule_based(transcript, company_name, industry)

    if not ollama_available(base_url):
        result = _rule_based(transcript, company_name, industry)
        result.notes.insert(
            0,
            "Ollama не запущена — использован режим без ИИ. "
            "Запустите Ollama, чтобы получить более точные формулировки.",
        )
        return result

    if model not in installed_models(base_url):
        result = _rule_based(transcript, company_name, industry)
        result.notes.insert(
            0,
            f"Модель «{model}» не установлена в Ollama — использован режим без ИИ. "
            f"Выполните: ollama pull {model}",
        )
        return result

    try:
        if progress:
            progress(15, "Модель разбирает разговор…")
        payload, notes = _generate_analysis(
            base_url, model, transcript, company_name, industry)
        if progress:
            progress(100, "Анализ завершён")

    except (urllib.error.URLError, OSError, json.JSONDecodeError,
            TimeoutError, ValueError) as exc:
        result = _rule_based(transcript, company_name, industry)
        result.notes.insert(
            0, f"Модель не ответила, использован режим без ИИ. Причина: {exc}"
        )
        return result

    fallback = _rule_based(transcript, company_name, industry)

    segment = _clean_model_output(payload["segment_value"]).rstrip(".")
    # Небольшая модель иногда выдаёт обрывок вроде «Выполняет перевозки».
    # Такой текст в первом абзаце письма выглядит хуже формулировки
    # по реестру, поэтому короткие ответы отбрасываем.
    if len(segment) < 70:
        segment = fallback.segment_value
        notes.append(
            "Характеристика компании составлена по данным реестра — "
            "проверьте формулировку."
        )

    # В коммерческом предложении не место акциям и площадкам конкурентов.
    needs, needs_cleaned = drop_foreign_offers(
        _strip_salutation(_clean_model_output(payload["client_needs"])))

    offer, offer_cleaned = drop_foreign_offers(
        _strip_salutation(_clean_model_output(payload["our_offer"])))
    offer = fix_grammar(ensure_offer_opening(offer))
    needs = fix_grammar(needs)
    if offer_cleaned and len(split_sentences(offer)) < 2:
        # После вырезания текст может стать слишком коротким —
        # дополняем его нашими реальными условиями.
        offer = (offer + " Готовы подобрать тариф под Ваш объём процедур "
                         "и обсудить индивидуальные условия.").strip()

    if needs_cleaned and len(split_sentences(needs)) < 2:
        needs = (needs + " Для Вас важно, чтобы работа на площадке была "
                         "прозрачной по стоимости и не требовала лишних "
                         "трудозатрат.").strip()

    if offer_cleaned or needs_cleaned:
        notes.append(
            "Из текста убрано упоминание акции другой площадки — "
            "проверьте формулировку."
        )

    return CallAnalysis(
        summary=fix_grammar(_clean_model_output(payload["summary"]))
                or fallback.summary,
        segment_value=segment or fallback.segment_value,
        client_needs=needs or fallback.client_needs,
        our_offer=offer or fallback.our_offer,
        benefits=payload.get("benefits") or fallback.benefits,
        used_ai=True,
        notes=notes,
    )
