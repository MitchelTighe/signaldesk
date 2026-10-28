#!/usr/bin/env python3
"""Build the deterministic MOCK showcase, or verify its checked-in bytes."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ENTRY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENTRY))
from signaldesk.demo_data import fixture_cases, generate_report, walkthrough
from signaldesk.replay import build


def generate(root):
    root = Path(root)
    (root/'fixtures').mkdir(parents=True, exist_ok=True)
    for name, data in [('showcase.json', fixture_cases()), ('walkthrough.json', walkthrough())]:
        (root/'fixtures'/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    # The live recorded replay owns site/; the mock QA showcase lives beside it.
    return build(generate_report(), root/'site'/'showcase')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true')
    p.add_argument('--output', type=Path, default=ENTRY)
    args = p.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            generate(tmp)
            for path in sorted(Path(tmp).rglob('*')):
                if path.is_file() and path.read_bytes() != (args.output/path.relative_to(tmp)).read_bytes():
                    raise ValueError('Generated artifact drift: '+str(path.relative_to(tmp)))
        print('Deterministic showcase: all six generated files match')
    else:
        data = generate(args.output)
        print(f'MOCK showcase: {len(data["rows"])} rows; 58 fixtures; zero network/model calls')


if __name__ == '__main__':
    main()
