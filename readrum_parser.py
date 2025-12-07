#!/usr/bin/env python3
"""
reaDrum parser: extract sample paths from a ReaDrum Machine .RPL backup

Usage: python3 readrum_parser.py /path/to/20251207.RPL out.csv

Produces a CSV with columns: preset,container,note,path

It decodes the base64 blobs in PRESET blocks, finds nested base64 tokens
that decode to path-like strings (e.g. /Users/.../*.wav, *.aif, ...),
and writes one row per found path.
"""
import sys
import re
import base64
import csv


def find_preset_blocks(text):
    lines = text.splitlines(True)
    presets = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"\s*<PRESET `([^`]+)`", line)
        if m:
            name = m.group(1)
            # collect until a line that matches ^\s*>\s*$ (closing of PRESET chunk)
            i += 1
            block_lines = []
            while i < len(lines) and not re.match(r"^\s*>\s*$", lines[i]):
                block_lines.append(lines[i])
                i += 1
            presets.append((name, ''.join(block_lines)))
        else:
            i += 1
    return presets


def extract_paths_from_block(block_text):
    # block_text is ASCII-ish content that includes base64 lines
    # gather base64-like contiguous lines
    lines = block_text.splitlines()
    blocks = []
    cur = []
    for line in lines:
        if re.match(r"^\s*[A-Za-z0-9+/=]{20,}\s*$", line):
            cur.append(line.strip())
        else:
            if cur:
                blocks.append(''.join(cur))
                cur = []
    if cur:
        blocks.append(''.join(cur))

    results = []
    # search for path-like strings after decoding the outer base64
    path_re = re.compile(r"(/[\w\- .,/\\()\[\]':]+\.(?:wav|WAV|aif|aiff|aifc|flac|ogg|mp3|sfz|WAV|AIFF|SFZ))")

    for b64 in blocks:
        try:
            outer = base64.b64decode(b64)
        except Exception:
            continue
        # interpret outer as latin1 to preserve bytes when searching ASCII tokens
        outer_text = outer.decode('latin1', errors='replace')
        # split into containers
        chunks = outer_text.split('<CONTAINER')
        for ch in chunks:
            m = re.search(r'Container "([^"]+)"', ch)
            container = m.group(1) if m else ''
            # find base64-like inner tokens in the chunk
            for inner in re.findall(r"[A-Za-z0-9+/=]{20,}", ch):
                try:
                    inner_bytes = base64.b64decode(inner)
                except Exception:
                    continue
                try:
                    inner_text = inner_bytes.decode('latin1', errors='replace')
                except Exception:
                    inner_text = ''
                for pm in path_re.finditer(inner_text):
                    path = pm.group(1)
                    # strip trailing non printable junk
                    path = path.split('\x00')[0]
                    results.append((container, path))
    return results


def main():
    if len(sys.argv) < 3:
        print('Usage: readrum_parser.py input.RPL out.csv')
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2]
    text = open(inp,'rb').read().decode('utf8',errors='replace')
    presets = find_preset_blocks(text)
    rows = []
    for pname, block in presets:
        hits = extract_paths_from_block(block)
        for container, path in hits:
            note = container.split(':',1)[0].strip() if ':' in container else ''
            rows.append({'preset':pname,'container':container,'note':note,'path':path})
    # write CSV
    with open(out,'w',newline='',encoding='utf8') as f:
        w = csv.DictWriter(f, fieldnames=['preset','container','note','path'])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print('wrote',len(rows),'rows to',out)


if __name__=='__main__':
    main()
