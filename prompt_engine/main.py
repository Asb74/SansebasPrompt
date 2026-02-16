"""Punto de entrada principal: lanza la interfaz gráfica."""

from __future__ import annotations

from .ui import run_ui


def main() -> None:
    """Inicia la aplicación de escritorio."""
    run_ui()


if __name__ == "__main__":
    main()
