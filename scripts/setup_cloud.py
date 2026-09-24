"""Owner-only guided deployment to Cloudflare Workers + D1. No paid resources requested."""
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
OWNER=ROOT/'gateway'/'.owner'


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.is_symlink():raise SystemExit('Refusing a symlink at '+str(path))
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as file:json.dump(data,file,indent=2);file.write('\n')


def main():
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    npx=shutil.which('npx.cmd' if os.name=='nt' else 'npx')
    if not npm or not npx:raise SystemExit('Owner setup needs Node.js 22+ from https://nodejs.org. Testers do not need it.')
    print('SPARKLE owner setup: Cloudflare Workers Free + D1, 50 members maximum.')
    print('You need your own Cloudflare account, NVIDIA key, UPI ID and recipient name. Do not paste secrets in chat.')
    subprocess.run([npm,'ci'],cwd=ROOT/'gateway',check=True)
    command=[npx,'--no-install','wrangler']
    def run(*args,capture=False,input_text=None,config=True):
        result=subprocess.run([*command,*args,*(['--config',str(OWNER/'wrangler.json')] if config else [])],
          cwd=ROOT/'gateway',check=True,text=True,input=input_text,capture_output=capture,
          env={**os.environ,'WRANGLER_SEND_METRICS':'false','NO_COLOR':'1'})
        return result.stdout if capture else ''
    # Cloudflare performs account selection and secure authentication itself.
    run('login',config=False)
    config_path=OWNER/'wrangler.json'
    if config_path.exists():
        config=json.loads(config_path.read_text())
    else:
        config=json.loads((ROOT/'gateway/wrangler.jsonc').read_text())
        config['name']='sparkle-pilot-'+secrets.token_hex(3)
        config['main']=str(ROOT/'gateway/src/worker.mjs')
        config['assets']['directory']=str(ROOT/'gateway/public')
        config['d1_databases'][0].update(database_name=config['name'],migrations_dir=str(ROOT/'gateway/migrations'))
        save(config_path,config)
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
    run('d1','migrations','apply',binding['database_name'],'--remote')
    credentials_path=OWNER/'admin-credentials.json'
    if credentials_path.exists():credentials=json.loads(credentials_path.read_text())
    else:
        credentials={'ADMIN_SECRET':secrets.token_urlsafe(48),'CACHE_SECRET':secrets.token_urlsafe(48)}
        save(credentials_path,credentials)
    key=getpass.getpass('NVIDIA API key (hidden; uploaded only as a Worker secret): ').strip()
    if not key:raise SystemExit('NVIDIA key is required. It is not saved in source or the installer.')
    # Publish locked endpoints first, then upload all secrets via stdin, never command arguments.
    output=run('deploy',capture=True)
    run('secret','bulk',input_text=json.dumps({**credentials,'NVIDIA_API_KEY':key}))
    key=''
    urls=re.findall(r'https://[a-z0-9.-]+\.workers\.dev',output)
    if not urls:
        print(output);raise SystemExit('Worker deployed. Copy its HTTPS URL from Cloudflare, then run scripts/configure_pilot.py --url URL.')
    url=urls[-1]
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
    try:main()
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        print('Setup stopped safely: '+str(error),file=sys.stderr);sys.exit(1)
