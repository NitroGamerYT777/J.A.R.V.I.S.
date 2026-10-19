from __future__ import annotations

from io import BytesIO
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import pytest

from jarvis.llm import AIError, GeminiAI, OpenAICompatibleAI, _office_retry_delay
from jarvis.tasks import COMPLETED, FAILED, PENDING_APPROVAL, RUNNING, TaskStore
from jarvis.ui.app import JarvisApp
from jarvis.ui.widgets import TaskPanel


@pytest.fixture(autouse=True)
def sleep():
    with patch("jarvis.llm.time.sleep") as sleep_mock:
        yield sleep_mock


def provider(name):
    if name == "gemini":
        return GeminiAI("secret-key", "fake-model")
    return OpenAICompatibleAI("secret-key", "fake-model", "https://fake.invalid/v1", "TestAI")


def ok(name):
    content = json.dumps({"title": "Ready"})
    result = {"candidates": [{"content": {"parts": [{"text": content}]}}]} if name == "gemini" else {"choices": [{"message": {"content": content}}]}
    return BytesIO(json.dumps(result).encode())


def http(code, headers=None):
    return HTTPError("https://fake.invalid/?key=secret-key", code, "private source text", headers or {}, BytesIO(b"secret-key and private source"))


@pytest.mark.parametrize("name", ["gemini", "compatible"])
def test_503_then_success_retries_same_request_without_rerouting(name, sleep):
    progress = Mock()
    with patch("jarvis.llm.urlopen", side_effect=[http(503), http(503), ok(name)]) as network:
        assert provider(name).complete_json("System", "Private prompt", progress=progress) == {"title": "Ready"}
    assert network.call_count == 3
    assert len({id(call.args[0]) for call in network.call_args_list}) == 1
    assert [call.args[0] for call in sleep.call_args_list] == [2, 4]
    assert progress.call_count == 2
    assert "3/4" in progress.call_args.args[0]
    assert "secret-key" not in str(progress.call_args_list)
    assert "Private prompt" not in str(progress.call_args_list)


@pytest.mark.parametrize("code", [408, 429, 500, 502, 503, 504])
def test_retry_is_bounded_with_correct_final_error(code, sleep):
    with patch("jarvis.llm.urlopen", side_effect=lambda *a, **kw: (_ for _ in ()).throw(http(code))) as network:
        with pytest.raises(AIError) as caught:
            provider("gemini").complete_json("System", "Private prompt")
    assert network.call_count == 4
    assert [call.args[0] for call in sleep.call_args_list] == [2, 4, 8]
    message = str(caught.value)
    assert f"({code})" in message
    assert "secret-key" not in message and "Private prompt" not in message
    assert "https://" not in message
    if code == 503:
        assert "4 ta urinish" in message
        assert "kalit noto'g'ri degani emas" in message
        assert "JSON rejimini" not in message


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_permanent_errors_do_not_retry(code, sleep):
    with patch("jarvis.llm.urlopen", side_effect=http(code)) as network, pytest.raises(AIError):
        provider("gemini").complete_json("System", "Prompt")
    assert network.call_count == 1
    sleep.assert_not_called()


def test_retry_after_is_respected_and_long_cooldowns_do_not_retry_early(sleep):
    with patch("jarvis.llm.urlopen", side_effect=[http(429, {"Retry-After": "12"}), ok("gemini")]):
        provider("gemini").complete_json("System", "Prompt")
    sleep.assert_called_once_with(12)
    sleep.reset_mock()
    with patch("jarvis.llm.urlopen", side_effect=http(429, {"Retry-After": "120"})) as network, pytest.raises(AIError):
        provider("gemini").complete_json("System", "Prompt")
    assert network.call_count == 1
    sleep.assert_not_called()
    assert _office_retry_delay(http(503, {"Retry-After": "invalid"}), 1) == 2


def test_transient_connection_failure_recovers(sleep):
    with patch("jarvis.llm.urlopen", side_effect=[URLError("private detail"), TimeoutError(), ok("gemini")]):
        assert provider("gemini").complete_json("System", "Prompt")["title"] == "Ready"
    assert sleep.call_count == 2


def test_retry_after_http_date_is_respected():
    from datetime import datetime, timezone, timedelta
    from email.utils import format_datetime
    now = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
    with patch("jarvis.llm.datetime") as clock:
        clock.now.return_value = now
        assert _office_retry_delay(http(503, {"Retry-After": format_datetime(now+timedelta(seconds=12))}), 1) == 12


def test_office_service_creates_real_docx_after_503_recovery(tmp_path):
    from docx import Document
    from jarvis.office.service import OfficeService
    spec = {"title": "Ona Vatan", "sections": [{"heading": "Vatan", "paragraphs": ["Vatan — insonning aziz maskani."]}]}
    response = {"candidates": [{"content": {"parts": [{"text": json.dumps(spec)}]}}]}
    progress = Mock()
    with patch("jarvis.llm.urlopen", side_effect=[http(503), BytesIO(json.dumps(response).encode())]) as network:
        result = OfficeService(tmp_path / "outputs").run("office_create", {"format": "docx", "prompt": "Ona vatan haqida esse yoz"}, ai=provider("gemini"), progress=progress)
    assert network.call_count == 2
    assert result.path.is_file()
    assert any("aziz maskani" in paragraph.text for paragraph in Document(result.path).paragraphs)
    progress.assert_called_once()


def test_retry_clones_failed_office_task_but_rechecks_source_consent(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    try:
        payload = {"format": "docx", "prompt": "Make a document", "source": str(tmp_path / "source.txt")}
        old = store.create("Old", "office", "office_create", json.dumps(payload))
        store.update(old.id, FAILED, "Old 503")
        app = Mock()
        app.tasks, app._office_retries = store, {}
        def submit(action, data):
            return store.create("Retry", "office", action, json.dumps(data))
        app._submit_office_task.side_effect = submit
        retried = JarvisApp._retry_office_task(app, old.id)
        assert retried.id != old.id
        assert retried.status == PENDING_APPROVAL and retried.requires_approval
        assert store.get(old.id).result == "Old 503"
        assert JarvisApp._retry_office_task(app, old.id).id == retried.id
        assert app._submit_office_task.call_count == 1
        store.update(retried.id, COMPLETED)
        store.clear_completed()
        assert JarvisApp._retry_office_task(app, old.id).id != old.id
    finally:
        store.close()


def test_progress_is_updated_on_ui_thread_without_finishing_task(tmp_path):
    import queue
    store = TaskStore(tmp_path / "tasks.db")
    try:
        task = store.create("Creating", "office", "office_create", '{"format":"docx","prompt":"Create document"}')
        store.update(task.id, RUNNING)
        app = Mock(tasks=store, events=queue.Queue())
        app.events.put(("task_progress", (task.id, "503: retry 2/4")))
        JarvisApp._read_events(app)
        assert store.get(task.id).status == RUNNING
        assert store.get(task.id).result == "503: retry 2/4"
    finally:
        store.close()


def test_task_panel_retry_only_handles_failed_office():
    app = Mock()
    app._selected_task.return_value = SimpleNamespace(id=19, status=FAILED, action="office_create")
    TaskPanel._approve_selected(app)
    app.retry.assert_called_once_with(19)
    app.approve.assert_not_called()
    app.retry.reset_mock()
    app._selected_task.return_value.action = "desktop_click"
    TaskPanel._approve_selected(app)
    app.retry.assert_not_called()
