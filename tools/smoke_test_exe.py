# -*- coding: utf-8 -*-
"""Проверяет, что собранный exe запускается и видит свои ресурсы."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "KPGEN ESTP" / "KPGEN ESTP.exe"


def main() -> int:
    if not EXE.exists():
        print("НЕ НАЙДЕН:", EXE)
        return 1

    print("Запускаю:", EXE.name)
    process = subprocess.Popen(
        [str(EXE)],
        cwd=str(EXE.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Окно должно продержаться несколько секунд — падение проявится сразу.
    time.sleep(12)

    if process.poll() is not None:
        out, err = process.communicate(timeout=10)
        print("ПРОГРАММА ЗАВЕРШИЛАСЬ, код:", process.returncode)
        print("stdout:", out.decode("utf-8", "ignore")[-1500:])
        print("stderr:", err.decode("utf-8", "ignore")[-2500:])
        return 1

    print("Программа работает — окно открыто.")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
    print("Проверка пройдена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
