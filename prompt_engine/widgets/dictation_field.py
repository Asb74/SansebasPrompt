"""Reusable widget that combines text input with voice dictation controls."""

from __future__ import annotations

from threading import Thread
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..voice_input import VoiceInput


class DictationField(ttk.Frame):
    """Composite widget with an editable field and integrated dictation button."""

    def __init__(
        self,
        master: tk.Widget,
        voice_input: VoiceInput | None,
        multiline: bool = False,
        height: int = 4,
    ) -> None:
        super().__init__(master)
        self.voice_input = voice_input
        self.multiline = multiline
        self._is_transcribing = False

        self.columnconfigure(0, weight=1)

        if multiline:
            self._field: tk.Widget = ScrolledText(self, height=height, wrap="word")
        else:
            self._field = ttk.Entry(self)
        self._field.grid(row=0, column=0, sticky="nsew")

        self.dictate_button = ttk.Button(self, text="🎤", width=3, command=self._toggle_dictation)
        self.dictate_button.grid(row=0, column=1, sticky="ne", padx=(6, 0))

        if self.voice_input is None:
            self.dictate_button.configure(state="disabled")

    def get_widget(self) -> tk.Widget:
        return self._field

    def get_text(self) -> str:
        if isinstance(self._field, tk.Text):
            return self._field.get("1.0", "end").strip()
        return self._field.get().strip()

    def set_text(self, value: str) -> None:
        self.clear()
        if isinstance(self._field, tk.Text):
            self._field.insert("1.0", value)
            return
        self._field.insert(0, value)

    def clear(self) -> None:
        if isinstance(self._field, tk.Text):
            self._field.delete("1.0", "end")
            return
        self._field.delete(0, "end")

    def _toggle_dictation(self) -> None:
        if self.voice_input is None:
            return
        if self._is_transcribing:
            return
        if self.voice_input.is_recording:
            self._stop_dictation()
            return
        self._start_dictation()

    def _start_dictation(self) -> None:
        if self.voice_input is None:
            return
        try:
            self.voice_input.start_recording()
        except Exception as exc:
            messagebox.showerror("Dictado", str(exc), parent=self.winfo_toplevel())
            return
        self.dictate_button.configure(text="⏹", state="normal")

    def _stop_dictation(self) -> None:
        if self.voice_input is None:
            return
        self._is_transcribing = True
        self.dictate_button.configure(text="⏹", state="disabled")
        worker = Thread(target=self._transcribe_worker, daemon=True)
        worker.start()

    def _transcribe_worker(self) -> None:
        if self.voice_input is None:
            return
        try:
            text = self.voice_input.stop_recording()
            self.after(0, lambda: self._on_transcription_done(text))
        except Exception as exc:
            self.after(0, lambda: self._on_transcription_error(exc))

    def _on_transcription_done(self, text: str) -> None:
        self._is_transcribing = False
        self.dictate_button.configure(text="🎤", state="normal")

        if not text:
            messagebox.showwarning("Dictado", "No se detectó texto.", parent=self.winfo_toplevel())
            return

        self._field.insert("insert", text)

    def _on_transcription_error(self, exc: Exception) -> None:
        self._is_transcribing = False
        self.dictate_button.configure(text="🎤", state="normal")
        messagebox.showerror("Dictado", str(exc), parent=self.winfo_toplevel())
