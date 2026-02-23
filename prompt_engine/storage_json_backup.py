"""Capa de persistencia para perfiles, contextos, plantillas e historial de tareas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import Tarea

BASE_DIR = Path(__file__).resolve().parent
PERFILES_FILE = BASE_DIR / "perfiles.json"
CONTEXTOS_FILE = BASE_DIR / "contextos.json"
PLANTILLAS_FILE = BASE_DIR / "plantillas" / "plantillas.json"
HISTORIAL_FILE = BASE_DIR / "historial" / "tareas.json"


def _read_json(path: Path, default: Any):
    """Lee un archivo JSON y devuelve un valor por defecto si no existe."""
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: Any) -> None:
    """Escribe contenido JSON asegurando la carpeta de destino."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def cargar_perfiles() -> List[Dict[str, str]]:
    return _read_json(PERFILES_FILE, [])


def cargar_contextos() -> List[Dict[str, str]]:
    return _read_json(CONTEXTOS_FILE, [])


def cargar_plantillas() -> List[Dict[str, Any]]:
    return _read_json(PLANTILLAS_FILE, [])


def guardar_plantillas(plantillas: List[Dict[str, Any]]) -> None:
    _write_json(PLANTILLAS_FILE, plantillas)


def guardar_perfiles(perfiles: List[Dict[str, str]]) -> None:
    _write_json(PERFILES_FILE, perfiles)


def guardar_contextos(contextos: List[Dict[str, str]]) -> None:
    _write_json(CONTEXTOS_FILE, contextos)


def actualizar_registro_json(path: Path, nombre: str, payload: Dict[str, Any]) -> bool:
    """Actualiza un registro JSON por campo nombre."""
    data = _read_json(path, [])
    for idx, item in enumerate(data):
        if item.get("nombre") == nombre:
            data[idx] = payload
            _write_json(path, data)
            return True
    return False


def insertar_registro_json(path: Path, payload: Dict[str, Any]) -> None:
    """Inserta un nuevo registro JSON en un listado."""
    data = _read_json(path, [])
    data.append(payload)
    _write_json(path, data)


def listar_tareas() -> List[Tarea]:
    data = _read_json(HISTORIAL_FILE, [])
    tareas = [Tarea.from_dict(item) for item in data]
    tareas.sort(key=lambda t: t.id, reverse=True)
    return tareas


def guardar_tarea(tarea: Tarea) -> None:
    """Guarda/actualiza una tarea y mantiene orden descendente por ID."""
    tareas = listar_tareas()
    found = False
    for idx, stored in enumerate(tareas):
        if stored.id == tarea.id:
            tareas[idx] = tarea
            found = True
            break
    if not found:
        tareas.append(tarea)
    tareas.sort(key=lambda item: item.id, reverse=True)
    _write_json(HISTORIAL_FILE, [t.to_dict() for t in tareas])


def sobrescribir_tareas(tareas: List[Tarea]) -> None:
    tareas.sort(key=lambda item: item.id, reverse=True)
    _write_json(HISTORIAL_FILE, [t.to_dict() for t in tareas])


def eliminar_tarea(tarea_id: str) -> bool:
    tareas = listar_tareas()
    filtered = [item for item in tareas if item.id != tarea_id]
    if len(filtered) == len(tareas):
        return False
    _write_json(HISTORIAL_FILE, [t.to_dict() for t in filtered])
    return True


def buscar_tarea_por_id(tarea_id: str) -> Optional[Tarea]:
    for tarea in listar_tareas():
        if tarea.id == tarea_id:
            return tarea
    return None
