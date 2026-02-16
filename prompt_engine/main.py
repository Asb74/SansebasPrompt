"""CLI principal de la herramienta multiusuario PROM-9™."""

from __future__ import annotations

import uuid
from pathlib import Path

from .motor import generar_prompt
from .pdf_export import export_prompt_to_pdf
from .schemas import Tarea, iso_timestamp
from .storage import (
    buscar_tarea_por_id,
    cargar_contextos,
    cargar_perfiles,
    guardar_tarea,
    listar_tareas,
)


def _seleccionar_opcion(items, label_key="nombre"):
    """Muestra opciones numeradas y devuelve el elemento seleccionado."""
    if not items:
        raise ValueError("No hay elementos disponibles para seleccionar.")

    for idx, item in enumerate(items, start=1):
        print(f"{idx}. {item.get(label_key, 'Sin nombre')}")

    while True:
        selected = input("Selecciona una opción por número: ").strip()
        if selected.isdigit() and 1 <= int(selected) <= len(items):
            return items[int(selected) - 1]
        print("Entrada inválida. Intenta nuevamente.")


def _pedir_campos_base() -> dict:
    """Solicita los campos comunes de una tarea PROM-9™."""
    return {
        "objetivo": input("Objetivo de la tarea: ").strip(),
        "entradas": input("Entradas clave: ").strip(),
        "restricciones": input("Restricciones: ").strip(),
        "formato_salida": input("Formato de salida esperado: ").strip(),
        "prioridad": input("Prioridad (Alta/Media/Baja): ").strip() or "Media",
    }


def _pedir_campos_por_area(area: str) -> dict:
    """Solicita campos específicos según área funcional."""
    area = area.lower()
    extras = {}
    if area == "it":
        extras["stack"] = input("Stack tecnológico: ").strip()
        extras["nivel_tecnico"] = input("Nivel técnico esperado: ").strip() or "Senior"
    elif area == "ventas":
        extras["segmento"] = input("Segmento objetivo: ").strip()
        extras["propuesta_valor"] = input("Propuesta de valor: ").strip()
    elif area == "contabilidad":
        extras["normativa"] = input("Normativa aplicable: ").strip() or "PGC"
        extras["periodo"] = input("Periodo de análisis: ").strip()
    else:
        extras["area_operativa"] = input("Área operativa: ").strip()
        extras["horizonte"] = input("Horizonte temporal: ").strip() or "Trimestral"
    return extras


def crear_tarea() -> None:
    """Flujo para crear una tarea nueva y generar prompt."""
    perfiles = cargar_perfiles()
    contextos = cargar_contextos()
    if not perfiles or not contextos:
        print("No hay perfiles/contextos configurados.")
        return

    print("\nSelecciona perfil:")
    perfil = _seleccionar_opcion(perfiles)
    print("\nSelecciona contexto:")
    contexto = _seleccionar_opcion(contextos)

    area = input("Área de la tarea (it/ventas/contabilidad/gestion): ").strip().lower() or "gestion"
    base = _pedir_campos_base()
    extras = _pedir_campos_por_area(area)

    datos_tarea = {"area": area, **base, **extras}
    prompt = generar_prompt(datos_tarea, perfil, contexto)

    tarea = Tarea(
        id=str(uuid.uuid4()),
        usuario=perfil.get("nombre", "Usuario"),
        contexto=contexto.get("nombre", "General"),
        area=area,
        objetivo=base["objetivo"],
        entradas=base["entradas"],
        restricciones=base["restricciones"],
        formato_salida=base["formato_salida"],
        prioridad=base["prioridad"],
        prompt_generado=prompt,
    )
    guardar_tarea(tarea)

    print("\n✅ Tarea creada correctamente")
    print(f"ID: {tarea.id}")
    print("\nPrompt generado:\n")
    print(prompt)


def ver_historial() -> None:
    """Lista el historial y permite filtrar por usuario."""
    tareas = listar_tareas()
    if not tareas:
        print("No hay tareas en el historial.")
        return

    filtro = input("Filtrar por usuario (dejar vacío para todos): ").strip().lower()
    for tarea in tareas:
        if filtro and tarea.usuario.lower() != filtro:
            continue
        print(f"- ID: {tarea.id} | Usuario: {tarea.usuario} | Área: {tarea.area} | Fecha: {tarea.created_at}")


def clonar_tarea() -> None:
    """Clona una tarea existente, regenerando ID, fecha y prompt."""
    tarea_id = input("ID de la tarea a clonar: ").strip()
    original = buscar_tarea_por_id(tarea_id)
    if not original:
        print("No se encontró la tarea indicada.")
        return

    perfiles = {p["nombre"]: p for p in cargar_perfiles()}
    contextos = {c["nombre"]: c for c in cargar_contextos()}
    perfil = perfiles.get(original.usuario, {"nombre": original.usuario, "rol": "Profesional"})
    contexto = contextos.get(
        original.contexto,
        {"nombre": original.contexto, "rol_contextual": "Asistente"},
    )

    datos_tarea = {
        "area": original.area,
        "objetivo": original.objetivo,
        "entradas": original.entradas,
        "restricciones": original.restricciones,
        "formato_salida": original.formato_salida,
        "prioridad": original.prioridad,
    }
    prompt_nuevo = generar_prompt(datos_tarea, perfil, contexto)

    clon = Tarea(
        id=str(uuid.uuid4()),
        usuario=original.usuario,
        contexto=original.contexto,
        area=original.area,
        objetivo=original.objetivo,
        entradas=original.entradas,
        restricciones=original.restricciones,
        formato_salida=original.formato_salida,
        prioridad=original.prioridad,
        prompt_generado=prompt_nuevo,
        created_at=iso_timestamp(),
    )
    guardar_tarea(clon)
    print(f"Tarea clonada correctamente. Nuevo ID: {clon.id}")


def exportar_pdf() -> None:
    """Exporta el prompt de una tarea específica a PDF."""
    tarea_id = input("ID de tarea a exportar: ").strip()
    tarea = buscar_tarea_por_id(tarea_id)
    if not tarea:
        print("No existe una tarea con ese ID.")
        return

    destino = input("Ruta de salida del PDF (default: exportaciones/<id>.pdf): ").strip()
    if not destino:
        destino = str(Path("exportaciones") / f"{tarea.id}.pdf")

    metadata = {
        "ID": tarea.id,
        "Usuario": tarea.usuario,
        "Contexto": tarea.contexto,
        "Área": tarea.area,
        "Fecha": tarea.created_at,
    }
    try:
        out = export_prompt_to_pdf("Prompt PROM-9™", metadata, tarea.prompt_generado, destino)
        print(f"PDF generado en: {out}")
    except RuntimeError as exc:
        print(f"No se pudo exportar: {exc}")


def main() -> None:
    """Punto de entrada del menú interactivo por consola."""
    opciones = {
        "1": crear_tarea,
        "2": ver_historial,
        "3": clonar_tarea,
        "4": exportar_pdf,
    }

    while True:
        print(
            """
=== PROM-9™ Prompt Engine ===
1. Crear nueva tarea y generar prompt
2. Listar historial (filtrado por usuario)
3. Clonar tarea anterior y regenerar prompt
4. Exportar prompt a PDF
5. Salir
"""
        )
        seleccion = input("Elige una opción: ").strip()
        if seleccion == "5":
            print("Hasta pronto.")
            break

        accion = opciones.get(seleccion)
        if not accion:
            print("Opción inválida.")
            continue

        try:
            accion()
        except Exception as exc:  # noqa: BLE001
            print(f"Error inesperado: {exc}")


if __name__ == "__main__":
    main()
