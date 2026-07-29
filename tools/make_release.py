# -*- coding: utf-8 -*-
"""Создание релиза на GitHub с прикреплённым установщиком.

Доступ берётся из системного хранилища Windows — того же, которым
работает `git push`. Значение токена нигде не печатается.
"""
from __future__ import annotations

import json
import mimetypes
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OWNER = "Shutmaxx"
REPO = "KPGen"
TAG = "v1.0"
TITLE = "KPGEN ESTP 1.0"
ASSET = Path(__file__).resolve().parents[1] / "dist_installer" / "KPGEN_ESTP_Setup.exe"

BODY = """Программа готовит коммерческое предложение, презентацию и выжимку
разговора для CRM по аудиозаписи звонка.

## Установка

Скачайте `KPGEN_ESTP_Setup.exe` и запустите. Требуются права администратора.
Python устанавливать не нужно.

При первом запуске Windows может показать окно SmartScreen — программа
не подписана сертификатом разработчика. Нажмите «Подробнее» →
«Выполнить в любом случае».

## Что умеет

- распознаёт речь локально, запись никуда не передаётся;
- разбирает разговор моделью Qwen через Ollama;
- работает и без Ollama — тексты составляются по правилам;
- подтягивает сведения о компании по ИНН из реестра;
- подставляет данные в фирменные шаблоны КП и презентации;
- добавляет слайд с преимуществами под задачи клиента;
- готовит выжимку из трёх предложений для CRM.

## Включение ИИ (по желанию)

Установите [Ollama](https://ollama.com) и выполните:

```
ollama pull qwen2.5:7b
```

Модель занимает около 4,7 ГБ и скачивается один раз.

## Первый разбор записи

При первой обработке скачается модель распознавания речи (~1,5 ГБ).
Дальше программа работает автономно."""


def get_token() -> str:
    """Берёт сохранённый доступ из хранилища Windows."""
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, timeout=30,
    )
    for line in result.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise RuntimeError(
        "Не удалось получить сохранённый доступ к GitHub. "
        "Выполните `gh auth login` и повторите."
    )


def api(method: str, url: str, token: str, data: bytes | None = None,
        content_type: str = "application/json", timeout: int = 900) -> dict:
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "kpgen-release-script")
    if data is not None:
        request.add_header("Content-Type", content_type)
        request.add_header("Content-Length", str(len(data)))

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError(f"GitHub ответил {exc.code}: {detail}") from exc


def main() -> int:
    if not ASSET.exists():
        print("Не найден установщик:", ASSET)
        return 1

    token = get_token()
    base = f"https://api.github.com/repos/{OWNER}/{REPO}"

    # Если релиз уже существует — используем его, иначе создаём.
    try:
        release = api("GET", f"{base}/releases/tags/{TAG}", token)
        print("Релиз уже существует, обновляю вложения.")
    except RuntimeError:
        release = api("POST", f"{base}/releases", token, data=json.dumps({
            "tag_name": TAG,
            "name": TITLE,
            "body": BODY,
            "draft": False,
            "prerelease": False,
        }).encode("utf-8"))
        print("Релиз создан:", release.get("html_url"))

    # Удаляем прежний файл с тем же именем, чтобы не плодить дубли.
    for asset in release.get("assets", []):
        if asset.get("name") == ASSET.name:
            api("DELETE", f"{base}/releases/assets/{asset['id']}", token)
            print("Прежний файл удалён.")

    size_mb = ASSET.stat().st_size / 1024 / 1024
    print(f"Загружаю {ASSET.name} ({size_mb:.0f} МБ), это займёт несколько минут…")

    upload_url = release["upload_url"].split("{")[0] + f"?name={ASSET.name}"
    content_type = mimetypes.guess_type(ASSET.name)[0] or "application/octet-stream"
    uploaded = api("POST", upload_url, token,
                   data=ASSET.read_bytes(), content_type=content_type)

    print("Файл загружен:", uploaded.get("browser_download_url"))
    print("Готово:", release.get("html_url"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
