import base64
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

import test_web
from sparkle_coder.config import Config
from sparkle_coder.demo import calls, python_command
from sparkle_coder.execution import CommandRunner
from sparkle_coder.provider import Completion
from sparkle_coder.state import Session
from sparkle_coder.tools import ToolSet
from sparkle_coder.webapp import AppService
from sparkle_coder.workspace import Workspace


class ImprovementTests(unittest.TestCase):
    setUp = test_web.WebTests.setUp
    close = test_web.WebTests.close
    request = test_web.WebTests.request
    api = test_web.WebTests.api
    await_run = test_web.WebTests.await_run
    start_demo = test_web.WebTests.start_demo
    finish_demo = test_web.WebTests.finish_demo

    def prefix(self):
        return '/api/projects/' + self.app.data['selected_project']

    def raw(self, path, auth=True):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=8)
        try:
            connection.request('GET', path, headers={'X-Sparkle-Token': self.server.token} if auth else {})
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()

    def upload(self, path, data):
        return self.api(self.prefix() + '/import', {'path': path, 'data': base64.b64encode(data).decode()})

    def local_model(self, factory):
        self.app.provider_factory = factory
        self.api('/api/settings', {'base_url': 'http://127.0.0.1:8000/v1', 'model': 'scripted-test'})

    def start_controlled(self, gate=None, review=False):
        entered = threading.Event()

        class Script:
            phase = 0
            def complete(inner, messages, schemas):
                inner.phase += 1
                if inner.phase == 1:
                    entered.set()
                    if gate:
                        gate.wait(5)
                    return calls(('write_file', {'path': 'new.txt', 'content': 'real write\n'}))
                return Completion('Scripted result.', [], {})
        self.local_model(lambda _: Script())
        run = self.api('/api/runs', {'project_id': self.app.data['selected_project'],
                                   'goal': 'Create a file', 'review_edits': review})
        self.assertTrue(entered.wait(2))
        return run

    def test_import_and_binary_download_preserve_exact_bytes(self):
        original = b'\x00\xffPNG\r\n\x10\x11'
        imported = self.upload('assets/image.bin', original)
        self.assertEqual(imported['bytes'], len(original))
        preview = self.api(self.prefix() + '/file?path=assets/image.bin')
        self.assertTrue(preview['binary'])
        status, data, headers = self.raw(self.prefix() + '/download?path=assets/image.bin')
        self.assertEqual(status, 200)
        self.assertEqual(data, original)
        self.assertIn('attachment', headers['Content-Disposition'])
        self.assertEqual(self.raw(self.prefix() + '/download?path=assets/image.bin', auth=False)[0], 401)

    def test_import_and_duplicate_keep_existing_files(self):
        self.upload('hello.txt', b'original')
        second = self.upload('hello.txt', b'new content')
        self.assertTrue(second['renamed'])
        self.assertEqual(self.api(self.prefix() + '/file?path=hello.txt')['content'], 'original')
        copy = self.api(self.prefix() + '/duplicate', {'source': 'hello.txt', 'destination': 'hello.txt'})
        self.assertNotEqual(copy['path'], second['path'])
        self.assertEqual(self.api(self.prefix() + '/file?path=' + copy['path'].replace(' ', '%20'))['content'], 'original')

    def test_exports_include_build_artifacts_but_exclude_credentials_and_state(self):
        self.upload('dist/app.bin', b'\x00built-software\xff')
        self.upload('src/code.js', b'console.log(42);')
        workspace = self.app.project(self.app.data['selected_project'])[1]
        (workspace.root / '.env').write_text('secret=do-not-export')
        dependency = workspace.root / 'node_modules' / 'ignored'
        dependency.parent.mkdir()
        dependency.write_text('dependency')
        manifest = self.api(self.prefix() + '/export-manifest')
        self.assertEqual(set(manifest['files']), {'dist/app.bin', 'src/code.js'})
        status, data, _ = self.raw(self.prefix() + '/download-project')
        self.assertEqual(status, 200)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(set(archive.namelist()), {'dist/app.bin', 'src/code.js'})
            self.assertEqual(archive.read('dist/app.bin'), b'\x00built-software\xff')
        self.assertEqual(self.raw(self.prefix() + '/download?path=.env')[0], 400)
        self.assertEqual(self.raw(self.prefix() + '/download?path=../settings.json')[0], 400)

    def test_copy_project_to_device_folder_creates_a_new_copy(self):
        self.upload('nested/file.txt', b'keep exactly')
        with tempfile.TemporaryDirectory() as target:
            first = self.api(self.prefix() + '/export-folder', {'path': target})
            second = self.api(self.prefix() + '/export-folder', {'path': target})
            self.assertNotEqual(first['path'], second['path'])
            self.assertEqual((Path(first['path']) / 'nested/file.txt').read_bytes(), b'keep exactly')
            self.assertEqual((Path(second['path']) / 'nested/file.txt').read_bytes(), b'keep exactly')
        project = self.app.project(self.app.data['selected_project'])[1]
        self.assertEqual(self.request(self.prefix() + '/export-folder', {'path': str(project.root / 'recursive')})[0], 400)

    def test_import_rejects_path_escape_and_malformed_data(self):
        for path in ('../outside', '/tmp/outside', '.nemotron/session', '.env', 'node_modules/code'):
            self.assertEqual(self.request(self.prefix() + '/import', {'path': path, 'data': 'eA=='})[0], 400)
        self.assertEqual(self.request(self.prefix() + '/import', {'path': 'file', 'data': '**invalid**'})[0], 400)
        self.assertFalse(self.api(self.prefix() + '/files')['files'])

    def test_import_and_project_export_wait_for_active_task_to_finish(self):
        _, waiting = self.start_demo()
        self.assertEqual(self.request(self.prefix() + '/import', {'path': 'x', 'data': 'eA=='})[0], 400)
        self.assertEqual(self.raw(self.prefix() + '/download-project')[0], 400)
        self.api('/api/runs/' + waiting['id'] + '/stop', {})
        self.await_run(waiting['id'], {'interrupted'})
        self.upload('after-stop', b'ok')

    def test_storage_switch_preserves_history_and_persists_on_restart(self):
        data, run = self.finish_demo()
        original = self.app.directory
        with tempfile.TemporaryDirectory() as parent:
            target = Path(parent) / 'Chosen device folder'
            result = self.api('/api/storage', {'path': str(target)})
            self.assertEqual(result['path'], str(target))
            self.assertEqual(self.api('/api/state')['storage']['path'], str(target))
            moved_project = self.app.project(data['project']['id'])[1]
            self.assertTrue(moved_project.root.is_relative_to(target))
            self.assertIn('return a + b', (moved_project.root / 'calculator.py').read_text())
            self.assertTrue((Path(data['project']['path']) / 'calculator.py').exists())
            reopened = AppService(original)
            self.assertEqual(reopened.directory, target)
            snapshot = reopened.snapshot(data['project']['id'], run['session_id'])
            self.assertEqual(snapshot['status'], 'checked')
            self.assertTrue(snapshot['events'])
            self.assertTrue(reopened.undo(data['project']['id'], run['session_id'])['paths'])
            reopened.close()

    def test_storage_refuses_nonempty_destination_and_preserves_external_project(self):
        with tempfile.TemporaryDirectory() as parent:
            parent = Path(parent)
            external = self.api('/api/projects', {'name': 'External', 'path': str(parent / 'external')})
            occupied = parent / 'occupied'
            occupied.mkdir()
            (occupied / 'precious').write_text('keep')
            original = self.app.directory
            self.assertEqual(self.request('/api/storage', {'path': str(occupied)})[0], 400)
            self.assertEqual(self.app.directory, original)
            self.assertEqual((occupied / 'precious').read_text(), 'keep')
            self.api('/api/storage', {'path': str(parent / 'data')})
            self.assertEqual(self.app.project(external['id'])[0]['path'], external['path'])

    def test_failed_storage_copy_does_not_change_current_location(self):
        original = self.app.directory
        with tempfile.TemporaryDirectory() as parent:
            with patch('sparkle_coder.storage.shutil.copytree', side_effect=OSError('disk full')):
                status, result, _ = self.request('/api/storage', {'path': str(Path(parent) / 'data')})
            self.assertEqual(status, 400)
            self.assertIn('original data remains', result['error'])
            self.assertEqual(self.app.directory, original)
            self.assertFalse((original / 'storage-location.json').exists())

    def test_file_edit_waits_for_diff_approval(self):
        run = self.start_controlled(review=True)
        waiting = self.await_run(run['id'], {'approval'})
        self.assertEqual(waiting['approval']['kind'], 'file edit')
        self.assertIn('+real write', waiting['approval']['diff'])
        self.assertNotIn('new.txt', self.api(self.prefix() + '/files')['files'])
        self.api('/api/runs/' + run['id'] + '/approval', {'approval_id': waiting['approval']['id'], 'allow': True})
        self.await_run(run['id'], {'unverified'})
        self.assertEqual(self.api(self.prefix() + '/file?path=new.txt')['content'], 'real write\n')

    def test_denied_file_edit_does_not_mutate_project(self):
        run = self.start_controlled(review=True)
        waiting = self.await_run(run['id'], {'approval'})
        self.api('/api/runs/' + run['id'] + '/approval', {'approval_id': waiting['approval']['id'], 'allow': False})
        finished = self.await_run(run['id'], {'unverified'})
        self.assertFalse(self.api(self.prefix() + '/files')['files'])
        self.assertFalse(finished['session']['actions'][0]['ok'])

    def test_pause_after_model_response_blocks_the_next_action_until_resume(self):
        gate = threading.Event()
        try:
            run = self.start_controlled(gate=gate)
            self.api('/api/runs/' + run['id'] + '/pause', {})
            gate.set()
            paused = self.await_run(run['id'], {'paused_by_user'})
            self.assertTrue(paused['pause_requested'])
            self.assertNotIn('new.txt', self.api(self.prefix() + '/files')['files'])
            self.api('/api/runs/' + run['id'] + '/resume', {})
            self.await_run(run['id'], {'unverified'})
            self.assertIn('new.txt', self.api(self.prefix() + '/files')['files'])
        finally:
            gate.set()

    def test_stop_while_paused_exits_without_pending_edits(self):
        gate = threading.Event()
        try:
            run = self.start_controlled(gate=gate)
            self.api('/api/runs/' + run['id'] + '/pause', {})
            gate.set()
            self.await_run(run['id'], {'paused_by_user'})
            self.api('/api/runs/' + run['id'] + '/stop', {})
            self.await_run(run['id'], {'interrupted'})
            self.assertFalse(self.api(self.prefix() + '/files')['files'])
        finally:
            gate.set()

    def test_monitor_events_reports_and_logs_survive_reopening(self):
        data, run = self.finish_demo()
        session_url = '/api/projects/' + run['project_id'] + '/sessions/' + run['session_id']
        saved = self.api(session_url)
        kinds = {e['kind'] for e in saved['events']}
        self.assertTrue({'model_start','model_end','tool_start','tool_end','command_output','command_end','approval_decision','finished'} <= kinds)
        self.assertGreater(run['elapsed_seconds'], 0)
        status, log, _ = self.raw(session_url + '/logs')
        self.assertEqual(status, 200)
        records = [json.loads(line) for line in log.splitlines()]
        self.assertIn('Syntax check passed', ''.join(e.get('output','') for e in records))
        self.assertEqual(records[-1]['kind'], 'finished')
        status, report, _ = self.raw(session_url + '/report')
        self.assertEqual(status, 200)
        self.assertIn(b'Status: checked', report)
        reopened = AppService(self.app.bootstrap)
        self.assertEqual(reopened.export_logs(run['project_id'], run['session_id']), log)
        reopened.close()


class LiveOutputTests(unittest.TestCase):
    def test_output_is_visible_before_process_finishes(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Workspace(Path(folder))
            seen, stop = threading.Event(), threading.Event()
            observed, result = [], {}
            def observe(kind, data):
                observed.append((kind, data))
                if kind == 'command_output' and 'FIRST' in data['output']:
                    seen.set()
            runner = CommandRunner(workspace, Config(auto_approve=True), lambda _: True, stop.is_set, observe)
            thread = threading.Thread(target=lambda: result.update(runner.run(
                python_command('-c', "import time; print('FIRST', flush=True); time.sleep(10); print('LAST')"))))
            thread.start()
            try:
                self.assertTrue(seen.wait(3), 'Output was buffered until command exit.')
                self.assertTrue(thread.is_alive())
            finally:
                stop.set()
                thread.join(5)
            self.assertTrue(result['cancelled'])
            self.assertNotIn('LAST', result['output'])

    def test_live_output_redacts_a_key_written_in_separate_chunks(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Workspace(Path(folder))
            config = Config(auto_approve=True)
            config._runtime_api_key = 'test-key-not-for-a-live-service'
            session = Session.create(workspace, 'check redaction', [], {})
            events = []
            tools = ToolSet(workspace, session, config, lambda _: True,
                            observe=lambda kind, data: events.append((kind, data)))
            command = python_command('-c', "import sys,time;sys.stdout.write('test-key-not-');sys.stdout.flush();time.sleep(.1);print('for-a-live-service')")
            self.assertTrue(tools.execute('run_command', {'command': command})['ok'])
            output = ''.join(e['output'] for kind, e in events if kind == 'command_output')
            self.assertIn('[REDACTED]', output)
            self.assertNotIn(config.api_key, json.dumps(events))
            self.assertNotIn('test-key-not-', output)


if __name__ == '__main__':
    unittest.main()
