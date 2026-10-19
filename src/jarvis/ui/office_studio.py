"""Office authoring/conversion controls; tasks, not this dialog, do the work."""
from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from jarvis.ui import theme
from jarvis.ui.widgets import GlowButton
from jarvis.office.service import OfficeService


class OfficeStudio(tk.Toplevel):
    FORMATS = {"Word • DOCX": "docx", "Excel • XLSX": "xlsx", "PowerPoint • PPTX": "pptx"}

    def __init__(self, parent, service: OfficeService, submit, lookup_task=None):
        super().__init__(parent)
        self.service, self.submit = service, submit
        self.lookup_task = lookup_task
        self.last_task_id = None
        self.title("JARVIS • Office Studio")
        self.configure(bg=theme.BACKGROUND)
        self.geometry("980x720")
        self.minsize(780, 630)
        self.transient(parent)
        self.job = None
        self.bind("<Destroy>", self._destroy, add="+")
        tk.Label(self, text="OFFICE STUDIO", bg=theme.BACKGROUND, fg=theme.CYAN_SOFT,
                 font=(theme.MONO, 18, "bold")).pack(anchor="w", padx=22, pady=(18, 3))
        tk.Label(self, text="Prompt → tahrirlanadigan hujjat. Konvertatsiya → lokal fayl.", bg=theme.BACKGROUND,
                 fg=theme.MUTED, font=(theme.FONT, 10)).pack(anchor="w", padx=22, pady=(0, 12))
        body = tk.Frame(self, bg=theme.BACKGROUND)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 18))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)
        form = tk.Frame(body, bg=theme.PANEL, padx=15, pady=14)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.output_format = tk.StringVar(value=next(iter(self.FORMATS)))
        self.filename = tk.StringVar()
        self.source = tk.StringVar()
        self.convert_format = tk.StringVar(value="pdf")
        self.sheet = tk.StringVar()
        self.message = tk.StringVar(value="Yangi hujjat uchun AI ulanishi kerak. Konvertatsiya AI'siz ishlaydi.")

        def label(text):
            tk.Label(form, text=text, bg=theme.PANEL, fg=theme.CYAN_SOFT,
                     font=(theme.FONT, 9, "bold")).pack(anchor="w", pady=(6, 4))
        def entry(variable):
            control = tk.Entry(form, textvariable=variable, bg=theme.PANEL_ALT,
                               fg=theme.TEXT, insertbackground=theme.CYAN, relief="flat")
            control.pack(fill="x", ipady=5)
            return control
        label("YARATISH FORMATI")
        self._menu(form, self.output_format, tuple(self.FORMATS)).pack(fill="x")
        label("HUJJAT TOPSHIRIG'I")
        self.prompt = tk.Text(form, height=6, wrap="word", bg=theme.PANEL_ALT, fg=theme.TEXT,
                              insertbackground=theme.CYAN, relief="flat", font=(theme.FONT, 10))
        self.prompt.pack(fill="both", expand=True)
        self.prompt.insert("1.0", "")
        self.prompt.bind("<Control-Return>", lambda _: self.create())
        label("FAYL NOMI (ixtiyoriy, papka yo'lisiz)")
        entry(self.filename)
        label("MANBA FAYL (konvertatsiya yoki manbadan yangi hujjat)")
        source_row = tk.Frame(form, bg=theme.PANEL)
        source_row.pack(fill="x")
        tk.Entry(source_row, textvariable=self.source, state="readonly", readonlybackground=theme.PANEL_ALT,
                 fg=theme.TEXT, relief="flat").pack(side="left", fill="x", expand=True, ipady=6)
        GlowButton(source_row, "TANLASH", self.choose_source).pack(side="right", padx=(5, 0))
        GlowButton(source_row, "×", lambda: self.source.set("")).pack(side="right", padx=(5, 0))
        tk.Label(form, text="Yaratishda manba tanlansa, matnning 24000 belgigacha qismi AI'ga yuboriladi: Tasks'da tasdiq kerak. Konvertatsiya lokal.",
                 wraplength=420, justify="left", bg=theme.PANEL, fg=theme.AMBER, font=(theme.FONT, 8)).pack(anchor="w", pady=6)
        GlowButton(form, "✦ HUJJATNI YARATISH", self.create).pack(fill="x", pady=(0, 6))
        label("KONVERTATSIYA FORMATI / XLSX VARAQ NOMI (CSV uchun)")
        row = tk.Frame(form, bg=theme.PANEL)
        row.pack(fill="x")
        self.convert_menu = self._menu(row, self.convert_format, ("pdf", "txt", "csv", "xlsx", "docx"))
        self.convert_menu.pack(side="left")
        tk.Entry(row, textvariable=self.sheet, bg=theme.PANEL_ALT, fg=theme.TEXT,
                 insertbackground=theme.CYAN, relief="flat").pack(side="left", fill="x", expand=True, padx=(8, 0), ipady=5)
        GlowButton(form, "KONVERTATSIYA QILISH", self.convert).pack(fill="x", pady=6)
        tk.Label(form, textvariable=self.message, bg=theme.PANEL, fg=theme.MUTED,
                 wraplength=420, justify="left", font=(theme.FONT, 9)).pack(fill="x")

        library = tk.Frame(body, bg=theme.PANEL, padx=14, pady=14)
        library.grid(row=0, column=1, sticky="nsew")
        tk.Label(library, text="TAYYOR FAYLLAR", bg=theme.PANEL, fg=theme.CYAN_SOFT,
                 font=(theme.MONO, 11, "bold")).pack(anchor="w", pady=(0, 8))
        tk.Label(library, text="Asl fayllar o'zgarmaydi. Natijalar alohida nom bilan saqlanadi.",
                 wraplength=270, justify="left", bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w", pady=(0, 8))
        self.files = tk.Listbox(library, bg=theme.PANEL_ALT, fg=theme.TEXT, selectbackground=theme.BLUE,
                               font=(theme.FONT, 9), relief="flat", activestyle="none", exportselection=False)
        self.files.pack(fill="both", expand=True)
        self.files.bind("<Double-Button-1>", lambda _: self.open_selected())
        self.files.bind("<Return>", lambda _: self.open_selected())
        GlowButton(library, "FAYLNI OCHISH", self.open_selected).pack(fill="x", pady=(8, 4))
        GlowButton(library, "MANBA SIFATIDA TANLASH", self.use_selected).pack(fill="x", pady=4)
        GlowButton(library, "NATIJALAR PAPKASI", self.open_folder).pack(fill="x", pady=4)
        tk.Label(library, text="DOCX / XLSX / PPTX → PDF\nCSV ↔ XLSX, TXT ↔ DOCX\nDOCX / PPTX / PDF → TXT\nPDF skanlari uchun OCR hozircha yo'q.",
                 justify="left", bg=theme.PANEL, fg=theme.MUTED, font=(theme.FONT, 8)).pack(anchor="w", pady=(10, 0))
        self.paths = []
        self._snapshot = None
        self.refresh()

    @staticmethod
    def _menu(parent, variable, choices):
        menu = tk.OptionMenu(parent, variable, *choices)
        menu.configure(bg=theme.PANEL_ALT, fg=theme.TEXT, activebackground=theme.BLUE, highlightthickness=0)
        menu["menu"].configure(bg=theme.PANEL_ALT, fg=theme.TEXT)
        return menu

    def choose_source(self):
        chosen = filedialog.askopenfilename(parent=self, title="Office manba fayli",
            filetypes=[("Office va matn", "*.docx *.xlsx *.pptx *.csv *.txt *.pdf")])
        if chosen:
            self.source.set(str(Path(chosen).resolve()))
            self._conversion_choices()

    def _conversion_choices(self):
        from jarvis.office.converters import supported_conversions
        choices = supported_conversions().get(Path(self.source.get()).suffix.casefold(), ())
        values = [item.lstrip(".") for item in choices]
        if not values:
            values = ["pdf"]
        self.convert_format.set(values[0])
        menu = self.convert_menu["menu"]
        menu.delete(0, "end")
        for value in values:
            menu.add_command(label=value, command=tk._setit(self.convert_format, value))

    def create(self):
        self._submit("office_create", {"format": self.FORMATS[self.output_format.get()],
            "prompt": self.prompt.get("1.0", "end").strip(), "filename": self.filename.get(), "source": self.source.get()})

    def convert(self):
        self._submit("office_convert", {"source": self.source.get(), "target_format": self.convert_format.get(), "sheet": self.sheet.get()})

    def _submit(self, action, data):
        try:
            task = self.submit(action, data)
            self.last_task_id = task.id
            self.message.set(f"TASK #{task.id}: " + ("Tasks panelida manbani AI'ga yuborishni tasdiqlang." if task.requires_approval else "Bajarilmoqda. Natija o'ngdagi kutubxonada paydo bo'ladi."))
        except Exception as error:
            self.message.set(str(error))

    def _selected(self):
        selected = self.files.curselection()
        return self.paths[selected[0]] if selected and selected[0] < len(self.paths) else None

    def use_selected(self):
        path = self._selected()
        if path:
            self.source.set(str(path))
            self._conversion_choices()

    def open_selected(self):
        path = self._selected()
        if path and path.is_file() and path.parent.resolve() == self.service.output_dir:
            try:
                os.startfile(path)
            except OSError as error:
                self.message.set("Faylni ochadigan dastur topilmadi: " + str(error))

    def open_folder(self):
        self.service.output_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.service.output_dir)

    def refresh(self):
        try:
            if self.last_task_id is not None and self.lookup_task:
                from jarvis.tasks import PENDING_APPROVAL
                try:
                    task = self.lookup_task(self.last_task_id)
                    detail = "Tasks panelida manba matnini AI'ga yuborishni tasdiqlang." if task.status == PENDING_APPROVAL else task.result[:260]
                    self.message.set(f"TASK #{task.id}: {task.status}. {detail}")
                except KeyError:
                    self.last_task_id = None
            paths = self.service.artifacts()
            snapshot = [(str(path), path.stat().st_size) for path in paths]
            if snapshot != self._snapshot:
                selected = self._selected()
                self.paths, self._snapshot = paths, snapshot
                self.files.delete(0, "end")
                for path in paths:
                    self.files.insert("end", f"{path.suffix[1:].upper()}  {path.name}")
                if paths:
                    self.files.selection_set(paths.index(selected) if selected in paths else 0)
        except OSError:
            self.message.set("Natijalar papkasini o'qib bo'lmadi.")
        self.job = self.after(1500, self.refresh)

    def _destroy(self, event):
        if event.widget is self and self.job:
            self.after_cancel(self.job)
            self.job = None
