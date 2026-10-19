import json
from pathlib import Path
import tempfile
import sys
from unittest.mock import Mock, patch
import zipfile

import pytest

from jarvis.computer.catalog import SKILLS, validate_action
from jarvis.computer.commands import ground_computer_intent, local_computer_intent
from jarvis.computer.files import FileEngine, valid_name
from jarvis.computer.platform import ApplicationNotFound, PlatformEngine, open_file
from jarvis.computer.service import ComputerService, PLATFORM_SKILLS
from jarvis.intent import AIIntent
from jarvis.task_policy import approval_reason
from jarvis.tasks import PENDING_APPROVAL, PLANNED, TaskPlanner, TaskStore


@pytest.fixture
def local(tmp_path):
    # Production intentionally blocks AppData, where pytest's Windows tmp_path
    # normally lives. Use an explicitly scoped disposable workspace instead.
    with tempfile.TemporaryDirectory(prefix='computer-check-', dir=Path(__file__).parent) as directory:
        root = Path(directory).resolve()
        folder = root/'documents'
        folder.mkdir()
        (folder/'report.txt').write_text('alpha\nbeta\n', encoding='utf-8')
        (folder/'copy.txt').write_text('alpha\nbeta\n', encoding='utf-8')
        (folder/'empty').mkdir()
        yield FileEngine([root], tmp_path/'state'), root, folder


def request(key, args=None):
    return {'skill': key, 'args': args or {}}


def test_exactly_fifty_unique_real_capabilities():
    assert len(SKILLS) == 50
    assert len({skill.key for skill in SKILLS.values()}) == 50
    assert all(skill.title and skill.group for skill in SKILLS.values())


@pytest.mark.parametrize('key', SKILLS)
def test_all_fifty_dispatch_and_approval_boundaries(key, tmp_path):
    service = ComputerService(roots=[tmp_path], storage=tmp_path/'state', platform=Mock())
    service.files = Mock()
    service.files.execute.return_value = {'ok': True}
    service.platform.execute.return_value = {'ok': True}
    skill = SKILLS[key]
    args = {field: 'sample' for field in skill.required}
    if skill.approval:
        with pytest.raises(PermissionError):
            service.run(request(key, args))
        service.files.execute.assert_not_called()
        service.platform.execute.assert_not_called()
    assert 'ok' in service.run(request(key, args), approved=True)
    expected = service.platform if key in PLATFORM_SKILLS else service.files
    expected.execute.assert_called_once_with(key, args)


@pytest.mark.parametrize('key', [key for key in SKILLS if key not in PLATFORM_SKILLS])
def test_each_file_capability_nominal_handler(key, local):
    engine, root, folder = local
    source = folder/'report.txt'
    args = {'path': str(source)}
    if key in {'file_find', 'text_search'}:
        args = {'query': 'report' if key == 'file_find' else 'alpha'}
    elif key in {'duplicates', 'largest_files', 'recent_files', 'inventory_export'}:
        args = {'root': str(root)}
    elif key.startswith('folder_') or key in {'organize_preview', 'zip_create'}:
        args = {'path': str(folder)}
    if key == 'text_create':
        args = {'path': str(root/'new.txt'), 'text': 'hello'}
    if key == 'text_append':
        args['text'] = 'tail'
    if key == 'text_replace':
        args.update(old='alpha', new='omega')
    if key.endswith('_rename'):
        args['name'] = 'renamed' if key.startswith('folder') else 'renamed.txt'
    if key.endswith(('_move', '_copy')):
        args['destination'] = str(root/('destination' if key.startswith('folder') else 'destination.txt'))
    if key == 'folder_create':
        args['path'] = str(root/'fresh')
    if key in {'file_compare', 'text_diff'}:
        args['other'] = str(folder/'copy.txt')
    if key == 'zip_create':
        args['destination'] = str(root/'created.zip')
    if key in {'zip_inspect', 'zip_extract'}:
        archive = root/'source.zip'
        with zipfile.ZipFile(archive, 'x') as stream:
            stream.writestr('nested/example.txt', 'example')
        args = {'path': str(archive)}
        if key == 'zip_extract':
            args['destination'] = str(root/'extracted')
    if key == 'backup_list':
        args = {}
    if key == 'backup_restore':
        engine.execute('text_append', {'path': str(source), 'text': 'tail'})
        args = {'id': engine.execute('backup_list', {})[-1]['id']}
    if key == 'organize_apply':
        args = {'id': engine.execute('organize_preview', {'path': str(folder)})['plan_id']}
    with patch('jarvis.computer.platform.open_file', return_value='opened') as opened, \
         patch('jarvis.computer.platform.reveal_file', return_value='revealed') as revealed, \
         patch('pyperclip.copy') as clipboard, patch('send2trash.send2trash') as recycle:
        result = engine.execute(key, args)
        assert result is not None
        if key == 'file_open':
            opened.assert_called_once_with(source)
        if key == 'file_reveal':
            revealed.assert_called_once_with(source)
        if key == 'clipboard_copy_path':
            clipboard.assert_called_once_with(str(source))
        if key == 'file_recycle':
            recycle.assert_called_once_with(str(source))
    if key == 'text_create':
        assert (root/'new.txt').read_text(encoding='utf-8') == 'hello'
    if key == 'text_replace':
        assert source.read_text(encoding='utf-8').startswith('omega')
    if key == 'text_append':
        assert source.read_text(encoding='utf-8').endswith('tail')
    if key == 'backup_restore':
        assert source.read_text(encoding='utf-8') == 'alpha\nbeta\n'
    if key in {'file_move', 'folder_move', 'file_rename', 'folder_rename'}:
        assert not Path(args['path']).exists()
    if key == 'folder_copy':
        assert (root/'destination/empty').is_dir()
        assert (root/'destination/report.txt').read_bytes() == source.read_bytes()
    if key == 'zip_extract':
        assert (root/'extracted/nested/example.txt').read_text() == 'example'
    if key == 'file_compare':
        assert result['same'] is True
    if key == 'file_find':
        assert result['matches'][0]['path'] == str(source)
    if key == 'duplicates':
        assert {str(source), str(folder/'copy.txt')} in [set(group) for group in result['groups']]
    if key == 'zip_create':
        with zipfile.ZipFile(root/'created.zip') as archive:
            assert 'empty/' in archive.namelist()
            assert archive.read('report.txt') == source.read_bytes()


@pytest.mark.parametrize('name', ['.env', '.env.local', 'connections.json', 'voice.json', 'secret.pem', 'secret.key'])
def test_secret_files_cannot_be_read_or_indexed(name, local):
    engine, root, _ = local
    path = root/name
    path.write_text('private')
    with pytest.raises(ValueError):
        engine.execute('text_read', {'path': str(path)})
    assert not any(row['path'] == str(path) for row in engine.execute('file_find', {'query': name})['matches'])


def test_outside_scope_and_traversal_rejected(local):
    engine, root, folder = local
    with pytest.raises(ValueError):
        engine.execute('text_create', {'path': str(root.parent/'outside.txt'), 'text': 'no'})
    with pytest.raises(ValueError):
        engine.execute('file_move', {'path': str(folder/'report.txt'), 'destination': str(root.parent/'outside.txt')})
    assert not (root.parent/'outside.txt').exists()


def test_ambiguous_names_are_not_guessed(local):
    engine, root, folder = local
    (root/'report.txt').write_text('different')
    with pytest.raises(ValueError, match='Aniq bitta'):
        engine.execute('text_append', {'path': 'report.txt', 'text': 'no'})
    assert (root/'report.txt').read_text() == 'different'


def test_named_file_can_be_found_and_edited_when_unique(local):
    engine, _, folder = local
    engine.execute('text_append', {'path': 'REPORT.txt', 'text': 'yes'})
    assert (folder/'report.txt').read_text().endswith('yes')


def test_create_and_copy_never_overwrite(local):
    engine, root, folder = local
    target = folder/'copy.txt'
    before = target.read_bytes()
    for key, args in [('text_create', {'path': str(target), 'text': 'no'}),
                      ('file_copy', {'path': str(folder/'report.txt'), 'destination': str(target)}),
                      ('file_move', {'path': str(folder/'report.txt'), 'destination': str(target)})]:
        with pytest.raises(ValueError):
            engine.execute(key, args)
    assert target.read_bytes() == before
    assert (folder/'report.txt').exists()


def test_restore_refuses_to_destroy_new_work(local):
    engine, _, folder = local
    source = folder/'report.txt'
    engine.execute('text_append', {'path': str(source), 'text': 'edited'})
    identifier = engine.execute('backup_list', {})[-1]['id']
    source.write_text('new external work')
    with pytest.raises(ValueError, match='keyin'):
        engine.execute('backup_restore', {'id': identifier})
    assert source.read_text() == 'new external work'


def test_move_undo_and_edit_backup_are_real(local):
    engine, root, folder = local
    source = folder/'report.txt'
    original = source.read_bytes()
    destination = root/'moved.txt'
    engine.execute('file_move', {'path': str(source), 'destination': str(destination)})
    record = engine.execute('backup_list', {})[-1]
    engine.execute('backup_restore', {'id': record['id']})
    assert source.read_bytes() == original and not destination.exists()
    engine.execute('text_append', {'path': str(source), 'text': 'hello'})
    record = engine.execute('backup_list', {})[-1]
    assert Path(record['backup']).read_bytes() == original


def test_utf8_bom_and_windows_newlines_survive_edit(local):
    engine, _, folder = local
    source = folder/'report.txt'
    source.write_bytes(b'\xef\xbb\xbfalpha\r\nbeta\r\n')
    engine.execute('text_replace', {'path': str(source), 'old': 'alpha', 'new': 'omega'})
    assert source.read_bytes() == b'\xef\xbb\xbfomega\r\nbeta\r\n'


def test_organize_requires_validated_unchanged_plan(local):
    engine, _, folder = local
    plan = engine.execute('organize_preview', {'path': str(folder)})
    (folder/'report.txt').write_text('new')
    with pytest.raises(ValueError, match='o‘zgargan|o.zgargan'):
        engine.execute('organize_apply', {'id': plan['plan_id']})
    assert not (folder/'TXT').exists()


@pytest.mark.parametrize('name', ['../escape.txt', '/absolute.txt', 'C:/outside.txt', 'x:stream.txt', 'CON.txt', 'nested/NUL', 'bad./file.txt'])
def test_hostile_zip_paths_rejected_before_output_created(name, local):
    engine, root, _ = local
    archive = root/'bad.zip'
    with zipfile.ZipFile(archive, 'x') as stream:
        stream.writestr(name, 'unsafe')
    with pytest.raises(ValueError):
        engine.execute('zip_extract', {'path': str(archive), 'destination': str(root/'out')})
    assert not (root/'out').exists()


def test_zip_case_collisions_and_symlinks_rejected(local):
    engine, root, _ = local
    for mode in ['collision', 'symlink']:
        archive = root/(mode+'.zip')
        with zipfile.ZipFile(archive, 'x') as stream:
            if mode == 'collision':
                stream.writestr('file.txt', 'a')
                stream.writestr('FILE.txt', 'b')
            else:
                entry = zipfile.ZipInfo('link')
                entry.create_system = 3
                entry.external_attr = 0o120777 << 16
                stream.writestr(entry, '../elsewhere')
        with pytest.raises(ValueError):
            engine.execute('zip_inspect', {'path': str(archive)})


def test_protected_nested_folder_not_copied(local):
    engine, root, folder = local
    (folder/'.env').write_text('key')
    with pytest.raises(ValueError):
        engine.execute('folder_copy', {'path': str(folder), 'destination': str(root/'copy')})
    assert not (root/'copy').exists()


@pytest.mark.parametrize('name', ['CON', 'nul.txt', 'COM1.log', 'CON .txt', 'bad.', '../other', 'a:b'])
def test_windows_reserved_names_rejected(name):
    with pytest.raises(ValueError):
        valid_name(name)


@pytest.mark.parametrize('data', [None, {'skill': 'shell', 'args': {}}, {'skill': 'file_find', 'args': {'query': 'x', 'evil': 'x'}},
    {'skill': 'file_find', 'args': {'query': 5}}, {'skill': 'file_find', 'args': {'query': 'x', 'limit': '1000'}},
    {'skill': 'text_replace', 'args': {'path': 'x', 'new': 'y'}}, {'skill': 'file_find', 'args': {'query': '\x00'}}])
def test_strict_action_schema(data):
    with pytest.raises(ValueError):
        validate_action(data)


def test_planner_policy_and_local_shortcuts(local):
    engine, root, _ = local
    store = TaskStore(root/'tasks.db')
    try:
        planner = TaskPlanner(store)
        read = planner.plan_ai_command('computer_action', json.dumps(request('file_find', {'query': 'report'})))
        write = planner.plan_ai_command('computer_action', json.dumps(request('text_create', {'path': str(root/'new.txt'), 'text': 'x'})))
        assert read.status == PLANNED
        assert write.status == PENDING_APPROVAL and write.approval_reason
        assert local_computer_intent('report.txt nomli faylni top').command == 'computer_action'
        assert json.loads(local_computer_intent('mrt bilan virusni tekshir').target)['skill'] == 'mrt_open'
        assert local_computer_intent('Virus nima?') is None
        assert local_computer_intent('Chrome ilovasini och').is_command
    finally:
        store.close()


def test_ai_cannot_invent_file_paths(local):
    _, root, folder = local
    data = request('text_append', {'path': str(folder/'report.txt'), 'text': 'hello'})
    intent = AIIntent('command', 'tayyor', 'computer', 'computer_action', json.dumps(data))
    assert not ground_computer_intent('reportni o‘zgartir', intent).is_command
    assert ground_computer_intent(str(folder/'report.txt')+' ga hello qo‘sh', intent).is_command


def test_cached_index_does_not_rescan_on_each_query(local):
    engine, _, _ = local
    engine.execute('file_find', {'query': 'report'})
    with patch.object(engine.scope, 'walk', side_effect=AssertionError('unnecessary scan')):
        for _ in range(10):
            assert engine.execute('file_find', {'query': 'report'})['matches']


def test_store_search_escapes_uri_and_never_installs():
    engine = PlatformEngine()
    with patch('jarvis.computer.platform.windows'), patch('os.startfile', create=True) as start, patch('subprocess.Popen') as process:
        result = engine.execute('store_search', {'name': 'App & editor'})
    start.assert_called_once_with('ms-windows-store://search/?query=App%20%26%20editor')
    process.assert_not_called()
    assert 'o‘zingiz' in result


def test_missing_app_is_typed_and_ambiguous_apps_are_not_guessed():
    engine = PlatformEngine()
    engine.apps = lambda: [{'name': 'Editor A', 'path': 'C:/Program Files/A.exe'}, {'name': 'Editor B', 'path': 'C:/Program Files/B.exe'}]
    with pytest.raises(ApplicationNotFound):
        engine.resolve('missing')
    with pytest.raises(ValueError, match='Bir nechta'):
        engine.resolve('Editor')
    assert engine.resolve('Editor A')['name'] == 'Editor A'


def test_executable_and_script_files_are_not_opened_as_documents():
    with patch('jarvis.computer.platform.windows'), patch('os.startfile', create=True) as start, patch('subprocess.Popen') as process:
        for extension in ['.exe', '.bat', '.lnk', '.ps1', '.docm', '.url']:
            with pytest.raises(ValueError):
                open_file(Path('danger'+extension))
    start.assert_not_called()
    process.assert_not_called()


def test_mrt_launch_only_no_silent_scan_or_clean():
    binary = Mock()
    binary.is_file.return_value = True
    with patch('jarvis.computer.platform.windows'), patch('jarvis.computer.platform.system_exe', return_value=binary), patch('os.startfile', create=True) as start, patch('subprocess.run') as run:
        result = PlatformEngine().execute('mrt_open', {})
    start.assert_called_once_with(str(binary))
    run.assert_not_called()
    assert 'noma’lum' in result and 'antivirus emas' in result


@pytest.mark.parametrize('mode,expected', [('trim', 'z\na\nz'), ('sort', ' a\nz \nz '), ('unique', 'z \n a')])
def test_clipboard_format_does_not_log_contents(mode, expected):
    with patch('pyperclip.paste', return_value='z \n a\nz '), patch('pyperclip.copy') as copy:
        result = PlatformEngine().execute('clipboard_format', {'mode': mode})
    copy.assert_called_once_with(expected)
    assert 'z ' not in result


@pytest.mark.parametrize('key', ['system_info', 'disk_info', 'process_list', 'battery_info', 'network_info'])
def test_readonly_telemetry_handlers_are_real(key):
    # These only read this test process/system, never launch apps or modify settings.
    result = PlatformEngine().execute(key, {})
    assert isinstance(result, (dict, list))


def test_explicit_extra_root_is_validated_and_persisted(local):
    engine, root, folder = local
    extra = root/'extra'
    extra.mkdir()
    (extra/'external.txt').write_text('sample')
    restricted = FileEngine([folder], engine.storage/'restricted')
    with pytest.raises(ValueError):
        restricted.execute('text_read', {'path': str(extra/'external.txt')})
    restricted.add_root(str(extra))
    assert 'sample' in restricted.execute('text_read', {'path': str(extra/'external.txt')})['text']
    with patch('jarvis.computer.files.default_roots', return_value=[folder]):
        restarted = FileEngine(storage=restricted.storage)
    assert extra in restarted.scope.roots
    with pytest.raises(ValueError):
        restricted.add_root(Path.home())
    with pytest.raises(ValueError):
        restricted.add_root(Path(root.anchor))
    assert 'add_root' not in SKILLS  # A model cannot expand its own access.


def test_scoped_query_does_not_rescan_whole_workspace(local):
    engine, _, folder = local
    engine.execute('file_find', {'query': 'report'})
    with patch.object(engine.scope, 'walk', wraps=engine.scope.walk) as walk:
        result = engine.execute('file_find', {'query': 'report', 'root': str(folder)})
        assert result['matches']
        assert walk.call_args.args[0] == folder
        walk.reset_mock()
        engine.execute('file_find', {'query': 'copy', 'root': str(folder)})
        walk.assert_not_called()


def test_literal_like_characters_do_not_become_wildcards(local):
    engine, root, _ = local
    (root/'a_b.txt').write_text('one')
    (root/'acb.txt').write_text('two')
    matches = engine.execute('file_find', {'query': 'a_b'})['matches']
    assert len(matches) == 1 and Path(matches[0]['path']).name == 'a_b.txt'


def test_zip_file_parent_conflict_rejected_before_any_output(local):
    engine, root, _ = local
    archive = root/'conflict.zip'
    with zipfile.ZipFile(archive, 'x') as stream:
        stream.writestr('parent', 'file')
        stream.writestr('parent/child.txt', 'child')
    with pytest.raises(ValueError):
        engine.execute('zip_extract', {'path': str(archive), 'destination': str(root/'out')})
    assert not (root/'out').exists()


def test_backup_journal_cannot_point_outside_backup_storage(local):
    engine, root, folder = local
    source = folder/'report.txt'
    engine.execute('text_append', {'path': str(source), 'text': 'tail'})
    records = engine.execute('backup_list', {})
    records[-1]['backup'] = str(folder/'copy.txt')
    engine.journal.write_text(json.dumps(records), encoding='utf-8')
    with pytest.raises(ValueError):
        engine.execute('backup_restore', {'id': records[-1]['id']})
    assert source.read_text().endswith('tail')


def test_defender_uses_fixed_readonly_query():
    with patch('jarvis.computer.platform.powershell', return_value='{"AntivirusEnabled":true}') as query:
        result = PlatformEngine().execute('security_status', {})
    assert result['defender']['AntivirusEnabled'] is True
    script = query.call_args.args[0]
    assert 'Get-MpComputerStatus' in script
    assert 'Set-Mp' not in script and 'Start-Mp' not in script


def test_mrt_reads_existing_log_with_explicit_staleness_warning(local):
    _, root, _ = local
    (root/'debug').mkdir()
    (root/'debug/mrt.log').write_text('Existing scan log', encoding='utf-8')
    with patch('jarvis.computer.platform.windows'), patch.dict('os.environ', {'SystemRoot': str(root)}):
        result = PlatformEngine().execute('mrt_report', {})
    assert 'Existing scan log' in result['log_tail']
    assert 'eski' in result['note']


def test_app_open_uses_resolved_executable_no_shell_or_arguments():
    engine = PlatformEngine()
    engine.resolve = Mock(return_value={'name': 'Editor', 'path': 'C:/Program Files/Editor.exe'})
    with patch('subprocess.Popen') as popen:
        engine.execute('app_open', {'name': 'Editor'})
    popen.assert_called_once_with(['C:/Program Files/Editor.exe'], shell=False)


def test_automatic_builtins_cannot_be_shadowed_by_registry_or_shortcuts(local):
    _, root, _ = local
    binary = root/'notepad.exe'
    binary.touch()
    engine = PlatformEngine()
    engine.apps = Mock(side_effect=AssertionError('Built-ins should not scan registry or shortcuts'))
    with patch('jarvis.computer.platform.windows'), patch('jarvis.computer.platform.system_exe', return_value=binary):
        assert engine.resolve('bloknot')['path'] == str(binary)
        assert engine.resolve('ms-settings:')['path'] == 'ms-settings:'
    engine.apps.assert_not_called()


def test_app_inventory_and_find_use_the_same_catalog():
    engine = PlatformEngine()
    engine.apps = Mock(return_value=[{'name': 'Notepad', 'path': 'C:/Windows/notepad.exe'}])
    assert engine.execute('app_inventory', {})['apps'][0]['name'] == 'Notepad'
    assert engine.execute('app_find', {'name': 'bloknot'})['matches'][0]['name'] == 'Notepad'


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows shortcut COM integration')
def test_shortcut_creation_is_exclusive_and_uses_resolved_app(local):
    _, root, _ = local
    engine = PlatformEngine()
    engine.resolve = Mock(return_value={'name': 'Editor', 'path': 'C:/Program Files/Editor.exe'})
    link = Mock()
    def shortcut(path):
        link.Save.side_effect = lambda: Path(path).write_bytes(b'test-shortcut')
        return link
    shell = Mock()
    shell.CreateShortcut.side_effect = shortcut
    with patch('jarvis.office.destinations.desktop_directory', return_value=root), patch('pythoncom.CoInitialize'), patch('pythoncom.CoUninitialize'), patch('win32com.client.Dispatch', return_value=shell):
        assert 'Editor.lnk' in engine.execute('app_shortcut', {'name': 'Editor'})
        with pytest.raises(ValueError):
            engine.execute('app_shortcut', {'name': 'Editor'})
    assert link.TargetPath == 'C:/Program Files/Editor.exe'
    assert (root/'Editor.lnk').read_bytes() == b'test-shortcut'
