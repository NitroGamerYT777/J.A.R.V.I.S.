"""Human-readable controls for all 50 local capabilities and their task results."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from jarvis.computer.catalog import SKILLS
from jarvis.tasks import COMPLETED, FAILED, REJECTED
from jarvis.ui import theme
from jarvis.ui.effects import NeuralRibbon
from jarvis.ui.widgets import GlowButton


LABELS = {'path': 'Manba fayl/papka', 'root': 'Qidirish papkasi (ixtiyoriy)', 'query': 'Qidiriladigan nom/matn',
          'limit': 'Natijalar soni (1–100)', 'destination': 'Natija yo‘li / mavjud manzil papkasi',
          'name': 'Yangi nom / ilova nomi', 'text': 'Yoziladigan matn', 'old': 'Aniq eski matn',
          'new': 'Yangi matn', 'other': 'Ikkinchi fayl', 'id': 'Tarix yoki reja ID', 'mode': 'trim / sort / unique'}


class ComputerHub(tk.Toplevel):
    def __init__(self, parent, service, submit, get_task):
        super().__init__(parent)
        self.service, self.submit, self.get_task = service, submit, get_task
        self.title('JARVIS • Computer Hub / 50 qobiliyat')
        self.geometry('1000x750')
        self.minsize(860, 650)
        self.configure(bg=theme.PANEL)
        self.messages = queue.Queue()
        self.selected = None
        self.task_id = None
        self.job = None
        self.fields = {}
        self.last_result = None
        self._refreshing = False
        self.bind('<Destroy>', self._closed, add='+')
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        title = tk.Frame(self, bg=theme.PANEL)
        title.pack(fill='x', padx=18, pady=(14, 4))
        tk.Label(title, text='COMPUTER HUB', bg=theme.PANEL, fg=theme.CYAN_SOFT, font=(theme.MONO, 16, 'bold')).pack(side='left')
        self.refresh_button = GlowButton(title, 'INDEKSNI YANGILASH', self._refresh)
        self.refresh_button.pack(side='right')
        GlowButton(title, '+ ISH PAPKASI', self._add_root).pack(side='right', padx=8)
        NeuralRibbon(self, state=lambda: 'thinking' if self.task_id else 'idle', height=32).pack(fill='x', padx=18)
        roots = ' • '.join(str(root) for root in service.files.scope.roots)
        self.roots_label = tk.Label(self, text='Lokal hudud: '+roots+'\nMaxfiy/tizim yo‘llari yopiq. Qidiruv chegaralangan; butun disk to‘liq tekshirildi degani emas.',
                 bg=theme.PANEL, fg=theme.MUTED, wraplength=800, justify='left', font=(theme.FONT, 8))
        self.roots_label.pack(fill='x', padx=18, pady=(3, 8))
        # Results and controls have reserved space even at the minimum window size.
        self.status = tk.Label(self, text='Amal tanlang. O‘zgarishlar Tasks panelida tasdiqlanadi.', bg=theme.PANEL, fg=theme.CYAN, anchor='w', font=(theme.FONT, 9))
        self.status.pack(side='bottom', fill='x', padx=18, pady=8)
        output = tk.Frame(self, bg=theme.PANEL_ALT)
        output.pack(side='bottom', fill='x', padx=18)
        self.result = tk.Text(output, height=10, bg=theme.PANEL_ALT, fg=theme.TEXT, relief='flat', wrap='word', font=(theme.MONO, 9), state='disabled')
        scroll = tk.Scrollbar(output, command=self.result.yview)
        self.result.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.result.pack(fill='both', expand=True)
        body = tk.Frame(self, bg=theme.PANEL)
        body.pack(fill='both', expand=True, padx=18, pady=8)
        left = tk.Frame(body, bg=theme.PANEL, width=340)
        left.pack(side='left', fill='y', padx=(0, 14))
        self.search = tk.StringVar()
        entry = tk.Entry(left, textvariable=self.search, bg=theme.PANEL_ALT, fg=theme.TEXT, insertbackground=theme.CYAN, relief='flat', font=(theme.FONT, 10))
        entry.pack(fill='x', ipady=6)
        self.search.trace_add('write', lambda *_: self._filter())
        self.group = tk.StringVar(value='Barchasi')
        group = ttk.Combobox(left, textvariable=self.group, values=['Barchasi']+sorted({skill.group for skill in SKILLS.values()}), state='readonly')
        group.pack(fill='x', pady=6)
        group.bind('<<ComboboxSelected>>', lambda _: self._filter())
        listing = tk.Frame(left, bg=theme.PANEL)
        listing.pack(fill='both', expand=True)
        self.listbox = tk.Listbox(listing, width=40, height=8, exportselection=False, bg=theme.PANEL_ALT, fg=theme.TEXT, selectbackground=theme.BLUE, relief='flat', activestyle='none', font=(theme.FONT, 9))
        scrollbar = tk.Scrollbar(listing, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.listbox.pack(fill='both', expand=True)
        self.listbox.bind('<<ListboxSelect>>', self._select)
        right = tk.Frame(body, bg=theme.PANEL)
        right.pack(side='left', fill='both', expand=True)
        self.heading = tk.Label(right, text='50 ta lokal vosita', bg=theme.PANEL, fg=theme.CYAN_SOFT, font=(theme.FONT, 12, 'bold'), wraplength=540, anchor='w', justify='left')
        self.heading.pack(fill='x')
        self.warning = tk.Label(right, bg=theme.PANEL, fg=theme.AMBER, font=(theme.FONT, 9), wraplength=530, anchor='w', justify='left')
        self.warning.pack(fill='x', pady=5)
        self.run_button = GlowButton(right, 'TASK YARATISH', self._run, state='disabled')
        self.run_button.pack(side='bottom', fill='x', pady=7)
        self.form = tk.Frame(right, bg=theme.PANEL)
        self.form.pack(fill='both', expand=True)
        self._filter()
        self.job = self.after(150, self._poll)

    def _filter(self):
        query = self.search.get().casefold()
        self.visible = [skill for skill in SKILLS.values() if (self.group.get() == 'Barchasi' or skill.group == self.group.get())
                        and query in (skill.key+' '+skill.title).casefold()]
        self.listbox.delete(0, 'end')
        for skill in self.visible:
            self.listbox.insert('end', ('◇ ' if skill.approval else '· ')+skill.title)

    def _select(self, _event=None):
        selected = self.listbox.curselection()
        if not selected:
            return
        self.selected = self.visible[selected[0]]
        skill = self.selected
        self.heading.configure(text=skill.title)
        self.warning.configure(text=('Tasdiq kerak: parametrlarni tekshirib, Tasks panelida tasdiqlang.' if skill.approval else 'O‘qish/ko‘rsatish amali avtomatik bajariladi.')+'\n'+skill.key)
        for child in self.form.winfo_children():
            child.destroy()
        self.fields = {}
        for field in skill.fields:
            tk.Label(self.form, text=LABELS[field]+(' *' if field in skill.required else ''), bg=theme.PANEL, fg=theme.MUTED, font=(theme.FONT, 8)).pack(anchor='w', pady=(4, 1))
            row = tk.Frame(self.form, bg=theme.PANEL)
            row.pack(fill='x')
            if field in {'text', 'old', 'new'}:
                widget = tk.Text(row, height=2, bg=theme.PANEL_ALT, fg=theme.TEXT, insertbackground=theme.CYAN, relief='flat', font=(theme.FONT, 9), wrap='word')
                widget.pack(fill='x')
            else:
                widget = tk.Entry(row, bg=theme.PANEL_ALT, fg=theme.TEXT, insertbackground=theme.CYAN, relief='flat', font=(theme.FONT, 10))
                widget.pack(side='left', fill='x', expand=True, ipady=4)
            self.fields[field] = widget
            if field in {'path', 'root', 'other', 'destination'}:
                GlowButton(row, '…', lambda name=field: self._browse(name), font=(theme.FONT, 8)).pack(side='right', padx=(4, 0))
        self.run_button.configure(state='normal')

    def _browse(self, field):
        key = self.selected.key
        options = {'parent': self, 'initialdir': str(self.service.files.scope.roots[0]) if self.service.files.scope.roots else str(Path.cwd())}
        if field == 'path' and key == 'folder_create':
            value = filedialog.asksaveasfilename(**options, title='Yangi papka yo‘lini kiriting')
        elif field == 'root' or (field == 'path' and key.startswith(('folder_', 'organize_'))):
            value = filedialog.askdirectory(**options)
        elif field == 'destination' and key in {'file_move', 'folder_move', 'file_copy', 'folder_copy'}:
            value = filedialog.askdirectory(**options)
        elif field == 'destination' or key == 'text_create':
            value = filedialog.asksaveasfilename(**options, defaultextension='.zip' if key == 'zip_create' else '')
        else:
            value = filedialog.askopenfilename(**options)
        if value:
            self.fields[field].delete(0, 'end')
            self.fields[field].insert(0, value)

    def _run(self):
        if self.selected is None:
            return
        args = {}
        for field, widget in self.fields.items():
            value = widget.get('1.0', 'end-1c') if isinstance(widget, tk.Text) else widget.get().strip()
            if value or field in self.selected.required:
                args[field] = value
        try:
            task = self.submit({'skill': self.selected.key, 'args': args})
            self.task_id = task.id
            self.last_result = None
            self.status.configure(text=f'TASK #{task.id}: {task.status}')
        except (ValueError, OSError, PermissionError) as error:
            messagebox.showerror('Computer Hub', str(error), parent=self)

    def _display(self, text):
        self.result.configure(state='normal')
        self.result.delete('1.0', 'end')
        self.result.insert('end', str(text))
        self.result.configure(state='disabled')

    def _refresh(self):
        if self._refreshing:
            return
        self._refreshing = True
        self.refresh_button.configure(state='disabled')
        self.status.configure(text='Indeks fonda yangilanmoqda (8 soniyagacha skan)...')
        def work():
            try:
                self.service.files.index.refresh(force=True)
                self.messages.put('Lokal indeks yangilandi. Hajm/vaqt chegarasi saqlanadi.')
            except Exception as error:
                self.messages.put('Indeks xatosi: '+str(error))
        threading.Thread(target=work, daemon=True).start()

    def _add_root(self):
        value = filedialog.askdirectory(parent=self, title='JARVIS uchun qo‘shimcha ish papkasi')
        if not value or not messagebox.askyesno('Lokal fayl hududini kengaytirish',
                f'{value}\n\nJARVIS shu papka va ichidagi fayllarni qidirishi/o‘qishi mumkin bo‘ladi. O‘zgartirish amallari Tasks tasdig‘ini talab qilishda davom etadi. Tanlovni lokal saqlaymi?', parent=self):
            return
        try:
            self.service.files.add_root(value)
            self.roots_label.configure(text='Lokal hudud: '+' • '.join(str(root) for root in self.service.files.scope.roots)+'\nMaxfiy/tizim yo‘llari yopiq. Qidiruv chegaralangan.')
            self.status.configure(text='Ish papkasi qo‘shildi; INDEKSNI YANGILASH tugmasini bosing.')
        except (ValueError, OSError) as error:
            messagebox.showerror('Ish papkasi', str(error), parent=self)

    def _poll(self):
        self.job = None
        try:
            while True:
                self.status.configure(text=self.messages.get_nowait())
                self._refreshing = False
                self.refresh_button.configure(state='normal')
        except queue.Empty:
            pass
        if self.task_id is not None:
            try:
                task = self.get_task(self.task_id)
                current = (task.status, task.result)
                if current != self.last_result:
                    self.status.configure(text=f'TASK #{task.id}: {task.status}')
                    self._display(task.result or task.payload+'\n\n'+task.approval_reason)
                    self.last_result = current
                if task.status in {COMPLETED, FAILED, REJECTED}:
                    self.task_id = None
            except KeyError:
                self.task_id = None
        self.job = self.after(200, self._poll)

    def _closed(self, event):
        if event.widget is self and self.job:
            self.after_cancel(self.job)
            self.job = None
