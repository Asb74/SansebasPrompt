"""Capa de persistencia para perfiles, contextos e historial de tareas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .schemas import Tarea

BASE_DIR = Path(__file__).resolve().parent
PERFILES_FILE = BASE_DIR / "perfiles.json"
CONTEXTOS_FILE = BASE_DIR / "contextos.json"
HISTORIAL_FILE = BASE_DIR / "historial" / "tareas.json"


def _read_json(path: Path, default):
    """Lee un archivo JSON y devuelve un valor por defecto si no existe."""
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload) -> None:
    """Escribe contenido JSON asegurando la carpeta de destino."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def cargar_perfiles() -> List[Dict[str, str]]:
    """Carga la lista de perfiles disponibles."""
    return _read_json(PERFILES_FILE, [])


def cargar_contextos() -> List[Dict[str, str]]:
    """Carga la lista de contextos configurados."""
    return _read_json(CONTEXTOS_FILE, [])


def listar_tareas() -> List[Tarea]:
    """Recupera todo el historial de tareas como objetos Tarea."""
    data = _read_json(HISTORIAL_FILE, [])
    return [Tarea.from_dict(item) for item in data]


def guardar_tarea(tarea: Tarea) -> None:
    """Añade una nueva tarea al historial persistido."""
    tareas = listar_tareas()
    tareas.append(tarea)
    _write_json(HISTORIAL_FILE, [t.to_dict() for t in tareas])


def sobrescribir_tareas(tareas: List[Tarea]) -> None:
    """Sobrescribe por completo el historial de tareas."""
    _write_json(HISTORIAL_FILE, [t.to_dict() for t in tareas])


def buscar_tarea_por_id(tarea_id: str) -> Optional[Tarea]:
    """Busca una tarea por ID y devuelve el primer resultado o None."""
    for tarea in listar_tareas():
        if tarea.id == tarea_id:
            return tarea
    return None
