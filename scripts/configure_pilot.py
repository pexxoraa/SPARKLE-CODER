"""Embed only the public server origin. Never embed a provider/admin secret."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=os.environ.get('SPARKLE_PILOT_URL',''))
    parser.add_argument('--personal', action='store_true')
    args=parser.parse_args()
    data={'mode':'personal','gateway_url':''}
    if not args.personal:
        url=args.url.rstrip('/');p=urlsplit(url)
        if p.scheme!='https' or not p.hostname or p.path or p.username or p.password or p.query or p.fragment:
            parser.error('Set SPARKLE_PILOT_URL to the deployed HTTPS origin. A tester installer cannot use a placeholder.')
        data={'mode':'pilot','gateway_url':url}
    destination=Path(__file__).resolve().parents[1]/'sparkle_coder/distribution.json'
    destination.write_text(json.dumps(data)+'\n')
    print('Configured '+data['mode']+' edition'+(' for '+data['gateway_url'] if data['gateway_url'] else ''))


if __name__=='__main__':main()
