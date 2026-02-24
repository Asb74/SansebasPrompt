"""Capa de persistencia SQLite para PROM-9™."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .db_config import get_db_path
from .schemas import Tarea


def _connect() -> sqlite3.Connection:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    print(">>> DB PATH EN USO:", db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _loads_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def _dumps_json(value: Any, default: Any) -> str:
    payload = default if value is None else value
    return json.dumps(payload, ensure_ascii=False)


def _loads_json_object(value: Any) -> Dict[str, Any]:
    payload = _loads_json(value, {})
    if isinstance(payload, dict):
        return payload
    return {}


def _loads_json_list(value: Any) -> List[Dict[str, Any]]:
    payload = _loads_json(value, [])
    if not isinstance(payload, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            cleaned.append(item)
    return cleaned


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _perfil_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    rol = _text(row["rol"])
    rol_base = _text(row["rol_base"])
    if not rol:
        rol = rol_base
    if not rol_base:
        rol_base = rol
    try:
        extras_raw = row["extras"]
    except (KeyError, IndexError):
        extras_raw = None
    try:
        extras_fields_raw = row["extras_fields"]
    except (KeyError, IndexError):
        extras_fields_raw = None
    return {
        "nombre": _text(row["nombre"]),
        "rol": rol,
        "rol_base": rol_base,
        "empresa": _text(row["empresa"]),
        "ubicacion": _text(row["ubicacion"]),
        "herramientas": _loads_json(row["herramientas"], []),
        "estilo": _text(row["estilo"]),
        "nivel_tecnico": _text(row["nivel_tecnico"]),
        "prioridades": _loads_json(row["prioridades"], []),
        "extras": _loads_json_object(extras_raw),
        "extras_fields": _loads_json_list(extras_fields_raw),
    }


def _contexto_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    try:
        no_hacer_raw = row["no_hacer"]
    except (KeyError, IndexError):
        no_hacer_raw = None
    try:
        extras_fields_raw = row["extras_fields"]
    except (KeyError, IndexError):
        extras_fields_raw = None
    return {
        "nombre": _text(row["nombre"]),
        "rol_contextual": _text(row["rol_contextual"]),
        "enfoque": _loads_json(row["enfoque"], []),
        "no_hacer": _loads_json(no_hacer_raw, []),
        "extras_fields": _loads_json_list(extras_fields_raw),
    }


def _plantilla_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "nombre": _text(row["nombre"]),
        "label": _text(row["label"]),
        "fields": _loads_json(row["fields"], []),
        "ejemplos": _loads_json(row["ejemplos"], []),
    }


def cargar_perfiles() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM perfiles").fetchall()
    return [_perfil_from_row(row) for row in rows]


def guardar_perfiles(perfiles: List[Dict[str, Any]]) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM perfiles")
        for perfil in perfiles:
            rol = _text(perfil.get("rol")) or _text(perfil.get("rol_base"))
            rol_base = _text(perfil.get("rol_base")) or _text(perfil.get("rol"))
            conn.execute(
                """
                INSERT INTO perfiles (
                    nombre, rol, rol_base, empresa, ubicacion,
                    herramientas, estilo, nivel_tecnico, prioridades, extras, extras_fields
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _text(perfil.get("nombre")),
                    rol,
                    rol_base,
                    _text(perfil.get("empresa")),
                    _text(perfil.get("ubicacion")),
                    _dumps_json(perfil.get("herramientas"), []),
                    _text(perfil.get("estilo")),
                    _text(perfil.get("nivel_tecnico")),
                    _dumps_json(perfil.get("prioridades"), []),
                    _dumps_json(perfil.get("extras"), {}),
                    _dumps_json(perfil.get("extras_fields"), []),
                ),
            )


def cargar_contextos() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM contextos").fetchall()
    return [_contexto_from_row(row) for row in rows]


def guardar_contextos(contextos: List[Dict[str, Any]]) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM contextos")
        for contexto in contextos:
            conn.execute(
                """
                INSERT INTO contextos (nombre, rol_contextual, enfoque, no_hacer, extras_fields)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _text(contexto.get("nombre")),
                    _text(contexto.get("rol_contextual")),
                    _dumps_json(contexto.get("enfoque"), []),
                    _dumps_json(contexto.get("no_hacer"), []),
                    _dumps_json(contexto.get("extras_fields"), []),
                ),
            )


def cargar_plantillas() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM plantillas").fetchall()
    return [_plantilla_from_row(row) for row in rows]


def guardar_plantillas(plantillas: List[Dict[str, Any]]) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM plantillas")
        for plantilla in plantillas:
            conn.execute(
                """
                INSERT INTO plantillas (nombre, label, fields, ejemplos)
                VALUES (?, ?, ?, ?)
                """,
                (
                    _text(plantilla.get("nombre")),
                    _text(plantilla.get("label")),
                    _dumps_json(plantilla.get("fields"), []),
                    _dumps_json(plantilla.get("ejemplos"), []),
                ),
            )


def actualizar_registro_json(path: Path, nombre: str, payload: Dict[str, Any]) -> bool:
    del path  # Compatibilidad con firma JSON legada.

    with _connect() as conn:
        if conn.execute("SELECT 1 FROM perfiles WHERE nombre = ?", (_text(nombre),)).fetchone():
            rol = _text(payload.get("rol")) or _text(payload.get("rol_base"))
            rol_base = _text(payload.get("rol_base")) or _text(payload.get("rol"))
            cursor = conn.execute(
                """
                UPDATE perfiles
                SET nombre = ?, rol = ?, rol_base = ?, empresa = ?, ubicacion = ?,
                    herramientas = ?, estilo = ?, nivel_tecnico = ?, prioridades = ?, extras = ?, extras_fields = ?
                WHERE nombre = ?
                """,
                (
                    _text(payload.get("nombre")) or _text(nombre),
                    rol,
                    rol_base,
                    _text(payload.get("empresa")),
                    _text(payload.get("ubicacion")),
                    _dumps_json(payload.get("herramientas"), []),
                    _text(payload.get("estilo")),
                    _text(payload.get("nivel_tecnico")),
                    _dumps_json(payload.get("prioridades"), []),
                    _dumps_json(payload.get("extras"), {}),
                    _dumps_json(payload.get("extras_fields"), []),
                    _text(nombre),
                ),
            )
            return cursor.rowcount > 0

        if conn.execute("SELECT 1 FROM contextos WHERE nombre = ?", (_text(nombre),)).fetchone():
            cursor = conn.execute(
                """
                UPDATE contextos
                SET nombre = ?, rol_contextual = ?, enfoque = ?, no_hacer = ?, extras_fields = ?
                WHERE nombre = ?
                """,
                (
                    _text(payload.get("nombre")) or _text(nombre),
                    _text(payload.get("rol_contextual")),
                    _dumps_json(payload.get("enfoque"), []),
                    _dumps_json(payload.get("no_hacer"), []),
                    _dumps_json(payload.get("extras_fields"), []),
                    _text(nombre),
                ),
            )
            return cursor.rowcount > 0

        if conn.execute("SELECT 1 FROM plantillas WHERE nombre = ?", (_text(nombre),)).fetchone():
            cursor = conn.execute(
                """
                UPDATE plantillas
                SET nombre = ?, label = ?, fields = ?, ejemplos = ?
                WHERE nombre = ?
                """,
                (
                    _text(payload.get("nombre")) or _text(nombre),
                    _text(payload.get("label")),
                    _dumps_json(payload.get("fields"), []),
                    _dumps_json(payload.get("ejemplos"), []),
                    _text(nombre),
                ),
            )
            return cursor.rowcount > 0

    return False


def insertar_registro_json(path: Path, payload: Dict[str, Any]) -> None:
    del path  # Compatibilidad con firma JSON legada.

    keys = set(payload.keys())
    with _connect() as conn:
        if {"rol_contextual", "enfoque", "no_hacer", "extras_fields"} & keys:
            conn.execute(
                """
                INSERT INTO contextos (nombre, rol_contextual, enfoque, no_hacer, extras_fields)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _text(payload.get("nombre")),
                    _text(payload.get("rol_contextual")),
                    _dumps_json(payload.get("enfoque"), []),
                    _dumps_json(payload.get("no_hacer"), []),
                    _dumps_json(payload.get("extras_fields"), []),
                ),
            )
            return

        if {"fields", "ejemplos", "label"} & keys:
            conn.execute(
                "INSERT INTO plantillas (nombre, label, fields, ejemplos) VALUES (?, ?, ?, ?)",
                (
                    _text(payload.get("nombre")),
                    _text(payload.get("label")),
                    _dumps_json(payload.get("fields"), []),
                    _dumps_json(payload.get("ejemplos"), []),
                ),
            )
            return

        conn.execute(
            """
            INSERT INTO perfiles (
                nombre, rol, rol_base, empresa, ubicacion,
                herramientas, estilo, nivel_tecnico, prioridades, extras, extras_fields
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _text(payload.get("nombre")),
                _text(payload.get("rol")) or _text(payload.get("rol_base")),
                _text(payload.get("rol_base")) or _text(payload.get("rol")),
                _text(payload.get("empresa")),
                _text(payload.get("ubicacion")),
                _dumps_json(payload.get("herramientas"), []),
                _text(payload.get("estilo")),
                _text(payload.get("nivel_tecnico")),
                _dumps_json(payload.get("prioridades"), []),
                _dumps_json(payload.get("extras"), {}),
                _dumps_json(payload.get("extras_fields"), []),
            ),
        )


def listar_tareas() -> List[Tarea]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM tareas ORDER BY id DESC").fetchall()

    return [
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
        for row in rows
    ]


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


def sobrescribir_tareas(tareas: List[Tarea]) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM tareas")
        for tarea in tareas:
            data = tarea.to_dict()
            conn.execute(
                """
                INSERT INTO tareas (
                    id, usuario, contexto, area, objetivo,
                    entradas, restricciones, formato_salida,
                    prioridad, prompt_generado, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def eliminar_tarea(tarea_id: str) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM tareas WHERE id = ?", (_text(tarea_id),))
        return cursor.rowcount > 0


def buscar_tarea_por_id(tarea_id: str) -> Optional[Tarea]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tareas WHERE id = ?", (_text(tarea_id),)).fetchone()

    if row is None:
        return None

    return Tarea.from_dict(
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


# Alias y helpers de compatibilidad con código UI existente.
get_perfiles = cargar_perfiles
get_contextos = cargar_contextos
get_plantillas = cargar_plantillas


def insert_perfil(payload: Dict[str, Any]) -> None:
    insertar_registro_json(Path("perfiles.json"), payload)


def insert_contexto(payload: Dict[str, Any]) -> None:
    insertar_registro_json(Path("contextos.json"), payload)


def update_perfil(nombre_original: str, payload: Dict[str, Any]) -> bool:
    return actualizar_registro_json(Path("perfiles.json"), nombre_original, payload)


def update_contexto(nombre_original: str, payload: Dict[str, Any]) -> bool:
    return actualizar_registro_json(Path("contextos.json"), nombre_original, payload)


def upsert_plantilla(payload: Dict[str, Any]) -> None:
    nombre = _text(payload.get("nombre"))
    if not actualizar_registro_json(Path("plantillas.json"), nombre, payload):
        insertar_registro_json(Path("plantillas.json"), payload)
