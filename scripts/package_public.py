#!/usr/bin/env python3
"""Export only the standalone entry, never its parent repository or runtime caches."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

ENTRY = Path(__file__).resolve().parents[1]
ROOT_FILES = {'README.md', 'FEEDBACK.md', 'HOSTING.md', 'LICENSE', 'SUBMISSION.md', '.gitignore', 'run.sh', 'pull.sh', 'demo.sh', 'runtime-image.txt', 'Containerfile.browser', 'Containerfile.judge', 'requirements-browser.txt', '.containerignore',
              '.github/workflows/pages.yml'}
SUFFIXES = {'signaldesk': {'.py', '.json'}, 'scripts': {'.py', '.sh'}, 'tests': {'.py'},
            'docs': {'.md', '.json', '.png'}, 'web': {'.html'}, 'site': {'.html', '.json'},
            'fixtures': {'.html', '.json', '.png', '.txt', '.sh', '.md'}}


# Opaque policy digests: no private names or reversibly encoded name list ships.
IDENTITY_DIGESTS = {
    '2a1f0b59dd6dd62cfe0022f3936f5eddd252e23dcf7be69256116bf07c1d6e6f',
    '8548d75fcb3a2a275a1ba868a36f6a26e528f16b07aa7d8006616ad090a9b349',
    '8db59feb4d217f26c79d6e76eea6ff80398e8b823e376bb783be870a96cab9e7',
    '96ef50b6513e10daa1a0c26e06e61cabe9a652c803ebdfc7fdbb5849b260c399',
    'b1e3c2ec1a80a8ccdbcdb04b26a5896ea2c7ef8b3774dbb004bd3b1aaa195bec',
    'e010fd1ce1acc173e3b4835b7635f8d4600d774869102adb5cb7b5d7895649ba',
    'ec5c41c127a484ebc9cc0b3ca294254623f11588ef3c71a3a148e1b19fbb79dd',
    'fb1e7ec987523d2cb9e022cec1d6ae7c99dc46edfae4fe51254025fe4bea571f',
    'fdee430d40bd57deeac186cd9790033d0f06f909a8806e7ce6e717ab7c7d5029',
}


def check_public_identity(text, name):
    for word in re.findall(r'\w+', text.casefold()):
        if hashlib.sha256(word.encode()).hexdigest() in IDENTITY_DIGESTS:
            raise ValueError('Private identifier refused in ' + name)


def public_files(root=ENTRY):
    root = Path(root)
    result = []
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if path.is_symlink():
            if rel.parts[0] in SUFFIXES or str(rel) in ROOT_FILES:
                raise ValueError('Symlink refused in public source')
            continue
        if not path.is_file() or any(part in {'__pycache__', 'cache', 'runs', 'state',
                                              'node_modules', '.git'} for part in rel.parts):
            continue
        permitted = (str(rel) in ROOT_FILES or str(rel) == 'site/_headers' or (len(rel.parts) > 1 and
                     rel.parts[0] in SUFFIXES and path.suffix in SUFFIXES[rel.parts[0]]))
        if not permitted:
            continue
        if any(part.startswith('.') and str(rel) not in {'.gitignore', '.containerignore', '.github/workflows/pages.yml'} for part in rel.parts):
            raise ValueError('Hidden file refused in public source')
        raw = path.read_bytes()
        check_public_identity(rel.as_posix(), str(rel))
        if path.suffix != '.png':
            text = raw.decode('utf-8')
            check_public_identity(text, str(rel))
            # No machine-specific paths or likely credential literals. ENV NAMES are fine.
            private_prefixes = ('/'+'home/', '/'+'mnt/', '/'+'Users/',
                                'C:'+'\\'+'Users'+'\\', '/'+'run/user/',
                                '~/'+'lab/', '~/' + '.vault', '~/'+'tmp/',
                                '~/'+'projects/', '/'+'root/')
            if any(prefix in text for prefix in private_prefixes):
                raise ValueError('Private path refused in ' + str(rel))
            private_key_header = '-----' + 'BEGIN ' + r'(?:RSA |EC |OPENSSH )?PRIVATE KEY' + '-----'
            if re.search(r'(?:sk-[A-Za-z0-9]{20,}|tvly-[A-Za-z0-9]{20,}|' + private_key_header + ')', text):
                raise ValueError('Credential-shaped literal refused in ' + str(rel))
            if re.search(r"""(?i)(?:api[_-]?key|secret|access[_-]?token)\s*["']?\s*[:=]\s*["'][A-Za-z0-9_./+-]{24,}["']""", text):
                raise ValueError('Credential-shaped assignment refused in ' + str(rel))
        else:
            # Generated screenshot pixels are manually reviewed. Text-bearing PNG
            # chunks are refused: metadata must not smuggle local paths or names.
            import struct
            offset = 8
            while offset + 12 <= len(raw):
                size = struct.unpack('>I', raw[offset:offset+4])[0]
                kind = raw[offset+4:offset+8]
                if kind in {b'tEXt', b'zTXt', b'iTXt', b'eXIf'}:
                    raise ValueError('PNG text metadata refused in ' + str(rel))
                offset += size + 12
        result.append((rel.as_posix(), raw))
    required = {'LICENSE', 'README.md', 'demo.sh', 'site/index.html',
                'scripts/signaldesk_live_eval.sh', 'signaldesk/live.py',
                'scripts/secret_scan.sh', 'scripts/scan_inside.sh',
                'signaldesk/demo.py'}
    if not required <= {r for r, _ in result}:
        raise ValueError('Required standalone files missing')
    return result


def export(output, root=ENTRY):
    files = public_files(root)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)  # Never destroy a previous export.
    manifest = {name: hashlib.sha256(raw).hexdigest() for name, raw in files}
    with (output/'signaldesk.tar.gz').open('xb') as target:
        with gzip.GzipFile(fileobj=target, mode='wb', mtime=0, filename='') as zipped:
            with tarfile.open(fileobj=zipped, mode='w') as archive:
                for name, raw in files:
                    info = tarfile.TarInfo('signaldesk/' + name)
                    info.size = len(raw); info.mtime = 0
                    info.mode = 0o755 if name.endswith('.sh') else 0o644
                    archive.addfile(info, io.BytesIO(raw))
    (output/'manifest.json').write_text(json.dumps({'license': 'MIT', 'files': manifest}, indent=2)+'\n')
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('public-export'))
    args = p.parse_args()
    try:
        manifest = export(args.output)
    except (OSError, ValueError):
        print('Export refused: output exists, required files absent, or source hygiene failed')
        return 2
    print('Exported %d allowlisted files; MIT; parent repo, caches, run logs and keys excluded' % len(manifest))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
