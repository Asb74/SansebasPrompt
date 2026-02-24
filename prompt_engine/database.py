"""Infraestructura SQLite para persistencia local de PROM-9™."""

from __future__ import annotations

import sqlite3

from .db_config import get_db_path


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
        print(">>> Verificando columnas de perfiles...")
        columnas_perfiles = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(perfiles)").fetchall()
        }
        print(">>> Columnas actuales en perfiles:", columnas_perfiles)
        if "extras" not in columnas_perfiles:
            print(">>> Añadiendo columna 'extras' a perfiles")
            conn.execute("ALTER TABLE perfiles ADD COLUMN extras TEXT;")
            print(">>> Columna 'extras' añadida correctamente")
        if "extras_fields" not in columnas_perfiles:
            print(">>> Añadiendo columna 'extras_fields' a perfiles")
            conn.execute("ALTER TABLE perfiles ADD COLUMN extras_fields TEXT;")
            print(">>> Columna 'extras_fields' añadida correctamente")

        columnas_contextos = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(contextos)").fetchall()
        }
        if "rol_contextual" not in columnas_contextos:
            conn.execute("ALTER TABLE contextos ADD COLUMN rol_contextual TEXT;")
        if "enfoque" not in columnas_contextos:
            conn.execute("ALTER TABLE contextos ADD COLUMN enfoque TEXT;")
        if "no_hacer" not in columnas_contextos:
            conn.execute("ALTER TABLE contextos ADD COLUMN no_hacer TEXT;")
        if "extras_fields" not in columnas_contextos:
            conn.execute("ALTER TABLE contextos ADD COLUMN extras_fields TEXT;")

        if "foco" in columnas_contextos and "rol_contextual" in {
            row["name"]
            for row in conn.execute("PRAGMA table_info(contextos)").fetchall()
        }:
            conn.execute(
                """
                UPDATE contextos
                SET rol_contextual = foco
                WHERE (rol_contextual IS NULL OR rol_contextual = '')
                  AND foco IS NOT NULL
                """
            )
