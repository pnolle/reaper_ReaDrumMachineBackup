#!/usr/bin/env python3
"""
reaDrum injector: read a CSV of replacements and apply them to an .RPL file

CSV format (header): preset,container,old_path,new_path

For each row the script finds inner base64 tokens inside the matching PRESET block whose
decoded bytes contain the `old_path` string and replaces that occurrence with `new_path`.

The script writes a backup of the original RPL as `file.RPL.bak` before modifying.
"""
import sys
import re
import base64
import csv
import argparse
from pathlib import Path


def find_preset_blocks(text):
    lines = text.splitlines(True)
    presets = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"\s*<PRESET `([^`]+)`", line)
        if m:
            name = m.group(1)
            start_i = i
            i += 1
            block_lines = []
            while i < len(lines) and not re.match(r"^\s*>\s*$", lines[i]):
                block_lines.append(lines[i])
                i += 1
            end_i = i
            presets.append((name, start_i, end_i, ''.join(block_lines)))
        else:
            i += 1
    return presets


def replace_in_block(block_text, replacements, report=False):
    # block_text contains outer base64 lines; we will replace inner base64 tokens
    lines = block_text.splitlines(True)
    blocks = []
    cur = []
    cur_orig = []
    for li, line in enumerate(lines):
        if re.match(r"^\s*[A-Za-z0-9+/=]{20,}\s*$", line):
            cur.append(line.strip())
            cur_orig.append(line)
        else:
            if cur:
                blocks.append(("".join(cur), "".join(cur_orig)))
                cur = []
                cur_orig = []
    if cur:
        blocks.append(("".join(cur), "".join(cur_orig)))

    new_block_text = block_text
    changed = False
    changes_report = []
    
    # operate on each outer base64 block
    for outer_b64, outer_orig_text in blocks:
        try:
            outer_bytes = base64.b64decode(outer_b64)
        except Exception:
            continue
        outer_text = outer_bytes.decode('latin1', errors='replace')
        # find inner base64 tokens in outer_text
        for inner_token in re.findall(r"[A-Za-z0-9+/=]{20,}", outer_text):
            try:
                inner_bytes = base64.b64decode(inner_token)
            except Exception:
                continue
            inner_changed = False
            inner_text = inner_bytes.decode('latin1', errors='replace')
            for row in replacements:
                old = row['old_path']
                new = row['new_path']
                if old and old in inner_text:
                    occ = inner_text.count(old)
                    inner_text = inner_text.replace(old, new)
                    inner_changed = True
                    if report:
                        changes_report.append({'old': old, 'new': new, 'count': occ, 'inner_token': inner_token[:20]})
            if inner_changed:
                # re-encode inner_text back to bytes (latin1 to preserve byte values)
                new_inner_bytes = inner_text.encode('latin1', errors='replace')
                new_inner_b64 = base64.b64encode(new_inner_bytes).decode('ascii')
                # replace token occurrence(s) in outer_text
                outer_text = outer_text.replace(inner_token, new_inner_b64)
                # commit back to outer_bytes
                outer_bytes = outer_text.encode('latin1', errors='replace')
                changed = True
        if changed:
            # re-encode outer_bytes to base64 and replace in the block_text
            new_outer_b64 = base64.b64encode(outer_bytes).decode('ascii')
            # format into 76-char lines with same indentation as the original outer text
            m = re.search(r"^(\s*)[A-Za-z0-9+/=]{20,}", outer_orig_text)
            indent = m.group(1) if m else '    '
            b64_lines = '\n'.join(indent + new_outer_b64[i:i+76] for i in range(0,len(new_outer_b64),76)) + '\n'
            # replace the original base64 block (with its newlines/indentation) with the new formatted block
            new_block_text = new_block_text.replace(outer_orig_text, b64_lines)
    return new_block_text, changed, changes_report


def main():
    parser = argparse.ArgumentParser(description='Apply replacements to a ReaDrum .RPL file')
    parser.add_argument('rpl', help='input .RPL file')
    # New CLI: positional CSV is the revised parser CSV (streamlined workflow)
    parser.add_argument('csv', nargs='?', help='revised parser CSV (positional). If provided, injector will parse the RPL in-memory and compute deltas.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--replacements', '-r', help='replacements CSV (preset,container,old_path,new_path)')
    group.add_argument('--csv-pair', nargs=2, metavar=('ORIG_CSV','REVISED_CSV'), help='Provide original and revised parser CSVs; injector will compute deltas by (preset,container,note)')
    parser.add_argument('--dry-run', action='store_true', help="Don't write file; just report replacements")
    args = parser.parse_args()
    inp = Path(args.rpl)
    dry_run = args.dry_run
    text = inp.read_text(encoding='utf8', errors='replace')
    # build replacements list from one of three modes:
    #  - explicit replacements CSV (--replacements)
    #  - csv-pair: two parser CSVs (orig,revised)
    #  - revised-csv: single revised CSV; parse RPL in-memory to compute original
    reps = []
    def read_replacements_file(p):
        out = []
        with Path(p).open(newline='', encoding='utf8') as f:
            r = csv.DictReader(f)
            for row in r:
                out.append({'preset':row.get('preset',''),'container':row.get('container',''),'old_path':row.get('old_path',''),'new_path':row.get('new_path','')})
        return out

    def read_map(csvp):
        m = {}
        with open(csvp, newline='', encoding='utf8') as f:
            r = csv.DictReader(f)
            for row in r:
                key = (row.get('preset',''), row.get('container',''), row.get('note',''))
                m[key] = row.get('path','')
        return m

    if args.replacements:
        reps = read_replacements_file(args.replacements)
    elif args.csv_pair:
        orig_csv, rev_csv = args.csv_pair
        orig_map = read_map(orig_csv)
        rev_map = read_map(rev_csv)
        for key, old_path in orig_map.items():
            new_path = rev_map.get(key)
            if new_path is None:
                continue
            if old_path != new_path:
                reps.append({'preset': key[0], 'container': key[1], 'old_path': old_path, 'new_path': new_path})
    else:
        # parse the RPL in-memory to build the original map, compare with the provided positional revised CSV
        if not args.csv:
            parser.error('Either provide a revised CSV as the second positional argument, or use --replacements/--csv-pair')
        rev_csv = args.csv
        rev_map = read_map(rev_csv)
        # build original map by parsing the RPL file in-memory
        rpl_text = text
        # minimal parser: iterate preset blocks, decode outer base64 blobs, split on '<CONTAINER',
        # extract container header and find first path-like token inside each container.
        def extract_map_from_rpl_text(text):
            result = {}
            presets = find_preset_blocks(text)
            path_re = re.compile(r"(/(?:Volumes|Users)[^\x00\n\r\"]+?\.(?:wav|aiff?|flac|ogg|mp3|sfz|WAV|AIF))")
            inner_b64_re = re.compile(r"[A-Za-z0-9+/=]{20,}")
            for pname, start_i, end_i, block in presets:
                # collect outer base64 contiguous lines
                b64_lines = []
                for L in block.splitlines():
                    if re.match(r"^\s*[A-Za-z0-9+/=]{20,}\s*$", L):
                        b64_lines.append(L.strip())
                if not b64_lines:
                    continue
                try:
                    outer_bytes = base64.b64decode(''.join(b64_lines))
                except Exception:
                    continue
                outer_text = outer_bytes.decode('latin1', errors='replace')
                # split into container fragments
                frags = outer_text.split('CONTAINER')
                for frag in frags[1:]:
                    # attempt to get note and container name (look for pattern: Container "<note>: <name>")
                    m = re.search(r'Container\s+"([^:]+):\s*([^\"]+)"', 'CONTAINER'+frag)
                    note = ''
                    container = ''
                    if m:
                        note = m.group(1).strip()
                        container = m.group(2).strip()
                    # search inner base64 tokens inside this fragment and decode them to find path-like strings
                    found = None
                    for inner_token in inner_b64_re.findall(frag):
                        try:
                            inner_bytes = base64.b64decode(inner_token)
                        except Exception:
                            continue
                        inner_text = inner_bytes.decode('latin1', errors='replace')
                        pm = path_re.search(inner_text)
                        if pm:
                            found = pm.group(1).strip('\x00')
                            break
                    if found:
                        key = (pname, container, note)
                        if key not in result:
                            result[key] = found
            return result

        orig_map = extract_map_from_rpl_text(rpl_text)
        # if our lightweight in-memory parse yields no matches against the revised CSV,
        # fall back to running the full `readrum_parser.py` script into a temporary CSV
        # so we can compute replacements exactly as the parser would produce.
        intersect = set(orig_map.keys()) & set(rev_map.keys())
        if not intersect:
            import tempfile, subprocess
            with tempfile.NamedTemporaryFile('w+', delete=False, suffix='.csv') as tf:
                tmpname = tf.name
            # run readrum_parser.py to produce an authoritative CSV
            subprocess.check_call([sys.executable, 'readrum_parser.py', str(inp), tmpname])
            orig_map = read_map(tmpname)
        for key, old_path in orig_map.items():
            new_path = rev_map.get(key)
            if new_path is None:
                continue
            if old_path != new_path:
                reps.append({'preset': key[0], 'container': key[1], 'old_path': old_path, 'new_path': new_path})

    presets = find_preset_blocks(text)
    text_lines = text.splitlines(True)
    modified = False
    # iterate presets and apply matching replacements
    for pname, start_i, end_i, block in presets:
        # collect only replacements that target this preset (or all if preset blank)
        target_reps = [r for r in reps if (not r['preset']) or r['preset']==pname]
        if not target_reps:
            continue
        new_block, changed, changes = replace_in_block(block, target_reps, report=True)
        if changed:
            modified = True
            # replace lines in text_lines between start_i+1..end_i-1 with new_block
            text_lines[start_i+1:end_i] = [new_block]
            # report changes found for this preset
            if changes:
                print(f"Preset: {pname} — {len(changes)} change(s) found")
                for c in changes[:50]:
                    print(f"  - {c['count']}x: '{c['old']}' -> '{c['new']}'")

    if modified:
        if dry_run:
            print('\nDry-run: changes were detected but not written. Run without --dry-run to apply.')
        else:
            bak = inp.with_suffix(inp.suffix + '.bak')
            inp.replace(bak)
            # write modified file
            inp.write_text(''.join(text_lines), encoding='utf8')
            print('Applied replacements; original backed up to', str(bak))
    else:
        print('No changes applied')


if __name__=='__main__':
    main()
