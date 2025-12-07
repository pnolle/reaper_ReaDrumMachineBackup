# ReaDrum Machine RPL tools

This folder contains two helper scripts to inspect and patch ReaDrum Machine `.RPL` preset backups that include embedded base64 payloads referencing sample files.

### What these tools do
- `readrum_parser.py`: Extracts preset/container/note → sample file path candidates from an `.RPL` file and writes them to CSV.
- `readrum_injector.py`: Reads a CSV of replacements and updates matching sample paths inside the nested base64 tokens in an `.RPL` file (creates a backup before writing).

### Files
- `readrum_parser.py`: parser script (already present in this folder).
- `readrum_injector.py`: injector script (already present in this folder).
- `20251207.RPL`: example/working `.RPL` backup (user-provided).

### CSV formats
- Parser output (example):
  - Columns: `preset,container,note,path`
  - Each row links a discovered path to its preset/container/note context.
- Injector input (required):
  - Columns: `preset,container,old_path,new_path`
  - `preset` may be left empty to apply the row to any preset. `old_path` must match the path substring found inside the decoded inner token; `new_path` is the replacement to encode back.

### Usage examples

1) Extract paths from an `.RPL` into a CSV (parser):

```bash
python3 readrum_parser.py \
  "/Users/Shared/_Samples/ReaDrum Machine Backups/20251207.RPL" \
  extracted_paths.csv
```

2) Edit `extracted_paths.csv` or create `replacements.csv` with mappings and then run the injector:

```bash
python3 readrum_injector.py \
  "/Users/Shared/_Samples/ReaDrum Machine Backups/20251207.RPL" \
  replacements.csv
```

### File examples

RPL file looks like

```
<REAPER_PRESET_LIBRARY "ReaDrum Machine"
  <PRESET `Snippetu_CLB`
    Q09OVEFJTkVSX0NGRyAyIDIgMiAwADxJTl9QSU5TAD4APE9VVF9QSU5TAD4AU...AxAA==
  >
>
```

The CSV file looks like

```
preset,container,note,path
Snippetu_CLB,D#3: Synthwave_tom1_ComeBack,D#3,/Users/Shared/_SnipShow/CLB/CLBshort_f6/AudioFiles/samples/Synthwave_tom1_ComeBack.aif
Snippetu_CLB,C4: HH_tri_reg,C4,/Users/Shared/_SnipShow/CLB/CLBshort_f6/AudioFiles/samples/HH_tri_reg.aif
Snippetu_CLB,E4: RimClick,E4,/Users/Shared/_SnipShow/CLB/CLBshort_f6/AudioFiles/samples/RimClick.aif
...
```

### What the injector does
- Reads `replacements.csv` and finds `PRESET` blocks in the `.RPL`.
- Decodes outer base64 payloads and searches them for inner base64 tokens.
- Decodes inner tokens and performs literal substring replacement of `old_path` → `new_path`.
- Re-encodes modified inner tokens and then re-encodes the outer base64 block back into the `.RPL`.
- Writes a backup copy of the original `.RPL` to `file.RPL.bak` before overwriting.

### Safety notes & limitations
- Always keep a copy of the original `.RPL`. The injector will write a `.bak` file, but keep additional backups if the file is important.
- Matching is literal substring matching inside decoded inner tokens. Ensure your `old_path` in the CSV matches exactly (including spaces and case).
- The scripts use `latin1` to preserve arbitrary bytes when decoding/encoding; this avoids immediate corruption but cannot guarantee success for every binary payload layout.
- The injector currently replaces all occurrences within tokens that contain the `old_path`. If you need narrower matching (e.g., verify container name before replacement), ask and I can tighten the logic.
- If path strings in your `.RPL` contain nulls or binary padding, the parser attempts to trim them, but you should review the CSV before applying changes.

### Recommended workflow
1. Run `readrum_parser.py` to generate `extracted_paths.csv`.
2. Edit the CSV to create `replacements.csv`. Limit rows to only the replacements you want to apply.
3. Run the injector on a copy of the `.RPL` or run it (it will create a `.bak` automatically).
4. Test import in REAPER / ReaDrum Machine and confirm everything works; if not, restore from the `.bak` file.

### Ideas
- Add a `--dry-run` mode to `readrum_injector.py` that reports changes it would make without writing the file.
- Add stricter matching by `container` and `note` so replacements are applied only in the intended container.
- Add path normalization helpers (strip trailing junk, unify `/Volumes/Macintosh HD` → `/Users`) and optional existence checks against local filesystem.
