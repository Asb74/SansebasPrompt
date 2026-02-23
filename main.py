"""Launcher para ejecutar la UI de PROM-9™ desde la raíz del proyecto."""

from prompt_engine.database import init_db
from prompt_engine.ui import run_ui


def main() -> None:
    """Inicializa esquema/migraciones y luego lanza la UI."""
    init_db()
    run_ui()


if __name__ == "__main__":
    main()
