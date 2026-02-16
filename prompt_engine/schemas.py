"""Esquemas de datos para tareas del motor PROM-9™."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict


def iso_timestamp() -> str:
    """Devuelve la fecha/hora actual en formato ISO 8601 (UTC)."""
    return datetime.now(timezone.utc).isoformat()


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
            id=data["id"],
            usuario=data["usuario"],
            contexto=data["contexto"],
            area=data["area"],
            objetivo=data["objetivo"],
            entradas=data["entradas"],
            restricciones=data["restricciones"],
            formato_salida=data["formato_salida"],
            prioridad=data["prioridad"],
            prompt_generado=data.get("prompt_generado", ""),
            created_at=data.get("created_at", iso_timestamp()),
        )
