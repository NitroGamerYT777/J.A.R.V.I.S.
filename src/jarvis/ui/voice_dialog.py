from __future__ import annotations

import tkinter as tk
from jarvis.ui import theme
from jarvis.ui.widgets import GlowButton
from jarvis.voice_settings import VoiceSettings, VOICES


class VoiceDialog(tk.Toplevel):
    def __init__(self, parent, service, on_save):
        super().__init__(parent)
        self.service, self.on_save = service, on_save
        self.title("JARVIS • Azure ovoz sozlamalari")
        self.configure(bg=theme.PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        body = tk.Frame(self, bg=theme.PANEL, padx=22, pady=20)
        body.pack(fill="both", expand=True)
        def label(text):
            tk.Label(body, text=text, bg=theme.PANEL, fg=theme.TEXT, wraplength=430,
                     justify="left").pack(anchor="w", pady=(8, 4))
        label("AZURE AI SPEECH • O'ZBEKCHA")
        label("Azure portalidagi Speech resursining Key va Region qiymatlarini kiriting. Bu Gemini API kaliti emas.")
        self.key = tk.StringVar(value=service.settings.key)
        self.region = tk.StringVar(value=service.settings.region)
        for title, variable, secret in (("API KEY", self.key, True), ("REGION (masalan: eastus)", self.region, False)):
            label(title)
            tk.Entry(body, textvariable=variable, show="•" if secret else "", width=48,
                     bg=theme.PANEL_ALT, fg=theme.TEXT, insertbackground=theme.CYAN).pack(fill="x", ipady=6)
        self.voice = tk.StringVar(value=service.settings.voice)
        label("JAVOB OVOZI")
        tk.OptionMenu(body, self.voice, *VOICES).pack(fill="x")
        self.continuous = tk.BooleanVar(value=service.settings.continuous)
        self.auto_send = tk.BooleanVar(value=service.settings.auto_send)
        self.output = tk.BooleanVar(value=service.settings.output_enabled)
        for text, variable in (("Doimiy suhbat (mikrofon tugmasi bilan boshlanadi)", self.continuous),
                               ("Eshitilgan matnni avtomatik yuborish", self.auto_send),
                               ("Javoblarni ovoz chiqarib aytish", self.output)):
            tk.Checkbutton(body, text=text, variable=variable, bg=theme.PANEL, fg=theme.TEXT,
                           selectcolor=theme.PANEL_ALT, activebackground=theme.PANEL).pack(anchor="w", pady=4)
        label("Mikrofon faqat yoqqaningizda Azure'ga audio yuboradi. Audio fayllar saqlanmaydi. Kalit Windows DPAPI bilan himoyalanadi. Azure tarifingiz amal qiladi.")
        self.message = tk.Label(body, text=service.store.error, bg=theme.PANEL, fg=theme.AMBER, wraplength=430)
        self.message.pack(fill="x", pady=8)
        controls = tk.Frame(body, bg=theme.PANEL)
        controls.pack(fill="x")
        GlowButton(controls, "SAQLASH", self.save).pack(side="right")
        GlowButton(controls, "OVOZNI SINASH", self.test).pack(side="left")

    def save(self):
        try:
            self.service.configure(VoiceSettings(self.key.get().strip(), self.region.get().strip().lower(),
                self.voice.get(), self.continuous.get(), self.auto_send.get(), self.output.get()))
            self.on_save()
            self.message.configure(text="Saqlandi. Ulanishni ovozni sinash orqali tekshiring.", fg=theme.GREEN)
            return True
        except Exception as error:
            self.message.configure(text=str(error), fg=theme.RED)
            return False

    def test(self):
        if self.save():
            self.service.speak("Assalomu alaykum! Men Jarvisman. Sizni tinglashga tayyorman.")
