"""Paquete de plantillas PROM-9™."""

from .contabilidad import render_contabilidad
from .gestion import render_gestion
from .it import render_it
from .ventas import render_ventas

__all__ = [
    "render_it",
    "render_ventas",
    "render_contabilidad",
    "render_gestion",
]
