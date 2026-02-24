"""Compat: ruta de base de datos per-user para PROM-9™."""

from pathlib import Path

from .app_paths import get_db_path as get_user_db_path


def get_db_path() -> Path:
    """Devuelve la ruta del archivo SQLite per-user."""
    return get_user_db_path()
