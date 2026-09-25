"""Owner setup recovery without remote credentials or production data."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import setup_cloud


class CloudSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.owner=self.root/'gateway/.owner'
        self.owner.mkdir(parents=True)
        self.migrations=self.root/'gateway/migrations'
        self.migrations.mkdir()
        source=setup_cloud.ROOT/'gateway/migrations/0001_pilot.sql'
        self.migration=self.migrations/source.name
        shutil.copyfile(source,self.migration)
        for name,value in [('ROOT',self.root),('OWNER',self.owner)]:
            replacement=patch.object(setup_cloud,name,value)
            replacement.start();self.addCleanup(replacement.stop)
        self.output=io.StringIO()
        for stream in ('stdout','stderr'):
            redirect=getattr(contextlib,'redirect_'+stream)(self.output)
            redirect.__enter__();self.addCleanup(redirect.__exit__,None,None,None)

    def remote(self,*,failure='incomplete input: SQLITE_ERROR [code: 7500]',fail_import=False):
        database=sqlite3.connect(':memory:',isolation_level=None)
        self.addCleanup(database.close)
        database.row_factory=sqlite3.Row
        database.execute('CREATE TABLE d1_migrations (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)')
        calls=[]
        def run(*args,**kwargs):
            calls.append(args)
            if args[:3]==('d1','migrations','apply'):
                if database.execute('SELECT COUNT(*) FROM d1_migrations').fetchone()[0]:return 'No migrations to apply!'
                raise subprocess.CalledProcessError(1,list(args),output='',stderr=failure)
            self.assertEqual(args[:3],('d1','execute','saved-pilot'))
            self.assertIn('--remote',args)
            if '--command' in args:
                rows=[dict(row) for row in database.execute(args[args.index('--command')+1])]
                return json.dumps([{'success':True,'results':rows}])
            self.assertIn('--file',args)
            sql=Path(args[args.index('--file')+1]).read_text()
            if fail_import:sql+='\nSELECT * FROM deliberately_missing_table;'
            try:database.executescript('BEGIN;\n'+sql+'\nCOMMIT;')
            except sqlite3.Error as error:
                database.execute('ROLLBACK')
                raise subprocess.CalledProcessError(1,list(args),stderr=str(error)) from error
            return ''
        return database,calls,run

    def test_normalize_zip_line_endings_and_validate_without_cloud_calls(self):
        original=self.migration.read_bytes()
        self.migration.write_bytes(b'\xef\xbb\xbf'+original.replace(b'\n',b'\r\n'))
        with patch.object(setup_cloud.subprocess,'run') as command:
            setup_cloud.main(check_only=True)
        command.assert_not_called()
        self.assertEqual(self.migration.read_bytes(),original)
        self.assertFalse((self.owner/'wrangler.json').exists())

    def test_invalid_sql_stops_before_login_or_cloud_changes(self):
        self.migration.write_text('CREATE TABLE broken (')
        with patch.object(setup_cloud.subprocess,'run') as command:
            with self.assertRaisesRegex(SystemExit,'No cloud changes'):
                setup_cloud.main()
        command.assert_not_called()

    def test_empty_database_import_records_schema_and_history_once(self):
        database,calls,run=self.remote()
        setup_cloud.apply_migrations(run,'saved-pilot')
        self.assertEqual(database.execute('SELECT name FROM d1_migrations').fetchone()[0],'0001_pilot.sql')
        self.assertEqual(database.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0],6)
        database.execute("INSERT INTO accounts(id,email,name,created) VALUES ('saved','a@example.test','Saved account',1)")
        setup_cloud.apply_migrations(run,'saved-pilot')
        self.assertEqual(sum('--file' in args for args in calls),1)
        self.assertEqual(database.execute('SELECT name FROM accounts').fetchone()[0],'Saved account')
        self.assertEqual(list(self.owner.glob('migration-*')),[])

    def test_populated_database_is_never_reimported_or_reset(self):
        database,calls,run=self.remote()
        database.execute('CREATE TABLE existing_data (value TEXT)')
        database.execute("INSERT INTO existing_data VALUES ('keep this')")
        with self.assertRaisesRegex(SystemExit,'not an empty initial setup'):
            setup_cloud.apply_migrations(run,'saved-pilot')
        self.assertFalse(any('--file' in args for args in calls))
        self.assertEqual(database.execute('SELECT value FROM existing_data').fetchone()[0],'keep this')

    def test_unrelated_cloud_error_does_not_trigger_import(self):
        _,calls,run=self.remote(failure='Authentication error [code: 10000]')
        with self.assertRaises(subprocess.CalledProcessError):
            setup_cloud.apply_migrations(run,'saved-pilot')
        self.assertEqual(len(calls),1)

    def test_existing_migration_history_blocks_recovery(self):
        database,calls,run=self.remote()
        database.execute("INSERT INTO d1_migrations(name) VALUES ('different_existing_migration.sql')")
        def failed_apply(*args,**kwargs):
            if args[:3]==('d1','migrations','apply'):
                raise subprocess.CalledProcessError(1,list(args),stderr='incomplete input: SQLITE_ERROR')
            return run(*args,**kwargs)
        with self.assertRaisesRegex(SystemExit,'migration history already exists'):
            setup_cloud.apply_migrations(failed_apply,'saved-pilot')
        self.assertFalse(any('--file' in args for args in calls))

    def test_cancelled_migration_never_reports_success(self):
        _,_,run=self.remote()
        def cancelled(*args,**kwargs):
            if args[:3]==('d1','migrations','apply'):return 'Cancelled'
            return run(*args,**kwargs)
        with self.assertRaisesRegex(SystemExit,'not completed'):
            setup_cloud.apply_migrations(cancelled,'saved-pilot')

    def test_import_failure_has_no_completion_record_and_stops(self):
        database,calls,run=self.remote(fail_import=True)
        with self.assertRaises(subprocess.CalledProcessError):
            setup_cloud.apply_migrations(run,'saved-pilot')
        self.assertEqual(database.execute('SELECT COUNT(*) FROM d1_migrations').fetchone()[0],0)
        self.assertEqual(database.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='accounts'").fetchone()[0],0)
        self.assertEqual(sum('--file' in args for args in calls),1)
        self.assertEqual(list(self.owner.glob('migration-*')),[])

    def saved_config(self):
        config={'name':'saved-pilot','main':'/old/location/worker.mjs',
                'assets':{'directory':'/old/location/public'},
                'd1_databases':[{'binding':'DB','database_name':'saved-pilot',
                    'database_id':'11111111-2222-3333-4444-555555555555','migrations_dir':'/old/location/migrations'}],
                'vars':{'UPI_ID':'owner@bank','PAYEE_NAME':'Owner','SUPPORT_EMAIL':'owner@example.test'}}
        setup_cloud.save(self.owner/'wrangler.json',config)
        return config

    def test_failed_resumed_setup_preserves_database_and_never_requests_secrets(self):
        config=self.saved_config()
        calls=[]
        def command(args,**kwargs):
            calls.append(args)
            if 'migrations' in args:
                raise subprocess.CalledProcessError(1,args,stderr='Connection interrupted')
            return subprocess.CompletedProcess(args,0,stdout='')
        with patch.object(setup_cloud.shutil,'which',side_effect=lambda name:name), \
             patch.object(setup_cloud.subprocess,'run',side_effect=command), \
             patch('builtins.input',return_value=''), \
             patch.object(setup_cloud.getpass,'getpass') as secret:
            with self.assertRaisesRegex(SystemExit,'Keep gateway/.owner'):
                setup_cloud.main()
        secret.assert_not_called()
        saved=json.loads((self.owner/'wrangler.json').read_text())
        self.assertEqual(saved['d1_databases'][0]['database_id'],config['d1_databases'][0]['database_id'])
        self.assertEqual(saved['d1_databases'][0]['database_name'],'saved-pilot')
        self.assertEqual(saved['d1_databases'][0]['migrations_dir'],str(self.migrations))
        self.assertEqual(saved['main'],str(self.root/'gateway/src/worker.mjs'))
        self.assertFalse(any('create' in args or 'deploy' in args or 'secret' in args for args in calls))

    def test_resumed_setup_reuses_owner_credentials_and_uploads_secrets_only_on_stdin(self):
        self.saved_config()
        credentials={'ADMIN_SECRET':'existing-admin-test-value','CACHE_SECRET':'existing-cache-test-value'}
        setup_cloud.save(self.owner/'admin-credentials.json',credentials)
        calls=[]
        def command(args,**kwargs):
            calls.append((args,kwargs))
            output='https://saved-pilot.example.workers.dev' if 'deploy' in args else ''
            if '--json' in args:output=json.dumps([{'success':True,'results':[{'name':'0001_pilot.sql'}]}])
            return subprocess.CompletedProcess(args,0,stdout=output)
        response=io.BytesIO(b'{"upi_id":"owner@bank"}')
        with patch.object(setup_cloud.shutil,'which',side_effect=lambda name:name), \
             patch.object(setup_cloud.subprocess,'run',side_effect=command), \
             patch('builtins.input',return_value=''), \
             patch.object(setup_cloud.getpass,'getpass',return_value='fake-nvidia-key'), \
             patch.object(setup_cloud.urllib.request,'urlopen',return_value=response):
            setup_cloud.main()
        self.assertEqual(json.loads((self.owner/'admin-credentials.json').read_text()),credentials)
        self.assertFalse(any('create' in args for args,_ in calls))
        secret_call=next(item for item in calls if 'secret' in item[0])
        self.assertEqual(json.loads(secret_call[1]['input']),{**credentials,'NVIDIA_API_KEY':'fake-nvidia-key'})
        self.assertNotIn('fake-nvidia-key',str([args for args,_ in calls]))
        self.assertNotIn('fake-nvidia-key',self.output.getvalue())


if __name__=='__main__':unittest.main()
