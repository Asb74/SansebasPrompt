"""Punto de entrada principal: lanza la interfaz gráfica."""

from __future__ import annotations

from .database import init_db
from .ui import run_ui


def main() -> None:
    """Inicia la aplicación de escritorio."""
    init_db()
    run_ui()


if __name__ == "__main__":
    main()
