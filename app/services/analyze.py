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

Сфера деятельности клиента: {industry}.

Разбери разговор и верни результат СТРОГО в формате JSON:

{{
  "summary": "итог звонка ровно тремя предложениями",
  "segment_value": "одна фраза: чем электронная торговая площадка полезна компании такого профиля",
  "client_needs": "абзац 2-3 предложения: что клиенту нужно и чего он ждёт",
  "our_offer": "абзац 2-3 предложения: что мы готовы для этого сделать",
  "benefits": ["преимущество 1", "преимущество 2", "преимущество 3", "преимущество 4"]
}}

Что писать в каждом поле:

summary — запись в CRM от лица нашего менеджера, ровно три предложения:
  1) с кем из компании клиента говорили и какая у клиента ситуация сейчас;
  2) ВСЕ причины отказа и возражения, которые прозвучали, — перечисли все, не выбирай одну;
  3) о чём договорились и когда следующий шаг.
  Первое предложение начни с действия менеджера: «Провёл разговор с…»,
  «Дозвонился до…», «Связался с…». НЕ пиши «с нами говорил» — звонили мы.

segment_value — короткая фраза без подлежащего, продолжающая название компании.
  Опиши, какую пользу электронная торговая площадка даёт компании именно этого
  профиля деятельности. Пример формы: «фармацевтическое предприятие, для которого
  важны регулярные закупки сырья и упаковки у проверенных поставщиков».
  НЕ упоминай регион, город и адрес — это не нужно.

client_needs — что клиенту нужно от площадки: его ожидания, потребности и условия,
  которые он назвал в разговоре. Пиши на «Вы», 2-3 предложения. Если клиент прямо
  не назвал потребность, опиши её из контекста разговора.

our_offer — что мы можем и готовы предложить именно под эти потребности.
  Пиши на «Вы», 2-3 предложения, конкретно и без общих слов.

benefits — 3-4 коротких пункта (по 3-6 слов) для слайда презентации: что даёт
  клиенту работа именно с НАШЕЙ площадкой ЕСТП и что закрывает его потребности.
  Это НАШИ преимущества: акции, условия и возможности других площадок
  (B2B, Bidzaar и прочих) сюда писать нельзя. Без точек в конце.
  Опирайся на реальные возможности ЕСТП: размещение закупок силами наших
  специалистов, работа без электронной подписи, бесплатное участие поставщиков
  по стандартным тарифам, отсутствие комиссии с победителя, персональный
  тариф, раздел «Тендеры» на сайте клиента, два личных менеджера.

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


def _generate_analysis(base_url: str, model: str, transcript: str,
                       company: str, industry: str) -> tuple[dict, list[str]]:
    """Один запрос к модели: выжимка, блоки КП и преимущества для слайда."""
    notes: list[str] = []
    base_prompt = ANALYSIS_PROMPT.format(
        company=company, industry=industry, transcript=transcript)
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
        segment_value=industry or "компания, которая регулярно проводит закупки",
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

    # В коммерческом предложении не место акциям и площадкам конкурентов.
    needs, needs_cleaned = drop_foreign_offers(
        _strip_salutation(_clean_model_output(payload["client_needs"])))

    offer, offer_cleaned = drop_foreign_offers(
        _strip_salutation(_clean_model_output(payload["our_offer"])))
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
        summary=_clean_model_output(payload["summary"]) or fallback.summary,
        segment_value=segment or fallback.segment_value,
        client_needs=needs or fallback.client_needs,
        our_offer=offer or fallback.our_offer,
        benefits=payload.get("benefits") or fallback.benefits,
        used_ai=True,
        notes=notes,
    )
