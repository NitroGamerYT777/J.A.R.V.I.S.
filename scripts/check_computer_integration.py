"""Own-app Tk smoke: no cloud, real user documents, Store launch or virus scan.

Run with python scripts/check_computer_integration.py from the repository.
All mutations use a disposable, explicitly scoped test workspace.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jarvis.computer.catalog import SKILLS
from jarvis.computer.platform import ApplicationNotFound
from jarvis.computer.service import ComputerService
from jarvis.memory import Memory
from jarvis.tasks import COMPLETED, FAILED, PENDING_APPROVAL, REJECTED, TaskStore
from jarvis.ui.app import JarvisApp
from jarvis.ui.effects import motion_clock


def main():
    checks = Path('data/computer/checks')
    checks.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='computer-ui-', dir=Path('tests')) as directory:
        temporary = Path(directory).resolve()
        root = temporary/'documents'
        root.mkdir()
        for index in range(200):
            (root/f'report-{index:03}.txt').write_text(f'Example {index}\n', encoding='utf-8')
        platform = Mock()
        def platform_action(key, args):
            if key == 'app_open':
                raise ApplicationNotFound(args['name'])
            assert key == 'store_search'
            return 'TEST ONLY: Store qidiruviga so‘rov olindi; haqiqiy oyna ochilmadi.'
        platform.execute.side_effect = platform_action
        service = ComputerService(roots=[root], storage=temporary/'state', platform=platform)
        connections = Mock(connections=[], assignments={})
        connections.default_connection.return_value = None
        connections.connection_for.return_value = None
        voice = Mock(configured=False, listening=False, speaking=False, wants_listen=False,
                     settings=SimpleNamespace(output_enabled=False))
        errors = []
        with patch('jarvis.ui.app.load_local_env'), patch('jarvis.ui.app.ConnectionStore', return_value=connections), \
             patch('jarvis.ui.app.build_ai', return_value=None), patch('jarvis.ui.app.get_voice', return_value=voice), \
             patch('jarvis.ui.app.Memory', side_effect=lambda _: Memory(temporary/'memory.db')), \
             patch('jarvis.ui.app.TaskStore', side_effect=lambda _: TaskStore(temporary/'tasks.db')), \
             patch('jarvis.ui.app.ComputerService', return_value=service), \
             patch('jarvis.ui.app.messagebox.askyesno', return_value=True) as approval:
            app = JarvisApp()
            app.title('JARVIS • Computer integration test')
            app.report_callback_exception = lambda kind, error, trace: errors.append(str(error))
            def pump(seconds=.1):
                deadline = time.monotonic()+seconds
                while time.monotonic() < deadline:
                    app.update()
                    time.sleep(.01)
            def wait_task(identifier):
                deadline = time.monotonic()+15
                while time.monotonic() < deadline:
                    pump(.03)
                    task = app.tasks.get(identifier)
                    if task.status in {COMPLETED, FAILED, REJECTED}:
                        return task
                raise AssertionError('Task timeout')
            try:
                app.geometry('980x620')
                app._show_computer_hub()
                hub = app.computer_window
                hub.geometry('860x650')
                pump(.4)
                assert hub.listbox.size() == 50
                for index, skill in enumerate(SKILLS.values()):
                    hub.listbox.selection_clear(0, 'end')
                    hub.listbox.selection_set(index)
                    hub._select()
                    app.update()
                    assert set(hub.fields) == set(skill.fields)
                    assert hub.run_button.winfo_ismapped()
                    assert hub.run_button.winfo_rooty()+hub.run_button.winfo_height() <= hub.winfo_rooty()+hub.winfo_height()
                    for widget in hub.fields.values():
                        assert widget.winfo_rooty()+widget.winfo_height() <= hub.run_button.winfo_rooty()
                source = root/'report-000.txt'
                started = time.perf_counter()
                task = app._submit_computer_task({'skill': 'file_find', 'args': {'query': 'report-000'}})
                assert wait_task(task.id).status == COMPLETED
                cold = (time.perf_counter()-started)*1000
                started = time.perf_counter()
                for _ in range(20):
                    assert service.files.execute('file_find', {'query': 'report-000'})['matches']
                warm = (time.perf_counter()-started)*1000/20
                task = app._submit_computer_task({'skill': 'text_append', 'args': {'path': str(source), 'text': 'appended'}})
                assert task.status == PENDING_APPROVAL
                assert 'appended' not in source.read_text()
                app._approve_task(task.id)
                assert wait_task(task.id).status == COMPLETED
                assert source.read_text().endswith('appended')
                identifier = service.files.execute('backup_list', {})[-1]['id']
                task = app._submit_computer_task({'skill': 'backup_restore', 'args': {'id': identifier}})
                app._approve_task(task.id)
                assert wait_task(task.id).status == COMPLETED
                assert source.read_text() == 'Example 0\n'
                task = app._submit_computer_task({'skill': 'app_open', 'args': {'name': 'Imaginary editor'}})
                app._approve_task(task.id)
                assert wait_task(task.id).status == FAILED
                pump(.2)
                approval.assert_called_once()
                store = next(task for task in app.tasks.recent() if 'store_search' in task.payload)
                assert wait_task(store.id).status == COMPLETED
                assert platform.execute.call_count == 2
                app._reply('report-000.txt nomli faylni top')  # Explicit shortcut needs no AI.
                pump(.3)
                assert any('report-000.txt' in task.result for task in app.tasks.recent())
                clock = motion_clock(app)
                items = len(hub.children)  # Stable Canvas items, no per-frame allocation.
                canvas_count = len(hub.winfo_children()[1].find_all())
                pump(.3)
                assert len(hub.children) == items
                assert len(hub.winfo_children()[1].find_all()) == canvas_count
                clock.set_enabled(False)
                pump(.2)
                frozen = clock.elapsed
                pump(.2)
                assert clock.elapsed == frozen
                clock.set_enabled(True)
                assert app.prompt.winfo_ismapped() and app.task_panel.clear_button.winfo_ismapped()
                assert app.prompt.winfo_rooty()+app.prompt.winfo_height() <= app.winfo_rooty()+app.winfo_height()
                app._show_office_studio()
                assert app.office_window.winfo_exists()
                if app.reactor.ready:
                    app.reactor.viewport.capture(checks/'native-core.png')
                else:
                    raise AssertionError('Native 3D renderer failed: '+app.reactor.error)
                assert not errors, errors
                print(json.dumps({'capabilities': len(SKILLS), 'forms': 50, 'taskApproval': True,
                    'realBackupRestore': True, 'storeConsentMock': True, 'cloudCalls': 0,
                    'smallWindows': True, 'native3D': app.reactor.ready, 'effectsToggle': True,
                    'coldTaskMs': round(cold, 2), 'cachedQueryMeanMs': round(warm, 2),
                    'sampleFiles': 200}))
            finally:
                app._close()


if __name__ == '__main__':
    main()
