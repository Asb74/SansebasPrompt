@echo off
cls
echo ============================================
echo         BUILD PROM-9™ EXECUTABLE
echo ============================================

REM === CONFIGURACION ===
set APP_NAME=PromptEngine_PROM9
set MAIN_FILE=main.py
set ICON_FILE=icono_app.ico

REM Carpeta con seed opcional
set SEED_DIR=seed
set SEED_DB=prom9_seed.sqlite

REM === DETECTAR PYTHON ===
set PYTHON_EXE=

IF EXIST "C:\Python313\python.exe" (
    set PYTHON_EXE=C:\Python313\python.exe
)

IF EXIST "C:\Python310\python.exe" (
    set PYTHON_EXE=C:\Python310\python.exe
)

IF "%PYTHON_EXE%"=="" (
    echo ERROR: No se encontro Python en C:\Python310 ni C:\Python313
    pause
    exit /b
)

echo Usando Python en: %PYTHON_EXE%
echo.

REM === LIMPIAR BUILDS ANTERIORES ===
echo Limpiando builds anteriores...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del %APP_NAME%.spec 2>nul

echo.
echo Compilando...

REM === BUILD PYINSTALLER ===
"%PYTHON_EXE%" -m PyInstaller ^
--noconfirm ^
--clean ^
--onefile ^
--windowed ^
--name %APP_NAME% ^
--icon %ICON_FILE% ^
--add-data "%ICON_FILE%;." ^
--add-data "prompt_engine;prompt_engine" ^
--add-data "%SEED_DIR%;%SEED_DIR%" ^
--hidden-import sounddevice ^
--hidden-import numpy ^
--hidden-import openai ^
--collect-all sounddevice ^
--collect-all numpy ^
--collect-all openai ^
%MAIN_FILE%

echo.
echo ============================================
echo        BUILD FINALIZADO CORRECTAMENTE
echo ============================================
echo.

IF EXIST "dist\%APP_NAME%.exe" (
    echo Ejecutable generado en:
    echo %CD%\dist\%APP_NAME%.exe
) ELSE (
    echo ERROR: No se genero el ejecutable.
)

echo.
pause