"""Launcher para ejecutar la UI de PROM-9™ desde la raíz del proyecto."""

from prompt_engine.ui import run_ui


def main() -> None:
    """Lanza la UI (bootstrap y migraciones se ejecutan en UI)."""
    run_ui()


if __name__ == "__main__":
    main()
