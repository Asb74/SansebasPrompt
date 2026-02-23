"""Infraestructura SQLite para persistencia local de PROM-9™."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

APP_DIR_NAME = "Prom9"
DB_FILENAME = "prom9.db"


def _local_appdata_dir() -> Path:
    """Devuelve la carpeta local de datos de aplicación compatible con Windows."""
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata)
    # Fallback útil para entornos no-Windows (tests/CI)
    return Path.home() / "AppData" / "Local"


def get_db_path() -> Path:
    """Ruta absoluta al archivo de base de datos local."""
    base_dir = _local_appdata_dir() / APP_DIR_NAME
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / DB_FILENAME


def get_connection() -> sqlite3.Connection:
    """Crea una conexión SQLite configurada (no compartida)."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db() -> None:
    """Inicializa el esquema SQLite si aún no existe."""
    schema = """
    CREATE TABLE IF NOT EXISTS perfiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        rol_base TEXT,
        empresa TEXT,
        ubicacion TEXT,
        estilo TEXT,
        nivel_tecnico TEXT
    );

    CREATE TABLE IF NOT EXISTS perfil_herramientas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        perfil_id INTEGER NOT NULL,
        herramienta TEXT NOT NULL,
        orden INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (perfil_id) REFERENCES perfiles(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS perfil_prioridades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        perfil_id INTEGER NOT NULL,
        prioridad TEXT NOT NULL,
        orden INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (perfil_id) REFERENCES perfiles(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS contextos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        foco TEXT,
        restricciones TEXT
    );

    CREATE TABLE IF NOT EXISTS contexto_enfoques (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contexto_id INTEGER NOT NULL,
        enfoque TEXT NOT NULL,
        orden INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (contexto_id) REFERENCES contextos(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS contexto_no_hacer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contexto_id INTEGER NOT NULL,
        no_hacer TEXT NOT NULL,
        orden INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (contexto_id) REFERENCES contextos(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS plantillas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        label TEXT
    );

    CREATE TABLE IF NOT EXISTS plantilla_campos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plantilla_id INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        etiqueta TEXT,
        ayuda TEXT,
        placeholder TEXT,
        orden INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (plantilla_id) REFERENCES plantillas(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS tareas (
        id TEXT PRIMARY KEY,
        usuario TEXT NOT NULL,
        contexto TEXT NOT NULL,
        area TEXT NOT NULL,
        objetivo TEXT NOT NULL,
        entradas TEXT NOT NULL,
        restricciones TEXT NOT NULL,
        formato_salida TEXT NOT NULL,
        prioridad TEXT NOT NULL,
        prompt_generado TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    """
    with get_connection() as conn:
        conn.executescript(schema)
