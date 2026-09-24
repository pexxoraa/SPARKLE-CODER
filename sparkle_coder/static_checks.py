"""Read-only structural checks for a small static site. Never claims browser testing."""
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
import re


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = set()
        self.ids = set()
        self.duplicates = []
        self.refs = []
        self.lang = False
        self.viewport = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.add(tag)
        if attrs.get('id'):
            if attrs['id'] in self.ids:
                self.duplicates.append(attrs['id'])
            self.ids.add(attrs['id'])
        if tag == 'html':
            self.lang = bool(attrs.get('lang'))
        if tag == 'meta' and attrs.get('name', '').lower() == 'viewport':
            self.viewport = True
        attr = 'href' if tag in ('a', 'link') else 'src' if tag in ('script', 'img', 'source') else None
        if attr and attrs.get(attr):
            self.refs.append(attrs[attr])

    handle_startendtag = handle_starttag


def inspect_site(workspace, entry='index.html'):
    text, _ = workspace.read(entry)
    page = Page()
    page.feed(text)
    errors, notes = [], []
    for tag in ('html', 'head', 'title', 'body'):
        if tag not in page.tags:
            errors.append('Missing <' + tag + '> in ' + entry)
    if not page.lang:
        errors.append('Set the page language with <html lang="…">.')
    if not page.viewport:
        errors.append('Add a viewport meta tag for mobile layouts.')
    errors += ['Duplicate element ID: ' + identity for identity in page.duplicates]
    checked = {entry}
    for reference in page.refs:
        url = urlsplit(reference)
        if url.scheme or url.netloc:
            if url.scheme in ('http', 'https'):
                notes.append('External resource not fetched: ' + reference[:140])
            continue
        if not url.path:
            if url.fragment and unquote(url.fragment) not in page.ids:
                errors.append('Link points to a missing section: ' + reference)
            continue
        base = PurePosixPath('.') if url.path.startswith('/') else PurePosixPath(entry).parent
        relative = str(base / unquote(url.path).lstrip('/'))
        try:
            target = workspace.path(relative)
            if not target.is_file():
                errors.append('Missing linked file: ' + relative)
            else:
                checked.add(relative)
        except ValueError:
            errors.append('Linked file is outside the project: ' + relative)
    metrics = []
    for name in sorted(checked):
        try:
            content, _ = workspace.read(name)
        except (ValueError, UnicodeError):
            continue  # Images are verified for existence, not parsed as text.
        metrics.append(name + ': ' + str(len(content.splitlines())) + ' lines')
        if name.endswith('.css'):
            cleaned = re.sub(r'/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '', content, flags=re.S)
            depth = 0
            for char in cleaned:
                depth += (char == '{') - (char == '}')
                if depth < 0:
                    break
            if depth != 0:
                errors.append('Unbalanced CSS braces in ' + name)
    output = '\n'.join(errors or ['HTML structure, section links and local file references passed.'])
    output += '\n' + '\n'.join(metrics)
    output += '\nNot tested: rendered appearance, JavaScript behavior, external resources or full accessibility.'
    if notes:
        output += '\n' + '\n'.join(notes[:8])
    return {'ok': not errors, 'exit_code': 0 if not errors else 1, 'output': output,
            'files_checked': sorted(checked), 'browser_tested': False}
