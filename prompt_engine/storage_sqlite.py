"""Capa de persistencia SQLite para perfiles y tareas."""

from __future__ import annotations

from typing import Any, Dict, List

from .database import get_connection
from .schemas import Tarea


def _normalize_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def _row_to_dict(row: Any) -> Dict[str, Any]:
    return dict(row) if row is not None else {}


def get_perfiles() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        perfiles_rows = conn.execute(
            """
            SELECT id, nombre, rol_base, empresa, ubicacion, estilo, nivel_tecnico
            FROM perfiles
            ORDER BY nombre COLLATE NOCASE
            """
        ).fetchall()

        perfiles: list[dict[str, Any]] = []
        for perfil_row in perfiles_rows:
            perfil = _row_to_dict(perfil_row)
            perfil_id = int(perfil["id"])

            herramientas_rows = conn.execute(
                """
                SELECT herramienta
                FROM perfil_herramientas
                WHERE perfil_id = ?
                ORDER BY orden, id
                """,
                (perfil_id,),
            ).fetchall()
            prioridades_rows = conn.execute(
                """
                SELECT prioridad
                FROM perfil_prioridades
                WHERE perfil_id = ?
                ORDER BY orden, id
                """,
                (perfil_id,),
            ).fetchall()

            perfil["herramientas"] = [row["herramienta"] for row in herramientas_rows]
            perfil["prioridades"] = [row["prioridad"] for row in prioridades_rows]
            perfiles.append(perfil)

        return perfiles


def insert_perfil(data: Dict[str, Any]) -> None:
    nombre = str(data.get("nombre", "")).strip()
    if not nombre:
        raise ValueError("El perfil requiere un nombre.")

    original_nombre = str(data.get("_original_nombre", "")).strip()
    herramientas = _normalize_lines(data.get("herramientas", []))
    prioridades = _normalize_lines(data.get("prioridades", []))

    with get_connection() as conn:
        if original_nombre and original_nombre != nombre:
            conn.execute("DELETE FROM perfiles WHERE nombre = ?", (original_nombre,))

        conn.execute(
            """
            INSERT INTO perfiles (nombre, rol_base, empresa, ubicacion, estilo, nivel_tecnico)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(nombre) DO UPDATE SET
                rol_base = excluded.rol_base,
                empresa = excluded.empresa,
                ubicacion = excluded.ubicacion,
                estilo = excluded.estilo,
                nivel_tecnico = excluded.nivel_tecnico
            """,
            (
                nombre,
                str(data.get("rol_base", "")).strip(),
                str(data.get("empresa", "")).strip(),
                str(data.get("ubicacion", "")).strip(),
                str(data.get("estilo", "")).strip(),
                str(data.get("nivel_tecnico", "")).strip(),
            ),
        )

        perfil_row = conn.execute("SELECT id FROM perfiles WHERE nombre = ?", (nombre,)).fetchone()
        if perfil_row is None:
            return
        perfil_id = int(perfil_row["id"])

        conn.execute("DELETE FROM perfil_herramientas WHERE perfil_id = ?", (perfil_id,))
        conn.execute("DELETE FROM perfil_prioridades WHERE perfil_id = ?", (perfil_id,))

        conn.executemany(
            "INSERT INTO perfil_herramientas (perfil_id, herramienta, orden) VALUES (?, ?, ?)",
            [(perfil_id, herramienta, idx) for idx, herramienta in enumerate(herramientas)],
        )
        conn.executemany(
            "INSERT INTO perfil_prioridades (perfil_id, prioridad, orden) VALUES (?, ?, ?)",
            [(perfil_id, prioridad, idx) for idx, prioridad in enumerate(prioridades)],
        )


def guardar_tarea(task: Tarea) -> None:
    data = task.to_dict()
    with get_connection() as conn:
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
                data["id"],
                data["usuario"],
                data["contexto"],
                data["area"],
                data["objetivo"],
                data["entradas"],
                data["restricciones"],
                data["formato_salida"],
                data["prioridad"],
                data["prompt_generado"],
                data["created_at"],
            ),
        )


def listar_tareas() -> List[Tarea]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM tareas ORDER BY id DESC").fetchall()
    return [Tarea.from_dict(_row_to_dict(row)) for row in rows]


def eliminar_tarea(task_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM tareas WHERE id = ?", (task_id,))
        return cursor.rowcount > 0
