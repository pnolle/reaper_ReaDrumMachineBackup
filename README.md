# ReaDrum Machine RPL tools

This folder contains two helper scripts to inspect and patch ReaDrum Machine `.RPL` preset backups that include embedded base64 payloads referencing sample files.

### What these tools do
- `readrum_parser.py`: Extracts preset/container/note → sample file path candidates from an `.RPL` file and writes them to CSV.
- `readrum_injector.py`: Reads a CSV of replacements and updates matching sample paths inside the nested base64 tokens in an `.RPL` file (creates a backup before writing).

### Files
- `readrum_parser.py`: parser script (already present in this folder).
- `readrum_injector.py`: injector script (already present in this folder).

### CSV formats
- Parser output (example):
  - Columns: `preset,container,note,path`
  - Each row links a discovered path to its preset/container/note context.
    - Example: `python3 readrum_parser.py myReaDrumBackup.RPL myReaDrumBackup.csv`.

- Injector inputs (supported formats):
  - Use `--dry-run` flag to get a preview of what will be overwritten.
  - Positional parser CSV (recommended): `preset,container,note,path`
    - Provide the revised parser CSV as the second positional argument to `readrum_injector.py`.
    - Example: `python3 readrum_injector.py myReaDrumBackup.RPL myReaDrumBackup.csv`.
    - The injector parses the `.RPL` in-memory (or falls back to running `readrum_parser.py` internally) and computes replacements by matching `(preset,container,note)` keys.
  - Explicit replacements CSV (legacy option): `preset,container,old_path,new_path`
    - Use `--replacements replacements.csv` when you already have a mapping file.
    - `preset` may be left empty to apply the row to any preset. `old_path` should match the path substring found inside the decoded inner token; `new_path` is the replacement to encode back.

### Advanced workflows

- Provide an explicit replacements CSV (columns `preset,container,old_path,new_path`) and run:

```bash
python3 readrum_injector.py "myReaDrumBackup.RPL" --replacements replacements.csv
```

- Or provide two parser CSVs (original + revised) and let the injector compute the delta:

```bash
python3 readrum_injector.py "myReaDrumBackup.RPL" --csv-pair extracted_paths.csv extracted_paths_revised.csv
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
- Compares findings from `.RPL` with `.CSV`
- Re-encodes modified inner tokens and then re-encodes the outer base64 block back into the `.RPL`.
- Writes a backup copy of the original `.RPL` to `file.RPL.bak` before overwriting.

### Safety notes & limitations
- The scripts use `latin1` to preserve arbitrary bytes when decoding/encoding; this avoids immediate corruption but cannot guarantee success for every binary payload layout.
- If path strings in your `.RPL` contain nulls or binary padding, the parser attempts to trim them, but you should review the CSV before applying changes.

### Recommended workflow
1. Run `readrum_parser.py` to generate `extracted_paths.csv`.
2. Edit the CSV to create `replacements.csv`. Limit rows to only the replacements you want to apply.
3. Run the injector on a copy of the `.RPL` or run it (it will create a `.bak` automatically).
4. Test import in REAPER / ReaDrum Machine and confirm everything works; if not, restore from the `.bak` file.
