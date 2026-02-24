"""Infraestructura SQLite para persistencia local de PROM-9™."""

from __future__ import annotations

import sqlite3

from .app_paths import ensure_user_dirs, get_db_path


def get_connection() -> sqlite3.Connection:
    """Crea una conexión SQLite configurada (no compartida)."""
    ensure_user_dirs()
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
        payload_json TEXT,
        prompt_generado TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    """
    with get_connection() as conn:
        conn.executescript(schema)
        def _columnas(tabla: str) -> set[str]:
            return {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({tabla})").fetchall()
            }

        columnas_perfiles = {
            row["name"] for row in conn.execute("PRAGMA table_info(perfiles)").fetchall()
        }
        for columna in (
            "nombre",
            "rol",
            "rol_base",
            "empresa",
            "ubicacion",
            "herramientas",
            "estilo",
            "nivel_tecnico",
            "prioridades",
            "extras",
            "extras_fields",
        ):
            if columna not in columnas_perfiles:
                conn.execute(f"ALTER TABLE perfiles ADD COLUMN {columna} TEXT;")

        conn.execute(
            """
            UPDATE perfiles
            SET rol = rol_base
            WHERE (rol IS NULL OR rol = '')
              AND rol_base IS NOT NULL
              AND rol_base != ''
            """
        )

        columnas_contextos = _columnas("contextos")
        for columna in (
            "nombre",
            "rol_contextual",
            "enfoque",
            "no_hacer",
            "extras_fields",
        ):
            if columna not in columnas_contextos:
                conn.execute(f"ALTER TABLE contextos ADD COLUMN {columna} TEXT;")

        columnas_contextos = _columnas("contextos")
        if "foco" in columnas_contextos and "rol_contextual" in columnas_contextos:
            conn.execute(
                """
                UPDATE contextos
                SET rol_contextual = foco
                WHERE (rol_contextual IS NULL OR rol_contextual = '')
                  AND foco IS NOT NULL
                  AND foco != ''
                """
            )

        columnas_plantillas = _columnas("plantillas")
        for columna in ("nombre", "label", "fields", "ejemplos"):
            if columna not in columnas_plantillas:
                conn.execute(f"ALTER TABLE plantillas ADD COLUMN {columna} TEXT;")

        columnas_tareas = {
            row["name"] for row in conn.execute("PRAGMA table_info(tareas)").fetchall()
        }
        if "payload_json" not in columnas_tareas:
            conn.execute("ALTER TABLE tareas ADD COLUMN payload_json TEXT;")
