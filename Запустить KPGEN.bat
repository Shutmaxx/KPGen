@echo off
chcp 65001 >nul
title KPGEN ESTP (запуск из исходников)
cd /d "%~dp0"

echo Запуск KPGEN ESTP из исходного кода...
echo Для обычной работы используйте установленную программу: Пуск - KPGEN ESTP
echo.

rem --- Проверка Python ---
py --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] На этом компьютере не найден Python.
    echo.
    echo Этот файл запускает программу из исходного кода и требует Python.
    echo Если вы просто хотите пользоваться программой - установите её
    echo через KPGEN_ESTP_Setup.exe, Python тогда не нужен.
    echo.
    echo Либо установите Python с сайта python.org
    echo.
    pause
    exit /b 1
)

rem --- Проверка библиотек ---
py -c "import PySide6, docx, pptx" >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Не хватает библиотек Python.
    echo.
    echo Установите их командой:
    echo    py -m pip install PySide6 python-docx python-pptx faster-whisper
    echo.
    pause
    exit /b 1
)

rem --- Запуск с показом настоящей ошибки ---
py app\main.py
set EXITCODE=%errorlevel%

if %EXITCODE% neq 0 (
    echo.
    echo [ОШИБКА] Программа завершилась с кодом %EXITCODE%.
    echo Текст ошибки показан выше - пришлите его разработчику.
    echo.
    pause
)
exit /b %EXITCODE%
