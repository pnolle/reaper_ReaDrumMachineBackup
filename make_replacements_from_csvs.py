#!/usr/bin/env python3
"""
Create a replacements CSV by comparing two CSV exports from the parser.

Usage:
  python3 make_replacements_from_csvs.py original.csv revised.csv replacements.csv

The script matches rows by the tuple (preset,container,note). When a matching key
has different `path` values between the two CSVs, it emits a row with
`preset,container,old_path,new_path`.
"""
import sys
import csv
from pathlib import Path


def read_map(csvp):
    m = {}
    with open(csvp, newline='', encoding='utf8') as f:
        r = csv.DictReader(f)
        for row in r:
            key = (row.get('preset',''), row.get('container',''), row.get('note',''))
            m[key] = row.get('path','')
    return m


def main():
    if len(sys.argv) < 4:
        print('Usage: make_replacements_from_csvs.py original.csv revised.csv replacements.csv')
        sys.exit(1)
    orig = Path(sys.argv[1])
    rev = Path(sys.argv[2])
    outp = Path(sys.argv[3])

    orig_map = read_map(orig)
    rev_map = read_map(rev)

    rows = []
    for key, old_path in orig_map.items():
        new_path = rev_map.get(key)
        if new_path is None:
            continue
        if old_path != new_path:
            rows.append({'preset': key[0], 'container': key[1], 'old_path': old_path, 'new_path': new_path})

    if not rows:
        print('No differing paths found between the CSVs')
        outp.write_text('', encoding='utf8')
        return

    with outp.open('w', newline='', encoding='utf8') as f:
        w = csv.DictWriter(f, fieldnames=['preset','container','old_path','new_path'])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print('Wrote', len(rows), 'replacements to', str(outp))


if __name__ == '__main__':
    main()
