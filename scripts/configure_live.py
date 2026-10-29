#!/usr/bin/env python3
"""Opt a static bundle into one reviewed proxy origin; empty endpoint disables live."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ENTRY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENTRY))
from signaldesk.safeio import pack


def endpoint_origin(endpoint):
    if not endpoint:
        return None
    url = urlsplit(endpoint)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.port not in (None, 443) or url.path != '/api/live' or url.query or url.fragment
            or not re.fullmatch(r'[a-z0-9.-]+', url.hostname)
            or endpoint != f'https://{url.hostname}/api/live'):
        raise ValueError('Endpoint must be exactly https://<proxy-host>/api/live')
    return f'https://{url.hostname}'


def configure(site, endpoint=''):
    site = Path(site)
    origin = endpoint_origin(endpoint)
    data = json.loads((site / 'replay.json').read_text())
    template = (ENTRY / 'web/replay-template.html').read_text()
    html = template.replace('__REPLAY_DATA__', pack(data).decode().replace('<', '\\u003c'))
    html = html.replace('name="signaldesk-live-endpoint" content=""',
                        f'name="signaldesk-live-endpoint" content="{endpoint}"')
    connect = origin or "'none'"
    html = html.replace("connect-src 'none'", f'connect-src {connect}')
    headers = (site / '_headers').read_text()
    headers = re.sub(r'connect-src [^;]+;', f'connect-src {connect};', headers)
    (site / 'index.html').write_text(html)
    (site / '_headers').write_text(headers)
    manifest_path = site / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['files'] = {name: hashlib.sha256((site / name).read_bytes()).hexdigest()
                         for name in manifest['files']}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    print(f'{site}: live endpoint ' + (endpoint or 'disabled; recorded replay remains default'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=ENTRY / 'site')
    parser.add_argument('--endpoint', default='')
    args = parser.parse_args()
    configure(args.site, args.endpoint)


if __name__ == '__main__':
    main()
