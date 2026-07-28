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
    summary: str            # выжимка для CRM (3 предложения)
    call_context: str       # абзац КП «в разговоре Вы обозначили…»
    outcome: str            # абзац КП про договорённости и сроки
    used_ai: bool           # True — писала модель, False — правила
    notes: list[str]        # предупреждения для интерфейса


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

Разбери разговор и верни результат СТРОГО в формате JSON с тремя полями:

{{
  "summary": "итог звонка РОВНО ТРЕМЯ предложениями",
  "context": "абзац из 2-3 предложений для коммерческого предложения",
  "outcome": "абзац из 2-3 предложений для завершения коммерческого предложения"
}}

Что писать в каждом поле:

summary — запись в CRM от лица нашего менеджера, ровно три предложения:
  1) с кем из компании клиента говорили и какая у клиента ситуация сейчас;
  2) ВСЕ причины отказа и возражения, которые прозвучали. Если клиент назвал
     несколько причин (например, нехватку сотрудников И действующий договор),
     перечисли их все, не выбирай одну;
  3) о чём договорились и когда следующий шаг.
  Первое предложение начни с действия менеджера: «Провёл разговор с…»,
  «Дозвонился до…», «Связался с…». НЕ пиши «с нами говорил» — звонили мы.

context — начни строго со слов «В разговоре Вы обозначили», опиши главную проблему
  клиента и то, что наше предложение построено вокруг её решения. Нужно 2-3 предложения.

outcome — зафиксируй договорённости и срок возврата к разговору, если он прозвучал.
  Если у клиента действует договор с другой площадкой — отметь, что мы уважаем
  действующие обязательства и не предлагаем менять площадку в середине срока.
  Нужно 2-3 предложения, не одно.

Общие правила:
- в context и outcome обращайся к клиенту на «Вы», тон уважительный, без давления;
- НЕ начинай context и outcome с приветствия или обращения к компании
  («Уважаемые…», «Здравствуйте», «Дорогие коллеги») — это середина письма,
  обращение в нём уже есть выше;
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


def _generate_analysis(base_url: str, model: str, transcript: str,
                       company: str) -> tuple[dict, list[str]]:
    """Один запрос к модели вместо трёх: выжимка и оба абзаца КП сразу."""
    notes: list[str] = []
    prompt = ANALYSIS_PROMPT.format(company=company, transcript=transcript)
    best: dict | None = None

    for attempt in range(2):
        raw = _ask_model(base_url, model, prompt, max_tokens=900)
        payload = _extract_json(raw)

        if payload is None:
            prompt = (
                ANALYSIS_PROMPT.format(company=company, transcript=transcript)
                + "\n\nВАЖНО: предыдущий ответ не был корректным JSON. "
                  "Верни только объект JSON с полями summary, context, outcome."
            )
            continue

        summary = str(payload.get("summary", "")).strip()
        context = str(payload.get("context", "")).strip()
        outcome = str(payload.get("outcome", "")).strip()

        if summary and context and outcome:
            if len(split_sentences(summary)) == 3:
                return {"summary": summary, "context": context,
                        "outcome": outcome}, notes
            best = {"summary": summary, "context": context, "outcome": outcome}
            prompt = (
                ANALYSIS_PROMPT.format(company=company, transcript=transcript)
                + f"\n\nВАЖНО: в поле summary было "
                  f"{len(split_sentences(summary))} предложений. "
                  "Нужно ровно три предложения."
            )
            continue

        best = best or {"summary": summary, "context": context, "outcome": outcome}

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


def _rule_based(transcript: str, company: str) -> CallAnalysis:
    """Формирует тексты по ключевым словам, когда модель недоступна."""
    lowered = transcript.lower()

    found_competitors = [c for c in COMPETITORS if c.lower() in lowered]
    competitor = found_competitors[0] if found_competitors else ""

    objections: list[str] = []
    context_parts: list[str] = []
    for pattern, objection, context in OBJECTION_RULES:
        if re.search(pattern, lowered):
            objections.append(objection)
            context_parts.append(context)

    deadline = ""
    if re.search(r"после нового года|январ", lowered):
        deadline = "после Нового года"
    elif re.search(r"следующ\w+ (месяц|недел)", lowered):
        deadline = "в следующем месяце"
    elif re.search(r"квартал", lowered):
        deadline = "в следующем квартале"

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
    if context_parts:
        context = (
            "В разговоре Вы обозначили главное: "
            + ", ".join(context_parts[:2])
            + ". Поэтому наше предложение построено вокруг решения именно этой задачи."
        )
    else:
        context = (
            "В разговоре мы обсудили Ваш текущий порядок проведения закупок. "
            "Наше предложение построено с учётом задач Вашего отдела снабжения."
        )

    outcome = (
        "Мы с уважением относимся к Вашим действующим обязательствам и не предлагаем "
        "менять площадку в середине срока. Настоящее предложение — информационное: "
    )
    outcome += (
        f"прошу сохранить его к моменту принятия решения {deadline}."
        if deadline else
        "прошу сохранить его к моменту, когда будет рассматриваться смена площадки."
    )

    return CallAnalysis(
        summary=" ".join([first, second, third]),
        call_context=context,
        outcome=outcome,
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

    if not use_ai:
        return _rule_based(transcript, company_name)

    if not ollama_available(base_url):
        result = _rule_based(transcript, company_name)
        result.notes.insert(
            0,
            "Ollama не запущена — использован режим без ИИ. "
            "Запустите Ollama, чтобы получить более точные формулировки.",
        )
        return result

    if model not in installed_models(base_url):
        result = _rule_based(transcript, company_name)
        result.notes.insert(
            0,
            f"Модель «{model}» не установлена в Ollama — использован режим без ИИ. "
            f"Выполните: ollama pull {model}",
        )
        return result

    try:
        if progress:
            progress(15, "Модель разбирает разговор…")
        payload, notes = _generate_analysis(base_url, model, transcript, company_name)
        if progress:
            progress(100, "Анализ завершён")

    except (urllib.error.URLError, OSError, json.JSONDecodeError,
            TimeoutError, ValueError) as exc:
        result = _rule_based(transcript, company_name)
        result.notes.insert(
            0, f"Модель не ответила, использован режим без ИИ. Причина: {exc}"
        )
        return result

    fallback = _rule_based(transcript, company_name)
    context = _strip_salutation(_clean_model_output(payload["context"]))
    outcome = _strip_salutation(_clean_model_output(payload["outcome"]))

    return CallAnalysis(
        summary=_clean_model_output(payload["summary"]) or fallback.summary,
        call_context=context or fallback.call_context,
        outcome=outcome or fallback.outcome,
        used_ai=True,
        notes=notes,
    )
