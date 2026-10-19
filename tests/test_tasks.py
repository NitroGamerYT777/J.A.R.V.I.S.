from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from jarvis.intent import AIIntent
from jarvis.task_policy import approval_reason
from jarvis.tasks import COMPLETED, FAILED, PENDING_APPROVAL, PLANNED, REJECTED, RUNNING, TaskPlanner, TaskStore
from jarvis.ui.app import JarvisApp


@pytest.mark.parametrize(("action", "payload"), [
    ("browser_open", "example.com"),
    ("open_url", "https://example.com/page?q=python"),
    ("search_web", "delete account instructions"),
    ("browser_read", ""),
    ("browser_set_theme", '{"theme":"dark"}'),
    ("browser_scroll", '{"direction":"down"}'),
    ("browser_click", '{"element":"Search"}'),
    ("browser_new_tab", ""),
    ("desktop_focus", '{"title":"Notepad"}'),
    ("desktop_type", '{"text":"Salom dunyo"}'),
    ("browser_type", '{"field":"Search","text":"Python"}'),
    ("desktop_launch", '{"program":"notepad.exe","args":[]}'),
    ("run_app", "kalkulyator"),
    ("desktop_hotkey", '{"keys":"alt+tab"}'),
    ("desktop_press", '{"key":"tab"}'),
    ("desktop_screenshot", ""),
    ("desktop_move", '{"x":20,"y":30}'),
    ("play_music", "some song"),
])
def test_ordinary_actions_do_not_ask_for_approval(action, payload):
    assert approval_reason(action, payload) == ""


@pytest.mark.parametrize(("action", "payload"), [
    ("browser_click", '{"element":"Send"}'),
    ("browser_click", '{"element":"Delete account"}'),
    ("browser_click", '{"element":"Buy now"}'),
    ("browser_click", '{"element":"Yuborish"}'),
    ("browser_click", '{"element":"css:#unknown"}'),
    ("browser_press", '{"key":"enter"}'),
    ("desktop_press", '{"key":"delete"}'),
    ("desktop_hotkey", '{"keys":"shift+delete"}'),
    ("desktop_hotkey", '{"keys":"ctrl+s"}'),
    ("desktop_type", '{"text":"Salom\\n"}'),
    ("desktop_type", '{"text":"Remove-Item file.txt"}'),
    ("browser_type", '{"field":"Password","text":"secret"}'),
    ("desktop_launch", '{"program":"powershell.exe","args":[]}'),
    ("desktop_launch", '{"program":"notepad.exe","args":["private.txt"]}'),
    ("desktop_launch", '{"program":"C:\\\\unknown\\\\notepad.exe"}'),
    ("desktop_click", '{"x":20,"y":30}'),
    ("desktop_drag", '{"x":20,"y":30}'),
    ("open_url", "file:///C:/private.exe"),
    ("browser_open", "https://example.com/%64elete/account"),
    ("browser_open", "https://example.com/?action=delete"),
    ("browser_open", "https://user:password@example.com"),
    ("unknown_action", "anything"),
    ("workflow", "not json"),
    ("workflow", '[]'),
    ("workflow", '[{"action":"unknown"}]'),
    ("workflow", '[{"action":[]}]'),
    ("workflow", '[{"action":"desktop_type","target":[]}]'),
])
def test_important_or_opaque_actions_keep_approval(action, payload):
    assert approval_reason(action, payload)


def test_entire_workflow_is_reviewed_before_running_any_step():
    steps = [{"action": "desktop_launch", "target": {"program": "notepad.exe"}},
             {"action": "desktop_focus", "target": {"title": "Notepad"}},
             {"action": "desktop_type", "target": {"text": "Salom"}}]
    assert not approval_reason("workflow", json.dumps(steps))
    steps.append({"action": "desktop_hotkey", "target": {"keys": "ctrl+s"}})
    assert approval_reason("workflow", json.dumps(steps)).startswith("4-qadam:")


def test_store_policy_cleanup_and_pending_priority(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    try:
        safe = store.create("Open", "browser", "browser_open", "example.com")
        assert safe.status == PLANNED
        important = store.create("Delete", "desktop", "desktop_press", '{"key":"delete"}', requires_approval=False)
        assert important.requires_approval
        assert important.status == PENDING_APPROVAL
        assert important.approval_reason
        running = store.create("Running", "browser", "browser_read")
        store.update(running.id, RUNNING)
        failed = store.create("Failed", "browser", "browser_read")
        store.update(failed.id, FAILED)
        rejected = store.create("Rejected", "browser", "browser_read")
        store.update(rejected.id, REJECTED)
        for index in range(35):
            task = store.create(str(index), "browser", "browser_read")
            store.update(task.id, COMPLETED)
        assert store.recent()[0].id == important.id
        assert store.clear_completed() == 35
        assert store.clear_completed() == 0
        for task_id, status in ((safe.id, PLANNED), (important.id, PENDING_APPROVAL), (running.id, RUNNING),
                                (failed.id, FAILED), (rejected.id, REJECTED)):
            assert store.get(task_id).status == status
    finally:
        store.close()


def test_local_plans_use_same_risk_policy(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    try:
        planner = TaskPlanner(store)
        assert not planner.plan("brauzerda och: example.com").requires_approval
        assert not planner.plan("loyiha papkasini och").requires_approval
        assert not planner.plan_ai_command("run_app", "notepad").requires_approval
        assert planner.plan_ai_command("run_app", "powershell").requires_approval
    finally:
        store.close()


def test_ui_auto_runs_safe_ai_task_but_not_important_task(tmp_path):
    import queue
    store = TaskStore(tmp_path / "tasks.db")
    try:
        app = Mock()
        app.tasks, app.planner, app.events = store, TaskPlanner(store), queue.Queue()
        app.events.put(("intent", AIIntent("command", "Ochaman", "browser", "browser_open", "example.com")))
        JarvisApp._read_events(app)
        task = store.recent()[0]
        app._approve_task.assert_called_once_with(task.id)
        app._approve_task.reset_mock()
        app.events.put(("intent", AIIntent("command", "Yuboraman", "browser", "browser_click", '{"element":"Send"}')))
        JarvisApp._read_events(app)
        app._approve_task.assert_not_called()
        assert store.recent()[0].requires_approval
    finally:
        store.close()


def test_running_task_cannot_be_started_twice():
    app = Mock()
    app.tasks.get.return_value.status = RUNNING
    JarvisApp._approve_task(app, 1)
    app.tasks.update.assert_not_called()


def test_local_safe_task_is_started_without_approval(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    try:
        app = Mock()
        app.planner = TaskPlanner(store)
        JarvisApp._send(app, "brauzerda och: example.com")
        app._approve_task.assert_called_once_with(store.recent()[0].id)
    finally:
        store.close()


def test_cleanup_button_refreshes_panel():
    app = Mock()
    app.tasks.clear_completed.return_value = 3
    JarvisApp._clear_completed_tasks(app)
    app.tasks.clear_completed.assert_called_once()
    app._refresh_tasks.assert_called_once()
