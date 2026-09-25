"""Owner-only guided deployment to Cloudflare Workers + D1. No paid resources requested."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
OWNER=ROOT/'gateway'/'.owner'


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.is_symlink():raise SystemExit('Refusing a symlink at '+str(path))
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as file:json.dump(data,file,indent=2);file.write('\n')


def run_wrangler(command,*args,capture=False,input_text=None,config=True,output_path=None):
    """Keep interactive commands on the terminal; expose failed captured commands."""
    environment={**os.environ,'WRANGLER_SEND_METRICS':'false','NO_COLOR':'1'}
    if output_path is not None:environment['WRANGLER_OUTPUT_FILE_PATH']=str(output_path)
    try:
        result=subprocess.run([*command,*args,*(['--config',str(OWNER/'wrangler.json')] if config else [])],
            cwd=ROOT/'gateway',check=True,text=True,input=input_text,capture_output=capture,env=environment)
    except subprocess.CalledProcessError as error:
        details='\n'.join(part for part in (error.stdout,error.stderr) if part)
        # Secret uploads use stdin. Do not repeat values if the CLI echoes input
        # in a diagnostic; the command arguments never contain these values.
        if input_text:
            details=details.replace(input_text,'[redacted]')
            try:values=json.loads(input_text)
            except ValueError:values={}
            if isinstance(values,dict):
                for value in values.values():
                    if isinstance(value,str) and value:details=details.replace(value,'[redacted]')
        if details.strip():print(details,file=sys.stderr,flush=True)
        raise
    return result.stdout if capture else ''


def deployment_url(path,worker_name):
    """Read this invocation's documented Wrangler output, not terminal text."""
    deployment=None
    for line in path.read_text(encoding='utf-8').splitlines():
        try:entry=json.loads(line)
        except ValueError:continue
        if isinstance(entry,dict) and entry.get('type')=='deploy' and entry.get('worker_name')==worker_name:
            deployment=entry
    if deployment and deployment.get('version')==1 and deployment.get('version_id'):
        targets=deployment.get('targets')
        for target in targets if isinstance(targets,list) else []:
            if isinstance(target,str) and re.fullmatch(
                    r'(?:https://)?'+re.escape(worker_name)+r'\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.workers\.dev/?',target):
                return (target if target.startswith('https://') else 'https://'+target).rstrip('/')
    raise SystemExit('Wrangler did not confirm a completed deployment with a workers.dev URL for '+worker_name+'. '
                     'Check the output above and rerun setup in the same folder. Keep gateway/.owner and the existing database. '
                     'No secrets were uploaded by this run.')


def deploy_worker(run,worker_name):
    print('Deploying Worker. Cloudflare progress, errors and setup prompts will appear below.',flush=True)
    print('If asked to register a workers.dev subdomain, choose a name for your free server address.',flush=True)
    # Piping stdout makes Wrangler non-interactive and can silently decline
    # first-account onboarding. Inherit the terminal and read its separate
    # ND-JSON output file instead. A fresh file cannot reuse a previous URL.
    with tempfile.TemporaryDirectory(prefix='deploy-',dir=OWNER) as temporary:
        output_path=Path(temporary)/'result.ndjson'
        save(output_path,{})
        try:run('deploy',output_path=output_path)
        except subprocess.CalledProcessError as error:
            raise SystemExit('Worker deployment did not complete. Read the Cloudflare error above. '
                             'Keep gateway/.owner and the existing database, then rerun setup in the same folder. '
                             'The NVIDIA key was not requested or uploaded by this run.') from error
        return deployment_url(output_path,worker_name)


def check_migrations(directory):
    """Validate locally and normalize ZIP/editor line endings before any cloud writes."""
    paths=sorted(directory.glob('*.sql'))
    if not paths:raise SystemExit('No database migrations found in '+str(directory))
    database=sqlite3.connect(':memory:')
    try:
        for path in paths:
            raw=path.read_bytes()
            sql=raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
            try:database.executescript(sql)
            except sqlite3.Error as error:
                raise SystemExit('Database setup check failed in '+path.name+': '+str(error)+'. No cloud changes were made.') from error
            normalized=sql.encode('utf-8')
            if normalized!=raw:path.write_bytes(normalized)
    finally:database.close()
    return len(paths)


def database_rows(run,name,sql):
    result=json.loads(run('d1','execute',name,'--remote','--command',sql,'--json',capture=True))
    if not isinstance(result,list) or not result or any(item.get('success') is not True for item in result):
        raise SystemExit('Could not verify the existing D1 database. No recovery import was attempted.')
    return [row for item in result for row in item.get('results',[])]


def apply_migrations(run,name):
    try:
        output=run('d1','migrations','apply',name,'--remote',capture=True)
    except subprocess.CalledProcessError as error:
        output=(error.stdout or '')+'\n'+(error.stderr or '')
        if 'incomplete input' not in output or 'SQLITE_ERROR' not in output:raise
        # The remote /query splitter can reject valid compound triggers. Use
        # Wrangler's documented file import path only for a confirmed empty DB.
        # Never reset a database, bypass history, or replay schema over accounts.
        paths=sorted((ROOT/'gateway/migrations').glob('*.sql'))
        if [path.name for path in paths]!=['0001_pilot.sql']:raise
        objects=database_rows(run,name,'SELECT type,name FROM sqlite_master')
        existing=[row for row in objects if not row['name'].startswith('sqlite_')
                  and row['name'] not in {'d1_migrations','_cf_METADATA'}]
        if existing or not any(row['name']=='d1_migrations' for row in objects):
            raise SystemExit('Recovery stopped: this database is not an empty initial setup. '
                             'Keep the database and gateway/.owner. No recovery import was attempted.')
        history=database_rows(run,name,'SELECT name FROM d1_migrations')
        if history:raise SystemExit('Recovery stopped: migration history already exists. No recovery import was attempted.')
        print('D1 rejected the SQL batch. Retrying the initial schema through file import in the same empty database.')
        # The import includes Wrangler's journal entry so schema and history
        # succeed together. An import error restores the original D1 state.
        sql=paths[0].read_text(encoding='utf-8')+"\nINSERT INTO d1_migrations (name) VALUES ('0001_pilot.sql');\n"
        with tempfile.TemporaryDirectory(prefix='migration-',dir=OWNER) as temporary:
            migration=Path(temporary)/'0001_pilot.sql'
            migration.write_text(sql,encoding='utf-8',newline='\n')
            run('d1','execute',name,'--remote','--file',str(migration),'--yes')
        history=database_rows(run,name,'SELECT name FROM d1_migrations')
        if [row['name'] for row in history]!=['0001_pilot.sql']:
            raise SystemExit('Could not confirm migration completion. Keep the existing database and rerun setup.')
        database=sqlite3.connect(':memory:')
        try:
            database.executescript(paths[0].read_text(encoding='utf-8'))
            expected={(kind,object_name) for kind,object_name in database.execute('SELECT type,name FROM sqlite_master')
                      if not object_name.startswith('sqlite_')}
        finally:database.close()
        actual={(row['type'],row['name']) for row in database_rows(run,name,'SELECT type,name FROM sqlite_master')}
        if not expected.issubset(actual):
            raise SystemExit('Database schema verification failed. No Worker deployment was attempted. Keep the existing database.')
        print('Initial database schema and migration history verified.')
    else:
        print(output)
        applied={row['name'] for row in database_rows(run,name,'SELECT name FROM d1_migrations')}
        required={path.name for path in (ROOT/'gateway/migrations').glob('*.sql')}
        if not required.issubset(applied):
            raise SystemExit('Database migrations were not completed. No Worker deployment was attempted. Rerun setup.')


def main(*,check_only=False):
    count=check_migrations(ROOT/'gateway/migrations')
    print(f'Local database schema check passed ({count} migration(s)). Remote D1 still needs verification.')
    if check_only:return
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    npx=shutil.which('npx.cmd' if os.name=='nt' else 'npx')
    if not npm or not npx:raise SystemExit('Owner setup needs Node.js 22+ from https://nodejs.org. Testers do not need it.')
    print('SPARKLE owner setup: Cloudflare Workers Free + D1, 50 members maximum.')
    print('You need your own Cloudflare account, NVIDIA key, UPI ID and recipient name. Do not paste secrets in chat.')
    subprocess.run([npm,'ci'],cwd=ROOT/'gateway',check=True)
    command=[npx,'--no-install','wrangler']
    def run(*args,**kwargs):return run_wrangler(command,*args,**kwargs)
    # Cloudflare performs account selection and secure authentication itself.
    run('login',config=False)
    config_path=OWNER/'wrangler.json'
    if config_path.exists():
        config=json.loads(config_path.read_text())
    else:
        config=json.loads((ROOT/'gateway/wrangler.jsonc').read_text())
        config['name']='sparkle-pilot-'+secrets.token_hex(3)
        config['d1_databases'][0]['database_name']=config['name']
        save(config_path,config)
    # Reuse the database identity when resuming, but read code from this checkout.
    config['main']=str(ROOT/'gateway/src/worker.mjs')
    config['assets']['directory']=str(ROOT/'gateway/public')
    config['d1_databases'][0]['migrations_dir']=str(ROOT/'gateway/migrations')
    variables=config['vars']
    for field,label in [('UPI_ID','Your UPI ID'),('PAYEE_NAME','Recipient name shown by UPI'),('SUPPORT_EMAIL','Support email')]:
        previous=variables.get(field,'')
        value=input(label+(' ['+previous+']' if previous else '')+': ').strip() or previous
        if not value:raise SystemExit(label+' is required before opening the pilot.')
        variables[field]=value
    if not re.fullmatch(r'[A-Za-z0-9._-]+@[A-Za-z0-9._-]+',variables['UPI_ID']):raise SystemExit('Enter a valid UPI ID.')
    save(config_path,config)
    binding=config['d1_databases'][0]
    if binding['database_id']=='REPLACE_AFTER_DATABASE_CREATE':
        output=run('d1','create',binding['database_name'],'--location','apac','--update-config=false',capture=True)
        match=re.search(r'(?:database_id["\s:=]+)([a-f0-9-]{36})',output)
        if not match:
            print(output);raise SystemExit('Could not read the new database ID. Add it to gateway/.owner/wrangler.json and rerun.')
        binding['database_id']=match.group(1);save(config_path,config)
    print('Applying database setup to existing database: '+binding['database_name'])
    try:apply_migrations(run,binding['database_name'])
    except subprocess.CalledProcessError as error:
        raise SystemExit('Database setup did not finish. Keep gateway/.owner and the existing D1 database. '
                         'Update the program files, then rerun python scripts/setup_cloud.py in this folder. '
                         'If it fails again, share the error above, not credentials. No Worker deployment was attempted.') from error
    # Publish locked endpoints before requesting any NVIDIA credential. Deploy
    # needs the owner's terminal for account onboarding and confirmations.
    url=deploy_worker(run,config['name'])
    credentials_path=OWNER/'admin-credentials.json'
    if credentials_path.exists():credentials=json.loads(credentials_path.read_text())
    else:
        credentials={'ADMIN_SECRET':secrets.token_urlsafe(48),'CACHE_SECRET':secrets.token_urlsafe(48)}
        save(credentials_path,credentials)
    key=getpass.getpass('NVIDIA API key (hidden; uploaded only as a Worker secret): ').strip()
    if not key:raise SystemExit('NVIDIA key is required. It is not saved in source or the installer.')
    try:run('secret','bulk',capture=True,input_text=json.dumps({**credentials,'NVIDIA_API_KEY':key}))
    finally:key=''
    print('Worker secrets uploaded. Checking the deployed server.',flush=True)
    with urllib.request.urlopen(url+'/api/info',timeout=30) as response:info=json.loads(response.read())
    if info.get('upi_id')!=variables['UPI_ID']:raise SystemExit('Payment details did not match the deployment. Do not distribute yet.')
    subprocess.run([sys.executable,str(ROOT/'scripts/configure_pilot.py'),'--url',url],check=True)
    save(OWNER/'deployment.json',{'gateway_url':url,'admin_url':url+'/admin'})
    print('\nServer: '+url+'\nAdmin: '+url+'/admin')
    print('Admin password is stored privately in '+str(credentials_path)+' (ADMIN_SECRET). Keep a secure backup.')
    print('In GitHub repository Settings > Secrets and variables > Actions > Variables, set SPARKLE_PILOT_URL to '+url)
    print('Run Actions > Build installers with the tester-edition option selected. Share only the pilot-edition Windows Setup executable.')
    print('First approve one real ₹15 payment, verify 1,000,000 credits, and benchmark one flower-shop page before inviting the group.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Validate migration files locally without login, secrets or cloud changes.')
    args=parser.parse_args()
    try:main(check_only=args.check)
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        print('Setup stopped safely: '+str(error),file=sys.stderr);sys.exit(1)
