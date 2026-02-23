"""Configuración de ruta de base de datos para PROM-9™."""

from pathlib import Path


def get_db_path() -> Path:
    """Devuelve la ruta del archivo SQLite del proyecto."""
    return Path(__file__).resolve().parent.parent / "prom9.sqlite"

