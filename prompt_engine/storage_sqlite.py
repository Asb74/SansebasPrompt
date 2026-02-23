"""Capa de persistencia SQLite para PROM-9™ (reemplazo de JSON)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from .schemas import Tarea

BASE_DIR = Path(__file__).resolve().parent
DB_FILENAME = "prom9.sqlite"


def _candidate_db_paths() -> list[Path]:
    return [
        BASE_DIR / DB_FILENAME,
        Path.cwd() / DB_FILENAME,
        BASE_DIR.parent / DB_FILENAME,
    ]


def _get_db_path() -> Path:
    for candidate in _candidate_db_paths():
        if candidate.exists():
            return candidate
    # Fallback: ruta por defecto en el paquete.
    return BASE_DIR / DB_FILENAME


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _loads_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    text = str(value).strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def _dumps_json(value: Any, fallback: Any) -> str:
    payload = fallback if value is None else value
    return json.dumps(payload, ensure_ascii=False)


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def get_perfiles() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, nombre, rol, rol_base, empresa, ubicacion,
                   herramientas, estilo, nivel_tecnico, prioridades
            FROM perfiles
            ORDER BY nombre COLLATE NOCASE
            """
        ).fetchall()

    perfiles: list[dict[str, Any]] = []
    for row in rows:
        perfil = {
            "id": row["id"],
            "nombre": _text(row["nombre"]),
            "rol": _text(row["rol"]),
            "rol_base": _text(row["rol_base"]),
            "empresa": _text(row["empresa"]),
            "ubicacion": _text(row["ubicacion"]),
            "herramientas": _loads_json(row["herramientas"], []),
            "estilo": _text(row["estilo"]),
            "nivel_tecnico": _text(row["nivel_tecnico"]),
            "prioridades": _loads_json(row["prioridades"], []),
        }
        if not perfil["rol"]:
            perfil["rol"] = perfil["rol_base"]
        if not perfil["rol_base"]:
            perfil["rol_base"] = perfil["rol"]
        perfiles.append(perfil)
    return perfiles


def get_contextos() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, nombre, rol_contextual, enfoque
            FROM contextos
            ORDER BY nombre COLLATE NOCASE
            """
        ).fetchall()

    contextos: list[dict[str, Any]] = []
    for row in rows:
        contexto = {
            "id": row["id"],
            "nombre": _text(row["nombre"]),
            "rol_contextual": _text(row["rol_contextual"]),
            "enfoque": _loads_json(row["enfoque"], []),
        }
        contextos.append(contexto)
    return contextos


def get_plantillas() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, nombre, label, fields, ejemplos
            FROM plantillas
            ORDER BY nombre COLLATE NOCASE
            """
        ).fetchall()

    plantillas: list[dict[str, Any]] = []
    for row in rows:
        plantillas.append(
            {
                "id": row["id"],
                "nombre": _text(row["nombre"]),
                "label": _text(row["label"]),
                "fields": _loads_json(row["fields"], []),
                "ejemplos": _loads_json(row["ejemplos"], []),
            }
        )
    return plantillas


def guardar_tarea(tarea: Tarea) -> None:
    data = tarea.to_dict()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tareas (
                id, usuario, contexto, area, objetivo,
                entradas, restricciones, formato_salida,
                prioridad, prompt_generado, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                usuario = excluded.usuario,
                contexto = excluded.contexto,
                area = excluded.area,
                objetivo = excluded.objetivo,
                entradas = excluded.entradas,
                restricciones = excluded.restricciones,
                formato_salida = excluded.formato_salida,
                prioridad = excluded.prioridad,
                prompt_generado = excluded.prompt_generado,
                created_at = excluded.created_at
            """,
            (
                _text(data.get("id")),
                _text(data.get("usuario")),
                _text(data.get("contexto")),
                _text(data.get("area")),
                _text(data.get("objetivo")),
                _text(data.get("entradas")),
                _text(data.get("restricciones")),
                _text(data.get("formato_salida")),
                _text(data.get("prioridad"), "Media"),
                _text(data.get("prompt_generado")),
                _text(data.get("created_at")),
            ),
        )


def listar_tareas() -> List[Tarea]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM tareas ORDER BY id DESC").fetchall()

    tareas: list[Tarea] = []
    for row in rows:
        tareas.append(
            Tarea.from_dict(
                {
                    "id": _text(row["id"]),
                    "usuario": _text(row["usuario"]),
                    "contexto": _text(row["contexto"]),
                    "area": _text(row["area"]),
                    "objetivo": _text(row["objetivo"]),
                    "entradas": _text(row["entradas"]),
                    "restricciones": _text(row["restricciones"]),
                    "formato_salida": _text(row["formato_salida"]),
                    "prioridad": _text(row["prioridad"], "Media"),
                    "prompt_generado": _text(row["prompt_generado"]),
                    "created_at": _text(row["created_at"]),
                }
            )
        )
    return tareas


def eliminar_tarea(tarea_id: str) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM tareas WHERE id = ?", (_text(tarea_id),))
        return cursor.rowcount > 0


def insert_perfil(payload: Dict[str, Any]) -> None:
    nombre = _text(payload.get("nombre")).strip()
    if not nombre:
        raise ValueError("El perfil requiere nombre.")

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO perfiles (
                nombre, rol, rol_base, empresa, ubicacion,
                herramientas, estilo, nivel_tecnico, prioridades
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nombre,
                _text(payload.get("rol")) or _text(payload.get("rol_base")),
                _text(payload.get("rol_base")) or _text(payload.get("rol")),
                _text(payload.get("empresa")),
                _text(payload.get("ubicacion")),
                _dumps_json(payload.get("herramientas"), []),
                _text(payload.get("estilo")),
                _text(payload.get("nivel_tecnico")),
                _dumps_json(payload.get("prioridades"), []),
            ),
        )


def update_perfil(nombre_original: str, payload: Dict[str, Any]) -> bool:
    nombre_objetivo = _text(payload.get("nombre")).strip()
    if not nombre_objetivo:
        return False

    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE perfiles
            SET nombre = ?,
                rol = ?,
                rol_base = ?,
                empresa = ?,
                ubicacion = ?,
                herramientas = ?,
                estilo = ?,
                nivel_tecnico = ?,
                prioridades = ?
            WHERE nombre = ?
            """,
            (
                nombre_objetivo,
                _text(payload.get("rol")) or _text(payload.get("rol_base")),
                _text(payload.get("rol_base")) or _text(payload.get("rol")),
                _text(payload.get("empresa")),
                _text(payload.get("ubicacion")),
                _dumps_json(payload.get("herramientas"), []),
                _text(payload.get("estilo")),
                _text(payload.get("nivel_tecnico")),
                _dumps_json(payload.get("prioridades"), []),
                _text(nombre_original),
            ),
        )
        return cursor.rowcount > 0


def insert_contexto(payload: Dict[str, Any]) -> None:
    nombre = _text(payload.get("nombre")).strip()
    if not nombre:
        raise ValueError("El contexto requiere nombre.")

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO contextos (nombre, rol_contextual, enfoque)
            VALUES (?, ?, ?)
            """,
            (
                nombre,
                _text(payload.get("rol_contextual")),
                _dumps_json(payload.get("enfoque"), []),
            ),
        )


def update_contexto(nombre_original: str, payload: Dict[str, Any]) -> bool:
    nombre_objetivo = _text(payload.get("nombre")).strip()
    if not nombre_objetivo:
        return False

    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE contextos
            SET nombre = ?,
                rol_contextual = ?,
                enfoque = ?
            WHERE nombre = ?
            """,
            (
                nombre_objetivo,
                _text(payload.get("rol_contextual")),
                _dumps_json(payload.get("enfoque"), []),
                _text(nombre_original),
            ),
        )
        return cursor.rowcount > 0


def upsert_plantilla(payload: Dict[str, Any]) -> None:
    nombre = _text(payload.get("nombre")).strip()
    if not nombre:
        raise ValueError("La plantilla requiere nombre.")

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO plantillas (nombre, label, fields, ejemplos)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(nombre) DO UPDATE SET
                label = excluded.label,
                fields = excluded.fields,
                ejemplos = excluded.ejemplos
            """,
            (
                nombre,
                _text(payload.get("label")) or nombre.title(),
                _dumps_json(payload.get("fields"), []),
                _dumps_json(payload.get("ejemplos"), []),
            ),
        )
