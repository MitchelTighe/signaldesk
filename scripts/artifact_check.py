#!/usr/bin/env python3
"""Offline standalone artifact integrity: links, PNG CRCs, shell syntax, source allowlist."""
import hashlib
import ast
import gzip
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
from urllib.parse import unquote
import zlib

from package_public import public_files

ENTRY = Path(__file__).resolve().parents[1]


def bundle_budget(root):
    sizes = {p.name: p.stat().st_size for p in (root/'site').iterdir() if p.is_file()}
    compressed = sum(len(gzip.compress(p.read_bytes(), mtime=0))
                     for p in (root/'site').iterdir() if p.is_file())
    limits = {'index_html_bytes':300_000, 'total_bytes':600_000, 'gzip_total_bytes':100_000}
    if (sizes['index.html'] > limits['index_html_bytes'] or sum(sizes.values()) > limits['total_bytes']
            or compressed > limits['gzip_total_bytes']):
        raise ValueError('Static bundle size budget exceeded')
    return {'files_bytes':sizes, 'total_bytes':sum(sizes.values()),
            'gzip_total_bytes':compressed, 'limits':limits, 'passed':True}


class LocalLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {'href', 'src'} and value:
                self.targets.append(value)


def png_dimensions(raw):
    if raw[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Invalid PNG signature')
    offset, dimensions, ended = 8, None, False
    while offset < len(raw):
        length = struct.unpack('>I', raw[offset:offset+4])[0]
        kind = raw[offset+4:offset+8]
        payload = raw[offset+8:offset+8+length]
        checksum = struct.unpack('>I', raw[offset+8+length:offset+12+length])[0]
        if zlib.crc32(kind + payload) & 0xffffffff != checksum:
            raise ValueError('PNG chunk CRC mismatch')
        if kind == b'IHDR':
            dimensions = struct.unpack('>II', payload[:8])
        offset += length + 12
        if kind == b'IEND':
            ended = True
            break
    if not dimensions or not min(dimensions) > 0 or not ended or offset != len(raw):
        raise ValueError('Truncated PNG or invalid dimensions')
    return dimensions


def check(root=ENTRY):
    root = Path(root).resolve()
    files = public_files(root)
    links, shells, images, python_files = 0, 0, {}, 0
    for name, raw in files:
        path = root / name
        if path.suffix == '.md':
            # The package uses plain inline links; anchors and public URLs need no local file.
            for target in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)', raw.decode()):
                target = target.strip('<>')
                if target.startswith(('https:', 'http:', '#', 'mailto:')):
                    continue
                destination = (path.parent / unquote(target.split('#')[0])).resolve()
                if not destination.is_relative_to(root) or not destination.is_file():
                    raise ValueError('Broken or escaping local link in ' + name)
                links += 1
        if path.suffix == '.sh':
            result = subprocess.run(['sh', '-n', str(path)], capture_output=True, timeout=10)
            if result.returncode:
                raise ValueError('Shell syntax failed in ' + name)
            shells += 1
        if path.suffix == '.py':
            ast.parse(raw.decode(), filename=name)
            python_files += 1
        if path.suffix == '.html':
            parser = LocalLinks()
            parser.feed(raw.decode())
            for target in parser.targets:
                if target.startswith(('https:', 'http:', '#', 'data:', 'mailto:')):
                    continue
                # Templates use runtime Blob downloads, with a packaged fallback
                # at the generated site path rather than next to the template.
                if name == 'web/replay-template.html' and target == 'replay.json':
                    destination = root/'site/replay.json'
                else:
                    destination = (path.parent/unquote(target.split('#')[0])).resolve()
                if not destination.is_relative_to(root) or not destination.is_file():
                    raise ValueError('Broken HTML local link in '+name)
                links += 1
        if path.suffix == '.png':
            images[name] = list(png_dimensions(raw))
    manifest = json.loads((root/'site/manifest.json').read_text())
    for name, expected in manifest['files'].items():
        path = (root/'site'/name).resolve()
        if not path.is_relative_to(root/'site') or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Static site manifest mismatch')
    return {'public_files': len(files), 'local_links_resolved': links,
            'python_files_parsed': python_files,
            'shell_scripts_syntax_passed': shells, 'pngs_crc_checked': len(images),
            'images': images, 'static_manifest_valid': True,
            'bundle_budget': bundle_budget(root),
            'private_identifier_scan': 'passed for allowlisted paths and text; PNG metadata refused',
            'private_path_and_credential_shape_scan': 'passed for allowlisted text',
            'limits': 'Path/shape scan and CRCs do not prove absence of all secrets or personal data. '
                      'Run the pinned Gitleaks scan and manually review the public export too.'}


def main():
    try:
        result = check()
    except (ValueError, KeyError, OSError, struct.error, subprocess.SubprocessError):
        print('Artifact check refused: source hygiene, link, PNG, shell or manifest integrity failed', file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
