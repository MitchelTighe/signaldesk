#!/usr/bin/env python3
"""Generate the Worker's public prompt/runbooks from the canonical Python sources."""
import argparse
import json
from pathlib import Path
import sys

ENTRY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENTRY))
from signaldesk.live import SYSTEM, runbooks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = 'export const resources = ' + json.dumps(
        {'system': SYSTEM, 'runbooks': runbooks()}, ensure_ascii=False, indent=2) + ';\n'
    target = ENTRY / 'worker/resources.mjs'
    if args.check:
        if target.read_text() != content:
            raise ValueError('Worker prompt/runbook drift; run scripts/live_assets.py')
        print('Worker prompt and eight runbooks match canonical Python sources')
    else:
        target.write_text(content)
        print('Generated worker/resources.mjs from public authored sources')


if __name__ == '__main__':
    main()
