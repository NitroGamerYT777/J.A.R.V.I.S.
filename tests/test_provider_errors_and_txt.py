from io import BytesIO
import json
import queue
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import pytest

from jarvis.connections import ConnectionStore
from jarvis.llm import AIError, GeminiAI, OpenAICompatibleAI
from jarvis.office.commands import local_text_creation_intent
from jarvis.office.destinations import wants_desktop
from jarvis.office.service import OfficeService
from jarvis.ui.app import JarvisApp


def provider(name):
    return GeminiAI('fake-secret', 'test-model') if name == 'gemini' else OpenAICompatibleAI('fake-secret', 'test-model', 'https://fake.invalid/v1', 'TestAI')


def failure(code, details=None, headers=None, **extra):
    error = {'code': code, 'message': 'private user text and fake-secret', **extra}
    if details is not None:
        error['details'] = details
    return HTTPError('https://fake.invalid/?key=fake-secret', code, 'private', headers or {}, BytesIO(json.dumps({'error': error}).encode()))


def answer(name):
    text = json.dumps({'type': 'answer', 'reply': 'Salom!'})
    data = {'candidates': [{'content': {'parts': [{'text': text}]}}]} if name == 'gemini' else {'choices': [{'message': {'content': text}}]}
    return BytesIO(json.dumps(data).encode())


@pytest.mark.parametrize('name', ['gemini', 'compatible'])
def test_chat_503_retries_then_returns_answer(name):
    ai, progress = provider(name), Mock()
    with patch('jarvis.llm.urlopen', side_effect=[failure(503), answer(name)]) as network, patch('jarvis.llm.time.sleep') as sleep:
        assert ai.interpret('salom', progress=progress).reply == 'Salom!'
    assert network.call_count == 2
    sleep.assert_called_once_with(2)
    assert '2/4' in progress.call_args.args[0]


@pytest.mark.parametrize('name', ['gemini', 'compatible'])
def test_daily_quota_is_not_retried_or_reported_as_invalid_key(name):
    details = [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [
        {'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaValue': '0'}]}]
    with patch('jarvis.llm.urlopen', side_effect=lambda *a, **k: (_ for _ in ()).throw(failure(429, details))) as network, patch('jarvis.llm.time.sleep') as sleep:
        with pytest.raises(AIError) as caught:
            provider(name).interpret('private user request')
    assert network.call_count == 1
    sleep.assert_not_called()
    assert caught.value.kind == 'quota'
    assert caught.value.status_code == 429
    assert 'yangi' in str(caught.value)
    assert 'fake-secret' not in str(caught.value) and 'private user' not in str(caught.value)
    assert 'https://' not in str(caught.value)


def test_temporary_rate_limit_respects_google_retry_info():
    details = [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '12s'}]
    with patch('jarvis.llm.urlopen', side_effect=[failure(429, details), answer('gemini')]), patch('jarvis.llm.time.sleep') as sleep:
        assert provider('gemini').interpret('salom').reply == 'Salom!'
    sleep.assert_called_once_with(12)


@pytest.mark.parametrize('headers,details', [({'Retry-After': '120'}, []), ({}, [{'retryDelay': '120s'}])])
def test_long_retry_hint_is_not_ignored(headers, details):
    with patch('jarvis.llm.urlopen', side_effect=failure(429, details, headers)) as network, patch('jarvis.llm.time.sleep') as sleep:
        with pytest.raises(AIError) as caught:
            provider('gemini').interpret('salom')
    assert caught.value.retry_after == 120
    assert caught.value.kind == 'rate_limit'
    assert network.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize('code,details,kind', [(401, [], 'auth'), (403, [], 'permission'),
    (400, [{'reason': 'API_KEY_INVALID'}], 'auth'), (404, [], 'model')])
def test_error_kinds_are_not_conflated(code, details, kind):
    with patch('jarvis.llm.urlopen', side_effect=failure(code, details)), patch('jarvis.llm.time.sleep') as sleep:
        with pytest.raises(AIError) as caught:
            provider('gemini').interpret('hello')
    assert caught.value.kind == kind
    sleep.assert_not_called()


def test_ui_does_not_multiply_the_shared_retry_loop():
    connection = SimpleNamespace(id='original')
    app = SimpleNamespace(ai=provider('gemini'), active_connection=connection, events=queue.Queue(), _local_intent=lambda _: None)
    with patch('jarvis.llm.urlopen', side_effect=lambda *a, **k: (_ for _ in ()).throw(failure(503))) as network, patch('jarvis.llm.time.sleep'):
        JarvisApp._reply(app, 'oddiy savol')
    assert network.call_count == 4
    events = list(app.events.queue)
    assert [value[0] for kind, value in events if kind == 'connection_issue'] == ['original']
    assert isinstance(next(value for kind, value in events if kind == 'provider_error'), AIError)


def test_status_persistence_and_duplicate_key_do_not_reset_quota(tmp_path):
    with patch.dict('os.environ', {'AI_API_KEY': '', 'GEMINI_API_KEY': ''}):
        store = ConnectionStore(tmp_path/'connections.json')
    connection = store.add('gemini', 'test-model', 'fake-secret')
    assert connection.status == 'untested'
    store.mark_error(connection.id, AIError('429 quota', kind='quota', status_code=429))
    duplicate = store.add('gemini', 'test-model', 'fake-secret')
    assert duplicate.id == connection.id and duplicate.status == 'quota'
    assert len(store.connections) == 1
    store.mark_ready(connection.id)
    assert connection.status == 'ready' and not connection.last_error
    store.mark_error(connection.id, AIError('403 permission', kind='permission', status_code=403))
    assert connection.status == 'permission_denied'


@pytest.mark.parametrize('kind,code', [('quota', 429), ('rate_limit', 429), ('unavailable', 503), ('permission', 403)])
def test_ui_never_offers_key_deletion_for_quota_service_or_permission(kind, code, tmp_path):
    with patch.dict('os.environ', {'AI_API_KEY': '', 'GEMINI_API_KEY': ''}):
        store = ConnectionStore(tmp_path/'connections.json')
    connection = store.add('gemini', 'test', 'fake')
    app = SimpleNamespace(connections=store, active_connection=connection, connection=Mock(),
        _connection_badge=lambda: ('quota', '#ffffff'), _add_feed=Mock())
    with patch('jarvis.ui.app.messagebox.askyesno') as ask:
        JarvisApp._connection_issue(app, connection.id, AIError('error', kind=kind, status_code=code))
    ask.assert_not_called()
    assert store.get(connection.id) is connection


@pytest.mark.parametrize('message', ["jarvis mavzusida she'r yoz va desktopda .txt qilib saqla",
    'JARVIS haqida matn yarat va ish stoliga txt formatida saqla'])
def test_explicit_txt_request_needs_no_router_and_preserves_prompt(message):
    intent = local_text_creation_intent(message)
    assert intent.command == 'office_create'
    data = json.loads(intent.target)
    assert data['format'] == 'txt' and data['prompt'] == message
    assert data['save_to'] == 'desktop' and wants_desktop(message)
    app = SimpleNamespace(ai=Mock(), events=queue.Queue())
    JarvisApp._reply(app, message)
    app.ai.interpret.assert_not_called()
    assert app.events.get_nowait()[0] == 'intent'


@pytest.mark.parametrize('message', ['TXT faylni qanday saqlash mumkinmi?', 'report.txt faylini tahrirla va saqla',
    'C:/Folder/input.txt faylini o‘qib qayta yoz va saqla', 'JARVIS haqida savol',
    'She’r yoz va desktopda txt hamda pdf qilib saqla', 'She’r yoz va .txt qilib saqlama',
    'TXT matn yaratma, faqat saqlash yo‘lini tushuntir'])
def test_local_authoring_does_not_hijack_questions_edits_or_ambiguous_formats(message):
    assert local_text_creation_intent(message) is None


def test_txt_poem_is_really_saved_to_desktop_with_line_breaks(tmp_path):
    desktop = tmp_path/'desktop'
    desktop.mkdir()
    poem = 'JARVIS, raqamli hamrohim,\nSen bilan yorug‘ yo‘lim.\n\nHar bir so‘rov — yangi kun.\n'
    ai = Mock()
    ai.complete_json.return_value = {'title': 'JARVIS she’ri', 'text': poem}
    intent = local_text_creation_intent("jarvis mavzusida she'r yoz va desktopda .txt qilib saqla")
    with patch('jarvis.office.service.desktop_directory', return_value=desktop):
        result = OfficeService(tmp_path/'outputs').run('office_create', json.loads(intent.target), ai=ai)
    assert result.path.suffix == '.txt'
    assert result.path.read_text(encoding='utf-8') == poem
    assert result.extra_paths[0].parent == desktop
    assert result.extra_paths[0].read_bytes() == poem.encode('utf-8')
    ai.complete_json.assert_called_once()
    assert 'FORMAT: txt' in ai.complete_json.call_args.args[1]


def test_quota_failure_creates_no_fake_or_empty_document(tmp_path):
    desktop = tmp_path/'desktop'
    desktop.mkdir()
    ai = Mock()
    ai.complete_json.side_effect = AIError('Quota tugagan', kind='quota', status_code=429)
    with patch('jarvis.office.service.desktop_directory', return_value=desktop), pytest.raises(AIError):
        OfficeService(tmp_path/'outputs').run('office_create', {'format': 'txt', 'prompt': 'She’r yoz va desktopda saqla'}, ai=ai)
    assert not list(desktop.iterdir())
    assert not (tmp_path/'outputs').exists()


def test_refusal_is_not_saved_as_a_fake_poem(tmp_path):
    ai = Mock()
    ai.complete_json.return_value = {'refusal': 'Model bu mavzuga javob bera olmaydi.'}
    with pytest.raises(AIError) as caught:
        OfficeService(tmp_path/'outputs').run('office_create', {'format': 'txt', 'prompt': 'She’r yoz'}, ai=ai)
    assert caught.value.kind == 'refusal'
    assert not (tmp_path/'outputs').exists()
    ai.complete_json.assert_called_once()


def test_provider_content_filter_does_not_look_like_expired_key():
    raw = json.dumps({'promptFeedback': {'blockReason': 'SAFETY'}}).encode()
    with patch('jarvis.llm.urlopen', return_value=BytesIO(raw)):
        with pytest.raises(AIError) as caught:
            provider('gemini').complete_json('schema', 'request')
    assert caught.value.kind == 'refusal'


def test_existing_non_gemini_connection_can_become_default_chat_ai(tmp_path):
    with patch.dict('os.environ', {'AI_API_KEY': '', 'GEMINI_API_KEY': ''}):
        store = ConnectionStore(tmp_path/'connections.json')
    store.add('gemini', 'test-gemini', 'fake-gemini')
    chosen = store.add('groq', 'test-groq', 'fake-groq')
    app = SimpleNamespace(connections=store, connection=Mock(), agent=Mock(), _add_feed=Mock())
    app._connection_badge = lambda: JarvisApp._connection_badge(app)
    with patch('jarvis.ui.app.build_ai', return_value=Mock()) as build:
        JarvisApp._activate_connection(app, chosen.id)
    assert store.default_id == chosen.id
    assert app.active_connection is chosen
    assert app.agent.ai is app.ai
    build.assert_called_once_with(chosen)
