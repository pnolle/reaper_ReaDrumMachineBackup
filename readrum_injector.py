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


def replace_in_block(block_text, replacements):
    # block_text contains outer base64 lines; we will replace inner base64 tokens
    lines = block_text.splitlines()
    blocks = []
    cur = []
    idx_map = []
    for li, line in enumerate(lines):
        if re.match(r"^\s*[A-Za-z0-9+/=]{20,}\s*$", line):
            cur.append(line.strip())
        else:
            if cur:
                blocks.append(''.join(cur))
                cur = []
    if cur:
        blocks.append(''.join(cur))

    new_block_text = block_text
    changed = False
    # operate on each outer base64 block
    for outer_b64 in blocks:
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
                    inner_text = inner_text.replace(old, new)
                    inner_changed = True
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
            # format into 76-char lines with same indentation as original lines
            # find indentation from block_text first base base64 line
            m = re.search(r"^(\s*)([A-Za-z0-9+/=]{20,})", block_text, re.M)
            indent = m.group(1) if m else '    '
            b64_lines = '\n'.join(indent + new_outer_b64[i:i+76] for i in range(0,len(new_outer_b64),76)) + '\n'
            new_block_text = new_block_text.replace(outer_b64, new_outer_b64)
    return new_block_text, changed


def main():
    if len(sys.argv) < 3:
        print('Usage: readrum_injector.py input.RPL replacements.csv')
        sys.exit(1)
    inp = Path(sys.argv[1])
    csvp = Path(sys.argv[2])
    text = inp.read_text(encoding='utf8', errors='replace')
    # read replacements CSV
    reps = []
    with csvp.open(newline='', encoding='utf8') as f:
        r = csv.DictReader(f)
        for row in r:
            # expect columns: preset,container,old_path,new_path
            reps.append({'preset':row.get('preset',''),'container':row.get('container',''),'old_path':row.get('old_path',''),'new_path':row.get('new_path','')})

    presets = find_preset_blocks(text)
    text_lines = text.splitlines(True)
    modified = False
    # iterate presets and apply matching replacements
    for pname, start_i, end_i, block in presets:
        # collect only replacements that target this preset (or all if preset blank)
        target_reps = [r for r in reps if (not r['preset']) or r['preset']==pname]
        if not target_reps:
            continue
        new_block, changed = replace_in_block(block, target_reps)
        if changed:
            modified = True
            # replace lines in text_lines between start_i+1..end_i-1 with new_block
            text_lines[start_i+1:end_i] = [new_block]

    if modified:
        bak = inp.with_suffix(inp.suffix + '.bak')
        inp.replace(bak)
        # write modified file
        inp.write_text(''.join(text_lines), encoding='utf8')
        print('Applied replacements; original backed up to', str(bak))
    else:
        print('No changes applied')


if __name__=='__main__':
    import csv
    main()
