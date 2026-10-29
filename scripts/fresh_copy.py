#!/usr/bin/env python3
"""Extract a clean standalone export and execute the README offline quickstart.

Uses the current Python interpreter; no git metadata, parent repository,
package installation or model service needed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--archive', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with tarfile.open(args.archive) as archive:
        members = archive.getmembers()
        for item in members:
            parts = Path(item.name).parts
            if (not item.isfile() or not parts or parts[0] != 'signaldesk' or
                    '..' in parts or Path(item.name).is_absolute()):
                raise ValueError('Non-standalone or unsafe archive member')
        # Older supported Python releases rely on the regular-file/path checks
        # above; use the standard data filter as well when it is available.
        filters = {'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}
        archive.extractall(args.output, members=members, **filters)
    source = args.output/'signaldesk'
    readme = (source/'README.md').read_text()
    section = re.search(r'^## Run locally in three commands\n(.*?)(?=^## |\Z)',
                        readme, re.M | re.S)
    block = re.search(r'^```sh\n(.*?)\n```', section.group(1), re.M | re.S) if section else None
    if not block:
        raise ValueError('README offline quickstart is missing')
    commands = block.group(1).splitlines()
    if len(commands) != 3 or any(not s.startswith('python3 ') for s in commands):
        raise ValueError('Expected the three-command README quickstart')
    results = []
    for index, cmd in enumerate(commands, 1):
        started = time.monotonic()
        # Keep the selected interpreter even when python3 is a shell launcher
        # that depends on environment deliberately omitted from these children.
        run = subprocess.run([sys.executable] + shlex.split(cmd)[1:], cwd=source,
                             capture_output=True, text=True,
                             timeout=180, env={'PATH':os.environ.get('PATH', os.defpath),
                                               'PYTHONDONTWRITEBYTECODE':'1'})
        log = f'command-{index}.txt'
        (args.output/log).write_text(run.stdout+run.stderr)
        result = {'command':cmd,'exit_code':run.returncode,'log':log,
                  'elapsed_seconds':round(time.monotonic()-started,3)}
        match = re.search(r'Ran (\d+) tests',run.stderr)
        if match:
            result['tests'] = int(match.group(1))
        results.append(result)
        print(json.dumps(result),flush=True)
        if run.returncode:
            break
    report = {'schema':'signaldesk-clean-copy-v1',
              'archive_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),
              'python':subprocess.check_output([sys.executable,'--version'],text=True).strip(),
              'commands':results,'passed':len(results)==3 and all(r['exit_code']==0 for r in results),
              'scope':'Fresh standalone archive, no parent imports or git checkout; not a public clone.'}
    (args.output/'fresh-copy-results.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
