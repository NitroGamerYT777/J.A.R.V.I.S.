from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

from jarvis.voice import AzureVoice
from jarvis.voice_settings import VoiceSettings, VoiceSettingsStore
from jarvis.ui.app import JarvisApp


class Signal:
    def connect(self, callback):
        self.callback = callback

    def emit(self, event):
        self.callback(event)


class Future:
    def __init__(self, result=None):
        self.result = result

    def get(self):
        return self.result


class Recognizer:
    def __init__(self, **kwargs):
        self.config = kwargs["speech_config"]
        self.stopped = False
        for name in ("recognizing", "recognized", "canceled", "session_stopped"):
            setattr(self, name, Signal())

    def start_continuous_recognition_async(self):
        return Future()

    def stop_continuous_recognition_async(self):
        self.stopped = True
        return Future()


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.recognizers = []
        self.synthesis = []
        self.release = threading.Event()
        self.entered = threading.Event()
        def recognizer(**kwargs):
            item = Recognizer(**kwargs)
            self.recognizers.append(item)
            return item
        def synthesizer(**kwargs):
            self.synthesis.append(kwargs)
            def speak(text):
                self.entered.set()
                class BlockingFuture:
                    def get(inner):
                        self.release.wait(3)
                        return NS(reason="done")
                return BlockingFuture()
            return NS(speak_text_async=speak,
                      stop_speaking_async=lambda: (self.release.set() or Future()))
        sdk = NS(SpeechConfig=lambda **kwargs: NS(**kwargs), SpeechRecognizer=recognizer,
                 SpeechSynthesizer=synthesizer, ResultReason=NS(RecognizedSpeech="text", Canceled="canceled"),
                 audio=NS(AudioConfig=lambda **kw: kw, AudioOutputConfig=lambda **kw: kw))
        store = Mock()
        store.load.return_value = VoiceSettings(key="secret-key", region="eastus")
        self.voice = AzureVoice(lambda *event: self.events.append(event), store, sdk)

    def tearDown(self):
        self.release.set()
        self.voice.close()

    def test_single_utterance_and_stale_callbacks(self):
        self.voice.start_listening()
        self.voice._jobs.join()
        recognizer = self.recognizers[-1]
        self.assertEqual(recognizer.config.speech_recognition_language, "uz-UZ")
        result = NS(result=NS(reason="text", text="Soat nechchi?"))
        recognizer.recognizing.emit(result)
        recognizer.recognized.emit(result)
        self.voice._jobs.join()
        recognizer.recognized.emit(result)
        self.assertEqual(self.events.count(("voice_final", "Soat nechchi?")), 1)
        self.assertFalse(self.voice.listening)
        self.assertTrue(recognizer.stopped)

    def test_continuous_half_duplex_and_stop(self):
        self.voice.settings.continuous = True
        self.voice.start_listening()
        self.voice._jobs.join()
        old = self.recognizers[-1]
        old.recognized.emit(NS(result=NS(reason="text", text="Salom")))
        self.voice._jobs.join()
        self.voice.speak("Assalomu alaykum")
        self.assertTrue(self.entered.wait(2))
        self.assertTrue(old.stopped)
        self.assertFalse(self.voice.listening)
        self.assertTrue(self.voice.speaking)
        self.assertEqual(self.synthesis[0]["speech_config"].speech_synthesis_voice_name, "uz-UZ-SardorNeural")
        self.voice.stop_speaking()
        self.voice._jobs.join()
        self.assertTrue(self.voice.listening)
        self.assertFalse(self.voice.speaking)

    def test_redaction_and_invalid_configuration(self):
        self.voice._error("failure secret-key")
        self.assertNotIn("secret-key", str(self.events))
        self.voice.settings.key = ""
        with self.assertRaises(ValueError):
            self.voice.start_listening()

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI")
    def test_settings_dpapi_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = VoiceSettingsStore(Path(directory) / "voice.json")
            settings = VoiceSettings(key="fake-azure-secret", region="eastus")
            store.save(settings)
            raw = store.path.read_text()
            self.assertNotIn(settings.key, raw)
            self.assertIn("key_protected", json.loads(raw))
            self.assertEqual(store.load(), settings)

    def test_invalid_settings_do_not_expose_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            store = VoiceSettingsStore(Path(directory) / "voice.json")
            store.path.write_text('{"continuous": "bad"}')
            store.load()
            self.assertTrue(store.error)

    def test_transcript_uses_existing_command_pipeline(self):
        app = Mock()
        app.voice.settings.auto_send = True
        JarvisApp._voice_event(app, "voice_final", "example.com saytini och")
        app._send.assert_called_once_with("example.com saytini och")
        app.voice.settings.auto_send = False
        app._send.reset_mock()
        JarvisApp._voice_event(app, "voice_final", "Salom")
        app._send.assert_not_called()
        app.voice.resume_listening.assert_called_once()

    def test_old_tts_does_not_resume_during_new_request(self):
        self.voice.settings.continuous = True
        self.voice.start_listening()
        self.voice._jobs.join()
        self.voice.speak("Javob")
        self.assertTrue(self.entered.wait(2))
        self.voice.suspend_listening()
        self.voice.stop_speaking()
        self.voice._jobs.join()
        self.assertFalse(self.voice.listening)
        self.voice.resume_listening()
        self.voice._jobs.join()
        self.assertTrue(self.voice.listening)
