"""Azure Uzbek speech. All blocking SDK work runs outside Tk's UI thread."""
from __future__ import annotations

import queue
import threading
from dataclasses import replace
from typing import Callable

from jarvis.voice_settings import VoiceSettings, VoiceSettingsStore


class AzureVoice:
    def __init__(self, emit: Callable = lambda *_: None, store=None, sdk=None) -> None:
        self.store = store or VoiceSettingsStore()
        self.settings = self.store.load()
        self.emit = emit
        self._sdk = sdk
        self._jobs = queue.Queue()
        self._recognizer = None
        self._synth = None
        self._generation = 0
        self._speech_generation = 0
        self._hold_revision = 0
        self._hold = False
        self.wants_listen = False
        self.listening = False
        self.speaking = False
        self.closed = False
        self._timer = None
        self._worker = threading.Thread(target=self._run, daemon=True, name="azure-speech")
        self._worker.start()

    @property
    def configured(self):
        return self.settings.configured

    def _library(self):
        if self._sdk is None:
            import azure.cognitiveservices.speech as speechsdk
            self._sdk = speechsdk
        return self._sdk

    def configure(self, settings: VoiceSettings) -> None:
        self.store.save(settings)
        self.stop_listening()
        self.stop_speaking()
        self.settings = replace(settings)

    def start_listening(self) -> None:
        self.settings.validate()
        self.wants_listen = True
        self._hold = False
        self.emit("voice_state", "starting")
        self._jobs.put(("listen", None))

    def stop_listening(self) -> None:
        self.wants_listen = False
        self._generation += 1
        self._jobs.put(("listen", None))

    def suspend_listening(self) -> None:
        self._hold = True
        self._hold_revision += 1
        self._jobs.put(("listen", None))

    def resume_listening(self) -> None:
        self._hold = False
        self._jobs.put(("listen", None))

    def speak(self, text: str) -> None:
        self.settings.validate()
        clean = " ".join(text.split())[:5000]
        if clean and not self.closed:
            self._jobs.put(("speak", (clean, replace(self.settings), self._speech_generation)))

    def stop_speaking(self) -> None:
        self._speech_generation += 1
        synth = self._synth
        if synth:
            def stop():
                try:
                    synth.stop_speaking_async().get()
                except Exception:
                    pass
            threading.Thread(target=stop, daemon=True).start()

    def _config(self, settings):
        sdk = self._library()
        config = sdk.SpeechConfig(subscription=settings.key, region=settings.region)
        config.speech_recognition_language = "uz-UZ"
        config.speech_synthesis_voice_name = settings.voice
        # Busy CPU/network can deliver audio slower than the SDK's strict defaults.
        if hasattr(config, "set_property") and hasattr(sdk, "PropertyId"):
            config.set_property(sdk.PropertyId.SpeechSynthesis_FrameTimeoutInterval, "10000")
            config.set_property(sdk.PropertyId.SpeechSynthesis_RtfTimeoutThreshold, "10")
        return config

    def _stop_recognizer(self):
        self._generation += 1
        if self._timer:
            self._timer.cancel()
            self._timer = None
        recognizer, self._recognizer = self._recognizer, None
        self.listening = False
        if recognizer:
            try:
                recognizer.stop_continuous_recognition_async().get()
            except Exception:
                pass

    def _sync(self):
        if self.closed or not self.wants_listen or self._hold or self.speaking:
            self._stop_recognizer()
            self.emit("voice_state", "waiting" if self.wants_listen else "idle")
            return
        if self._recognizer:
            return
        sdk = self._library()
        recognizer = sdk.SpeechRecognizer(speech_config=self._config(self.settings),
            audio_config=sdk.audio.AudioConfig(use_default_microphone=True))
        self._recognizer = recognizer
        self._generation += 1
        generation = self._generation
        def active():
            return not self.closed and generation == self._generation and not self._hold
        def partial(event):
            if active():
                self.emit("voice_partial", event.result.text)
        def final(event):
            if not active():
                return
            if event.result.reason == sdk.ResultReason.RecognizedSpeech and event.result.text.strip():
                self._hold = True
                self._hold_revision += 1
                if not self.settings.continuous:
                    self.wants_listen = False
                self._jobs.put(("listen", None))
                self.emit("voice_final", event.result.text.strip())
        def canceled(event):
            if active():
                self.wants_listen = False
                self._jobs.put(("listen", None))
                self._error(getattr(event, "error_details", "Azure tinglashni bekor qildi."))
        def stopped(_event):
            if active():
                self.wants_listen = False
                self._jobs.put(("listen", None))
                self.emit("voice_notice", "Tinglash yakunlandi. Mikrofonni qayta yoqishingiz mumkin.")
        recognizer.recognizing.connect(partial)
        recognizer.recognized.connect(final)
        recognizer.canceled.connect(canceled)
        recognizer.session_stopped.connect(stopped)
        recognizer.start_continuous_recognition_async().get()
        self.listening = True
        self.emit("voice_state", "listening")
        if not self.settings.continuous:
            def timeout():
                if generation == self._generation and not self._hold:
                    self.stop_listening()
                    self.emit("voice_notice", "Nutq eshitilmadi. Mikrofonni yana yoqing.")
            self._timer = threading.Timer(25, timeout)
            self._timer.daemon = True
            self._timer.start()

    def _speak(self, payload):
        text, settings, generation = payload
        if generation != self._speech_generation or self.closed:
            return
        revision = self._hold_revision
        self.speaking = True
        self._stop_recognizer()
        self.emit("voice_state", "speaking")
        try:
            sdk = self._library()
            synth = sdk.SpeechSynthesizer(speech_config=self._config(settings),
                audio_config=sdk.audio.AudioOutputConfig(use_default_speaker=True))
            self._synth = synth
            if generation != self._speech_generation or self.closed:
                return
            result = synth.speak_text_async(text).get()
            if result.reason == sdk.ResultReason.Canceled and generation == self._speech_generation:
                self._error(getattr(result.cancellation_details, "error_details", "Ovoz bekor qilindi."))
        finally:
            self._synth = None
            self.speaking = False
            if revision == self._hold_revision:
                self._hold = False
            self.emit("voice_state", "idle")
            self._sync()

    def _error(self, error):
        details = str(error)
        if self.settings.key:
            details = details.replace(self.settings.key, "[MAXFIY]")
        if "timeout" in details.casefold() or "timed out" in details.casefold():
            details = "Ovoz oqimi kechikdi va to'xtadi. Internet/kompyuter yuklanishini tekshiring. Matnli javob va Office tasklari ishlashda davom etadi."
        self.emit("voice_error", "Azure Speech: " + details[:350])

    def _run(self):
        while True:
            action, payload = self._jobs.get()
            try:
                if action == "close":
                    self._stop_recognizer()
                    return
                if self.closed:
                    continue
                if action == "speak":
                    self._speak(payload)
                else:
                    self._sync()
            except Exception as error:
                self.wants_listen = False
                self._stop_recognizer()
                self._error(error)
                self.emit("voice_state", "idle")
            finally:
                self._jobs.task_done()

    def close(self):
        self.closed = True
        self.wants_listen = False
        self.stop_speaking()
        self.emit = lambda *_: None
        self._jobs.put(("close", None))
        self._worker.join(timeout=2)


_voice = None


def get_voice() -> AzureVoice:
    global _voice
    if _voice is None or _voice.closed:
        _voice = AzureVoice()
    return _voice


def speak(text: str) -> None:
    """Compatibility entry point for the voice task executor."""
    get_voice().speak(text)
