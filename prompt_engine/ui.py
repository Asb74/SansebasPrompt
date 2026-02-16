"""Interfaz gráfica Tkinter para PROM-9™ Prompt Engine."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from .motor import generar_prompt
from .pdf_export import export_prompt_to_pdf
from .schemas import Tarea
from .storage import (
    CONTEXTOS_FILE,
    PERFILES_FILE,
    cargar_contextos,
    cargar_perfiles,
    guardar_tarea,
    listar_tareas,
)

BASE_FIELDS = [
    ("objetivo", "Objetivo"),
    ("entradas", "Tipo situación"),
    ("prioridad", "Urgencia"),
    ("formato_salida", "Formato de salida"),
    ("restricciones", "Restricciones"),
]

TEMPLATE_FIELDS = {
    "it": [("stack", "Stack tecnológico"), ("nivel_tecnico", "Nivel técnico")],
    "ventas": [("segmento", "Segmento"), ("propuesta_valor", "Propuesta de valor")],
    "contabilidad": [("normativa", "Normativa"), ("periodo", "Periodo")],
    "gestion": [("area_operativa", "Área operativa"), ("horizonte", "Horizonte temporal")],
}


def _save_json(path: Path, payload: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


class KeyValueEditor(tk.Toplevel):
    """Editor modal genérico para crear/editar perfiles y contextos."""

    def __init__(self, master: tk.Tk, title: str, item: dict | None = None) -> None:
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.result: dict | None = None
        self.rows: list[tuple[ttk.Entry, ttk.Entry]] = []

        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Clave").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(container, text="Valor").grid(row=0, column=1, sticky="w")

        data = item or {"nombre": ""}
        for idx, (key, value) in enumerate(data.items(), start=1):
            self._add_row(container, key, str(value), idx)

        btns = ttk.Frame(container)
        btns.grid(row=1000, column=0, columnspan=2, pady=(12, 0), sticky="ew")
        ttk.Button(btns, text="+ Campo", command=lambda: self._add_row(container, "", "")).pack(
            side="left"
        )
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="Guardar", command=self._save).pack(side="right")

    def _add_row(self, parent: ttk.Frame, key: str, value: str, row: int | None = None) -> None:
        row = row or len(self.rows) + 1
        key_entry = ttk.Entry(parent)
        key_entry.insert(0, key)
        key_entry.grid(row=row, column=0, sticky="ew", pady=2)

        value_entry = ttk.Entry(parent)
        value_entry.insert(0, value)
        value_entry.grid(row=row, column=1, sticky="ew", pady=2)

        self.rows.append((key_entry, value_entry))

    def _save(self) -> None:
        payload: dict[str, str] = {}
        for key_entry, value_entry in self.rows:
            key = key_entry.get().strip()
            value = value_entry.get().strip()
            if not key:
                continue
            payload[key] = value

        if not payload.get("nombre"):
            messagebox.showwarning("Validación", "El campo 'nombre' es obligatorio.", parent=self)
            return

        self.result = payload
        self.destroy()


class PromptEngineUI:
    """Ventana principal para gestionar perfiles, contextos y tareas."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PROM-9™ Prompt Engine")
        self.root.geometry("980x760")

        self.perfiles = cargar_perfiles()
        self.contextos = cargar_contextos()
        self.current_task: Tarea | None = None

        self.base_entries: dict[str, tk.Widget] = {}
        self.template_entries: dict[str, ttk.Entry] = {}

        self.perfil_var = tk.StringVar()
        self.contexto_var = tk.StringVar()
        self.area_var = tk.StringVar(value="gestion")

        self._build_menu()
        self._build_layout()
        self._reload_selectors()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        archivo = tk.Menu(menubar, tearoff=False)
        archivo.add_command(label="Nuevo perfil", command=self.new_profile)
        archivo.add_command(label="Editar perfil", command=self.edit_profile)
        archivo.add_separator()
        archivo.add_command(label="Nuevo contexto", command=self.new_context)
        archivo.add_command(label="Editar contexto", command=self.edit_context)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.root.destroy)
        menubar.add_cascade(label="Archivo", menu=archivo)
        self.root.config(menu=menubar)

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 8))

        ttk.Label(header, text="Perfil").grid(row=0, column=0, sticky="w")
        self.perfil_combo = ttk.Combobox(header, textvariable=self.perfil_var, state="readonly")
        self.perfil_combo.grid(row=1, column=0, padx=(0, 8), sticky="ew")

        ttk.Label(header, text="Contexto").grid(row=0, column=1, sticky="w")
        self.contexto_combo = ttk.Combobox(header, textvariable=self.contexto_var, state="readonly")
        self.contexto_combo.grid(row=1, column=1, padx=(0, 8), sticky="ew")

        ttk.Label(header, text="Plantilla").grid(row=0, column=2, sticky="w")
        self.template_combo = ttk.Combobox(
            header,
            textvariable=self.area_var,
            state="readonly",
            values=["it", "ventas", "contabilidad", "gestion"],
        )
        self.template_combo.grid(row=1, column=2, sticky="ew")
        self.template_combo.bind("<<ComboboxSelected>>", lambda _: self._render_template_fields())

        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=1)
        header.columnconfigure(2, weight=1)

        base_box = ttk.LabelFrame(main, text="Datos base de la tarea")
        base_box.pack(fill="x", pady=(0, 8))

        for idx, (field, label) in enumerate(BASE_FIELDS):
            ttk.Label(base_box, text=label).grid(row=idx, column=0, sticky="w", padx=8, pady=4)
            if field in {"objetivo", "entradas", "restricciones"}:
                widget = tk.Text(base_box, height=2, wrap="word")
                widget.grid(row=idx, column=1, sticky="ew", padx=8, pady=4)
            else:
                widget = ttk.Entry(base_box)
                if field == "prioridad":
                    widget.insert(0, "Media")
                widget.grid(row=idx, column=1, sticky="ew", padx=8, pady=4)
            self.base_entries[field] = widget

        base_box.columnconfigure(1, weight=1)

        self.template_box = ttk.LabelFrame(main, text="Datos específicos según plantilla")
        self.template_box.pack(fill="x", pady=(0, 8))
        self._render_template_fields()

        ttk.Button(main, text="GENERAR PROMPT", command=self.generate_prompt).pack(fill="x", pady=(0, 8))

        self.prompt_box = ScrolledText(main, wrap="word", height=16)
        self.prompt_box.pack(fill="both", expand=True)

        footer = ttk.Frame(main)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(footer, text="Guardar", command=self.save_task).pack(side="left")
        ttk.Button(footer, text="Exportar PDF", command=self.export_pdf).pack(side="left", padx=6)
        ttk.Button(footer, text="Historial", command=self.show_history).pack(side="left")

    def _reload_selectors(self) -> None:
        profile_names = [item.get("nombre", "") for item in self.perfiles]
        context_names = [item.get("nombre", "") for item in self.contextos]

        self.perfil_combo["values"] = profile_names
        self.contexto_combo["values"] = context_names

        if profile_names and self.perfil_var.get() not in profile_names:
            self.perfil_var.set(profile_names[0])
        if context_names and self.contexto_var.get() not in context_names:
            self.contexto_var.set(context_names[0])

    def _render_template_fields(self) -> None:
        for widget in self.template_box.winfo_children():
            widget.destroy()
        self.template_entries.clear()

        fields = TEMPLATE_FIELDS.get(self.area_var.get(), TEMPLATE_FIELDS["gestion"])
        for idx, (field, label) in enumerate(fields):
            ttk.Label(self.template_box, text=label).grid(row=idx, column=0, sticky="w", padx=8, pady=4)
            entry = ttk.Entry(self.template_box)
            if field in {"nivel_tecnico"}:
                entry.insert(0, "Senior")
            if field in {"normativa"}:
                entry.insert(0, "PGC")
            if field in {"horizonte"}:
                entry.insert(0, "Trimestral")
            entry.grid(row=idx, column=1, sticky="ew", padx=8, pady=4)
            self.template_entries[field] = entry

        self.template_box.columnconfigure(1, weight=1)

    def _selected_item(self, collection: list[dict], name: str) -> dict | None:
        for item in collection:
            if item.get("nombre") == name:
                return item
        return None

    def _read_field(self, field: str) -> str:
        widget = self.base_entries[field]
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end").strip()
        return widget.get().strip()

    def _collect_task_data(self) -> dict[str, str]:
        data = {"area": self.area_var.get()}
        for field, _ in BASE_FIELDS:
            data[field] = self._read_field(field)
        for field, entry in self.template_entries.items():
            data[field] = entry.get().strip()
        if not data.get("prioridad"):
            data["prioridad"] = "Media"
        return data

    def generate_prompt(self) -> None:
        perfil = self._selected_item(self.perfiles, self.perfil_var.get())
        contexto = self._selected_item(self.contextos, self.contexto_var.get())
        if not perfil or not contexto:
            messagebox.showwarning("Datos incompletos", "Selecciona un perfil y un contexto válidos.")
            return

        data = self._collect_task_data()
        prompt = generar_prompt(data, perfil, contexto)
        self.prompt_box.delete("1.0", "end")
        self.prompt_box.insert("1.0", prompt)

        self.current_task = Tarea(
            id=str(uuid.uuid4()),
            usuario=perfil.get("nombre", "Usuario"),
            contexto=contexto.get("nombre", "General"),
            area=data["area"],
            objetivo=data.get("objetivo", ""),
            entradas=data.get("entradas", ""),
            restricciones=data.get("restricciones", ""),
            formato_salida=data.get("formato_salida", ""),
            prioridad=data.get("prioridad", "Media"),
            prompt_generado=prompt,
        )

    def save_task(self) -> None:
        prompt = self.prompt_box.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("Sin prompt", "Genera o pega un prompt antes de guardar.")
            return

        if self.current_task is None:
            data = self._collect_task_data()
            self.current_task = Tarea(
                id=str(uuid.uuid4()),
                usuario=self.perfil_var.get() or "Usuario",
                contexto=self.contexto_var.get() or "General",
                area=data["area"],
                objetivo=data.get("objetivo", ""),
                entradas=data.get("entradas", ""),
                restricciones=data.get("restricciones", ""),
                formato_salida=data.get("formato_salida", ""),
                prioridad=data.get("prioridad", "Media"),
                prompt_generado=prompt,
            )
        else:
            self.current_task.prompt_generado = prompt

        guardar_tarea(self.current_task)
        messagebox.showinfo("Guardado", f"Tarea guardada con ID: {self.current_task.id}")

    def export_pdf(self) -> None:
        prompt = self.prompt_box.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("Sin contenido", "No hay prompt para exportar.")
            return

        filename = filedialog.asksaveasfilename(
            title="Exportar prompt a PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"prompt_{self.area_var.get()}.pdf",
        )
        if not filename:
            return

        metadata = {
            "Usuario": self.perfil_var.get(),
            "Contexto": self.contexto_var.get(),
            "Área": self.area_var.get(),
        }
        try:
            out = export_prompt_to_pdf("Prompt PROM-9™", metadata, prompt, filename)
            messagebox.showinfo("Exportación completada", f"PDF generado en:\n{out}")
        except RuntimeError as exc:
            messagebox.showerror("Error", str(exc))

    def show_history(self) -> None:
        history = listar_tareas()
        window = tk.Toplevel(self.root)
        window.title("Historial de tareas")
        window.geometry("900x380")

        columns = ("id", "usuario", "contexto", "area", "created_at")
        tree = ttk.Treeview(window, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col.upper())
            tree.column(col, width=170 if col != "id" else 260)

        for task in history:
            tree.insert("", "end", values=(task.id, task.usuario, task.contexto, task.area, task.created_at))

        tree.pack(fill="both", expand=True, padx=12, pady=12)

    def _edit_item(self, title: str, items: list[dict], save_path: Path, target_name: str | None = None) -> None:
        selected = self._selected_item(items, target_name) if target_name else None
        modal = KeyValueEditor(self.root, title=title, item=selected)
        self.root.wait_window(modal)
        if modal.result is None:
            return

        if selected:
            selected.clear()
            selected.update(modal.result)
        else:
            items.append(modal.result)

        _save_json(save_path, items)
        self.perfiles = cargar_perfiles()
        self.contextos = cargar_contextos()
        self._reload_selectors()

    def new_profile(self) -> None:
        self._edit_item("Nuevo perfil", self.perfiles, PERFILES_FILE)

    def edit_profile(self) -> None:
        if not self.perfiles:
            messagebox.showwarning("Sin datos", "No hay perfiles para editar.")
            return
        self._edit_item("Editar perfil", self.perfiles, PERFILES_FILE, self.perfil_var.get())

    def new_context(self) -> None:
        self._edit_item("Nuevo contexto", self.contextos, CONTEXTOS_FILE)

    def edit_context(self) -> None:
        if not self.contextos:
            messagebox.showwarning("Sin datos", "No hay contextos para editar.")
            return
        self._edit_item("Editar contexto", self.contextos, CONTEXTOS_FILE, self.contexto_var.get())


def run_ui() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    elif "clam" in style.theme_names():
        style.theme_use("clam")
    PromptEngineUI(root)
    root.mainloop()
