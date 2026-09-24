"""Desktop account connection. Provider credentials never reach the desktop."""
import json
from pathlib import Path
import secrets
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

from .workspace import write_json


def distribution():
    data = json.loads(Path(__file__).with_name('distribution.json').read_text('utf-8'))
    if data.get('mode') != 'pilot':
        return ''
    url = data.get('gateway_url', '').rstrip('/')
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.path not in ('', '/')
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('This installer has no valid server address. Ask the admin for the current installer.')
    return url


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # Never forward a device credential to a different address.


class CloudAccount:
    def __init__(self, directory, url):
        self.path = Path(directory) / 'device-account.json'
        self.url = url
        self.lock = threading.RLock()
        self.credentials = {}
        self.cached = {'enabled': bool(url), 'enrolled': False, 'ready': False}
        if url and self.path.exists():
            if self.path.is_symlink():
                raise ValueError('The account connection file must not be a symlink.')
            self.credentials = json.loads(self.path.read_text('utf-8'))
            if self.credentials.get('server') != url:
                raise ValueError('This installer uses a different server. Ask the admin to reconnect your account.')
            self.cached['enrolled'] = bool(self.credentials.get('registered'))

    @property
    def secret(self):
        return self.credentials.get('device_secret', '') if self.credentials.get('registered') else ''

    def request(self, path, payload=None):
        if not self.url:
            raise ValueError('Account access is available in the tester installer.')
        headers = {'Accept': 'application/json'}
        secret = self.credentials.get('device_secret', '') if path == '/api/enroll' else self.secret
        if secret:
            headers['Authorization'] = 'Bearer ' + secret
        raw = None
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            raw = json.dumps(payload).encode('utf-8')
        request = Request(self.url + path, data=raw, headers=headers)
        try:
            with build_opener(NoRedirect()).open(request, timeout=25) as response:
                result = json.loads(response.read(150000))
        except HTTPError as exc:
            try:
                message = json.loads(exc.read(8000)).get('error', 'Account request failed.')
            except (ValueError, AttributeError):
                message = 'Account request failed. Try again or contact the admin.'
            raise ValueError(str(message)) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise ValueError('Cannot reach the account server. Check your internet connection and retry.') from None
        if not isinstance(result, dict):
            raise ValueError('The account server returned an invalid response.')
        return result

    def status(self):
        with self.lock:
            info = self.request('/api/info')
            account = self.request('/api/me') if self.secret else {}
            self.cached = {**info, **account, 'enabled': True, 'enrolled': bool(self.secret)}
            return dict(self.cached)

    def enroll(self, payload):
        if set(payload) - {'name', 'email', 'phone', 'consent', 'recovery'}:
            raise ValueError('Invalid account details.')
        with self.lock:
            if not self.credentials:
                self.credentials = {'server': self.url, 'device_secret': secrets.token_urlsafe(48), 'registered': False}
                write_json(self.path, self.credentials)
            result = self.request('/api/enroll', payload)
            self.credentials['registered'] = True
            write_json(self.path, self.credentials)
            self.cached = {**result, 'enabled': True, 'enrolled': True}
            return self.status()

    def payment(self, payload):
        if set(payload) != {'utr'}:
            raise ValueError('Enter the UPI transaction reference.')
        with self.lock:
            self.request('/api/payments', payload)
            return self.status()

    def reconnect(self):
        with self.lock:
            if not self.url:
                raise ValueError('Account access is available in the tester installer.')
            self.credentials = {'server': self.url, 'device_secret': secrets.token_urlsafe(48), 'registered': False}
            write_json(self.path, self.credentials)
            self.cached = {'enabled': True, 'enrolled': False, 'ready': False}
            return dict(self.cached)
