"""Rutas per-user para datos persistentes de PROM-9™."""

from __future__ import annotations

import os
from pathlib import Path


APP_FOLDER = "PROM9"
DB_FILENAME = "prom9.sqlite"
TEMPLATES_FOLDER = "plantillas"


def get_user_data_dir() -> Path:
    """Devuelve el directorio de datos por usuario (%APPDATA%\\PROM9)."""
    appdata = os.environ.get("APPDATA")
    base_dir = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base_dir / APP_FOLDER


def get_db_path() -> Path:
    """Devuelve la ruta de la base de datos SQLite per-user."""
    return get_user_data_dir() / DB_FILENAME


def get_templates_dir() -> Path:
    """Devuelve la carpeta de plantillas editables per-user."""
    return get_user_data_dir() / TEMPLATES_FOLDER


def ensure_user_dirs() -> None:
    """Crea las carpetas de datos per-user si faltan."""
    get_user_data_dir().mkdir(parents=True, exist_ok=True)
    get_templates_dir().mkdir(parents=True, exist_ok=True)
