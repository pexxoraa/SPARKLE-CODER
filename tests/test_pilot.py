import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from sparkle_coder.agent import Agent
from sparkle_coder.cloud import CloudAccount
from sparkle_coder.config import Config
from sparkle_coder.efficiency import compact_group
from sparkle_coder.provider import ModelError, NemotronClient
from sparkle_coder.state import Session
from sparkle_coder.webapp import AppService
from sparkle_coder.workspace import Workspace


class EfficiencyTests(unittest.TestCase):
    def test_historical_file_writes_shrink_without_losing_original_or_pairing(self):
        code = 'body { color: green; }\n' * 1448
        group = [{'role':'assistant','content':'','tool_calls':[{'id':'write-1','type':'function','function':{'name':'write_file','arguments':json.dumps({'path':'styles.css','content':code})}}]},
                 {'role':'tool','tool_call_id':'write-1','content':json.dumps({'ok':True,'path':'styles.css','diff':code})}]
        original = json.dumps(group)
        compact = compact_group(group)
        self.assertLess(len(json.dumps(compact)), len(original)*.08)
        self.assertEqual(json.dumps(group), original)
        self.assertEqual(compact[0]['tool_calls'][0]['id'], compact[1]['tool_call_id'])
        self.assertIn('Historical edit body omitted', compact[0]['tool_calls'][0]['function']['arguments'])

    def test_plain_site_verification_rechecks_edits_without_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace=Workspace(Path(temporary));config=Config()
            html='<html lang="en"><head><title>Flowers</title><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="styles.css"></head><body><a href="#contact">Contact</a><section id="contact">Flowers</section></body></html>'
            workspace.path('index.html').write_text(html);workspace.path('styles.css').write_text('body {color: green;}')
            session=Session.create(workspace,'Build a simple flower shop page',[],config.public_info())
            agent=Agent(workspace,session,config,None,lambda _:self.fail('A read-only HTML check must not run a command'),lambda _:None)
            self.assertTrue(agent.verify_completion()[0])
            self.assertEqual(session.state['checks'][-1]['source'],'builtin')
            self.assertIn('Not tested: rendered appearance', session.state['checks'][-1]['output'])
            workspace.path('styles.css').write_text('body {color: green;')
            self.assertFalse(agent.verify_completion()[0])
            workspace.path('styles.css').write_text('body {color: green;}')
            self.assertTrue(agent.verify_completion()[0])

    def test_direct_provider_does_not_repeat_an_ambiguous_post(self):
        client=NemotronClient(Config())
        with patch.object(client,'_read',side_effect=TimeoutError) as read:
            with self.assertRaisesRegex(ModelError,'not automatically repeated'):
                client.complete([],[])
            self.assertEqual(read.call_count,1)

    def test_gateway_retry_reuses_request_id_and_fast_mode_disables_reasoning(self):
        config=Config();config._runtime_cloud=True;client=NemotronClient(config);requests=[]
        def read(request):
            requests.append(request)
            if len(requests)==1:raise TimeoutError()
            return b'{"choices":[{"message":{"content":"OK"}}],"usage":{"prompt_tokens":0,"completion_tokens":3}}'
        with patch.object(client,'_read',side_effect=read),patch.object(client,'wait_retry'):
            response=client.complete([{'role':'user','content':'Hello'}],[])
        self.assertEqual(requests[0].get_header('Idempotency-key'),requests[1].get_header('Idempotency-key'))
        self.assertTrue(requests[0].get_header('Idempotency-key'))
        self.assertFalse(json.loads(requests[0].data)['chat_template_kwargs']['enable_thinking'])
        self.assertEqual(response.usage,{'prompt_tokens':0,'completion_tokens':3})


@unittest.skipUnless(shutil.which('node'),'Node 24 required for gateway integration')
class DesktopGatewayTests(unittest.TestCase):
    def test_signup_approval_model_usage_restart_and_credit_reload(self):
        root=Path(__file__).resolve().parents[1]
        server=subprocess.Popen(['node',str(root/'scripts/test_gateway_server.mjs')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(server.stderr.close);self.addCleanup(server.stdout.close)
        self.addCleanup(lambda: server.wait(timeout=5));self.addCleanup(server.terminate)
        url=server.stdout.readline().strip()
        self.assertTrue(url.startswith('http://127.0.0.1:'))
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        cookie=''
        def admin(path,payload=None):
            nonlocal cookie
            request=urllib.request.Request(url+'/api/admin/'+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Origin':url,'Cookie':cookie,'Content-Type':'application/json'})
            with opener.open(request,timeout=5) as response:
                if response.headers.get('Set-Cookie'):cookie=response.headers['Set-Cookie'].split(';')[0]
                return json.loads(response.read())
        with tempfile.TemporaryDirectory() as directory,patch('sparkle_coder.webapp.distribution',return_value=url):
            app=AppService(Path(directory));self.addCleanup(app.close)
            self.assertTrue(app.state()['account']['enabled'])
            account=app.account.enroll({'name':'Pilot Tester','email':'pilot@example.com','phone':'','consent':True})
            self.assertFalse(account['ready']);self.assertTrue(account['enrolled'])
            token=app.account.secret
            self.assertGreater(len(token),43)
            self.assertNotIn(token,json.dumps(app.state()))
            self.assertNotIn(token,app.settings_path.read_text())
            with self.assertRaisesRegex(ValueError,'managed by the admin'):
                app.configure({'base_url':'https://attacker.example/v1','api_key':'oops'})
            app.account.payment({'utr':'123456789012'})
            admin('login',{'password':'test-admin-'*8})
            pending=admin('overview')['payments'][0]
            admin('payments/'+pending['id'],{'action':'approve','verified':True})
            ready=app.account.status();self.assertEqual(ready['available_tokens'],1000000)
            client=NemotronClient(app.config())
            self.assertEqual(client.complete([{'role':'user','content':'Hi'}],[]).content,'Scripted response')
            self.assertEqual(app.account.status()['available_tokens'],999850)
            reopened=AppService(Path(directory));self.addCleanup(reopened.close)
            self.assertEqual(reopened.account.secret,token)
            self.assertTrue(reopened.account.status()['ready'])
            self.assertEqual(reopened.account.status()['available_tokens'],999850)
            if os.name!='nt':self.assertEqual(app.account.path.stat().st_mode&0o777,0o600)
            with tempfile.TemporaryDirectory() as destination:
                app.storage(destination)
                self.assertEqual(app.account.path,app.directory/'device-account.json')
