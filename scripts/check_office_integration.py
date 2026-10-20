"""Deterministic Office Studio smoke; fake AI, temporary files, no cloud requests."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from jarvis.office.service import OfficeService
from jarvis.connections import ConnectionStore
from jarvis.tasks import COMPLETED, FAILED, PENDING_APPROVAL, TaskPlanner, TaskStore
from jarvis.ui.app import JarvisApp


SPECS = {
    'txt': {'title': 'JARVIS', 'text': 'JARVIS — raqamli hamroh,\nYordam berar har bir chog‘.\n'},
    "docx": {"title": "JARVIS sinovi", "sections": [{"heading": "Natija", "paragraphs": ["O'zbekcha matn va tahrirlanadigan hujjat."]}]},
    "xlsx": {"title": "Budjet namunasi", "sheets": [{"name": "Budjet", "headers": ["Nomi", "Summa"],
             "rows": [["Namuna A", 10], ["Namuna B", 20], ["Jami", None]],
             "formulas": [{"cell": "B4", "formula": "=SUM(B2:B3)"}],
             "chart": {"type": "bar", "title": "Namuna", "category_column": 1, "value_columns": [2]}}]},
    "pptx": {"title": "JARVIS imkoniyatlari", "slides": [{"title": "Office Studio", "bullets": ["Word, Excel va PowerPoint", "Asl faylga tegmasdan yangi natija"]},
             {"title": "Konvertatsiya", "body": "Lokal matn va Office formatlarini aylantirish."}]},
}


class FakeAI:
    model = "deterministic-test-only"
    def __init__(self):
        self.calls = 0

    def complete_json(self, instruction, message, **kwargs):
        self.calls += 1
        extension = message.split("FORMAT: ", 1)[1].splitlines()[0]
        return SPECS[extension]


def main():
    fake = FakeAI()
    checks = Path("data/office/checks")
    checks.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="integration-", dir=checks) as directory, patch("jarvis.ui.app.build_ai", return_value=fake), patch('jarvis.ui.app.load_local_env'), patch.dict('os.environ', {'AI_API_KEY': '', 'GEMINI_API_KEY': ''}):
        connections = ConnectionStore(Path(directory)/'connections.json')
        connections.add('gemini', 'deterministic-test-only', 'fake-test-key')
        with patch('jarvis.ui.app.ConnectionStore', return_value=connections):
            app = JarvisApp()
        app.title("JARVIS • Office integration test")
        app.voice_enabled = False
        app.tasks.close()
        app.tasks = TaskStore(Path(directory) / "test.db")
        app.planner = TaskPlanner(app.tasks)
        app.office = OfficeService(Path(directory) / "outputs")
        app._refresh_tasks()
        errors = []
        app.report_callback_exception = lambda kind, error, trace: errors.append(str(error))
        app._show_office_studio()
        studio = app.office_window
        outputs = []
        def wait_for(task_id):
            deadline = time.monotonic()+20
            while time.monotonic() < deadline:
                app.update()
                task = app.tasks.get(task_id)
                if task.status in {COMPLETED, FAILED}:
                    assert task.status == COMPLETED, task.result
                    return
                time.sleep(.02)
            raise AssertionError("Office task timed out")
        try:
            for label, extension in studio.FORMATS.items():
                studio.output_format.set(label)
                studio.prompt.delete("1.0", "end")
                studio.prompt.insert("1.0", "2 slaydli taqdimot yarat" if extension == "pptx" else "Sinov hujjati yarat")
                studio.create()
                wait_for(studio.last_task_id)
                path = next(path for path in app.office.artifacts() if path.suffix == "."+extension)
                assert path.stat().st_size > 0
                outputs.append(extension)
            docx = next(path for path in app.office.artifacts() if path.suffix == ".docx")
            task = app._submit_office_task("office_convert", {"source": str(docx), "target_format": "txt"})
            wait_for(task.id)
            assert fake.calls == 4  # Conversion did not invoke a provider.
            task = app._submit_office_task("office_create", {"format": "docx", "prompt": "Manbadan xulosa yarat", "source": str(docx)})
            assert app.tasks.get(task.id).status == PENDING_APPROVAL
            assert fake.calls == 4
            app._approve_task(task.id)  # Fake provider only: no source goes to a cloud service.
            wait_for(task.id)
            assert fake.calls == 5
            studio.geometry("780x630")
            app.geometry("980x620")
            app.update()
            studio.refresh()
            assert studio.files.size() >= 5
            assert studio.convert_menu.winfo_ismapped()
            assert app.prompt.winfo_ismapped() and app.task_panel.clear_button.winfo_ismapped()
            assert not errors, errors
            print(json.dumps({"created": outputs, "localConversion": True, "sourceApproval": True,
                              "library": studio.files.size(), "smallWindow": True, "cloudCalls": 0}))
        finally:
            app._close()


if __name__ == "__main__":
    main()
