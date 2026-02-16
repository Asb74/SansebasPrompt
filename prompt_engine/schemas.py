"""Esquemas de datos para tareas del motor PROM-9™."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict

TASK_ID_FORMAT = "%Y%m%d%H%M%S"


def iso_timestamp() -> str:
    """Devuelve la fecha/hora actual en formato ISO 8601 (UTC)."""
    return datetime.now(timezone.utc).isoformat()


def generate_task_id() -> str:
    """Genera un ID temporal sortable con formato YYYYMMDDHHMMSS."""
    return datetime.now().strftime(TASK_ID_FORMAT)


def parse_task_id(task_id: str) -> datetime | None:
    """Convierte un ID de tarea en datetime, devolviendo None si no es válido."""
    try:
        return datetime.strptime(task_id, TASK_ID_FORMAT)
    except ValueError:
        return None


def task_id_to_human(task_id: str) -> str:
    """Convierte un ID de tarea en fecha legible."""
    parsed = parse_task_id(task_id)
    if not parsed:
        return "Fecha desconocida"
    return parsed.strftime("%d/%m/%Y %H:%M:%S")


@dataclass
class Tarea:
    """Representa una tarea PROM-9™ con metadatos y prompt final."""

    id: str
    usuario: str
    contexto: str
    area: str
    objetivo: str
    entradas: str
    restricciones: str
    formato_salida: str
    prioridad: str
    prompt_generado: str = ""
    created_at: str = field(default_factory=iso_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa la tarea a un diccionario listo para JSON."""
        return {
            "id": self.id,
            "usuario": self.usuario,
            "contexto": self.contexto,
            "area": self.area,
            "objetivo": self.objetivo,
            "entradas": self.entradas,
            "restricciones": self.restricciones,
            "formato_salida": self.formato_salida,
            "prioridad": self.prioridad,
            "prompt_generado": self.prompt_generado,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tarea":
        """Construye una tarea desde un diccionario persistido."""
        return cls(
            id=str(data.get("id", "")),
            usuario=data.get("usuario", ""),
            contexto=data.get("contexto", ""),
            area=data.get("area", ""),
            objetivo=data.get("objetivo", ""),
            entradas=data.get("entradas", ""),
            restricciones=data.get("restricciones", ""),
            formato_salida=data.get("formato_salida", ""),
            prioridad=data.get("prioridad", "Media"),
            prompt_generado=data.get("prompt_generado", ""),
            created_at=data.get("created_at", iso_timestamp()),
        )
