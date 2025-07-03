# Git Search and Replace Tool

This project provides a Python-based tool to perform regex-based search and replace operations across files in a Git repository. It supports file filtering, in-place edits, JSON logging of changes, and complex dynamic substitutions using embedded Python expressions.

## Features

- Search and replace using regular expressions
- In-place file modification (`--fix`)
- Preview changes using diff-style output (`--diff`)
- Include/exclude file types
- Rename matching filenames
- Timestamped JSON logs of matches and changes
- Compatible with Azure DevOps pipelines and LFS-aware workflows

## File Structure

- `main.py` – Entry point that runs the `main()` function from the module
- `__init__.py` – Core logic including search/replace, argument parsing, and result logging
- `gsr-config.json` – Sample configuration for expressions (OldString/NewString pairs)
- `gsr-valid-filetypes.json` – File patterns to include in the search
- `template-gsr-config.json` – Example template for expressions
- `template-gsr-valid-filetypes.json` – Template for valid file extensions

## Usage

```bash
python main.py --fix -i "*.cs" -i "*.json" "pattern1///replacement1" "pattern2///replacement2"
```

Or use pair format:

```bash
python main.py -p "pattern1" "replacement1" "pattern2" "replacement2"
```

### Flags

- `-f`, `--fix` – Modify files in place
- `-d`, `--diff` – Show before/after differences without writing to disk
- `-i`, `--include PATTERN` – Include only matching files
- `-e`, `--exclude PATTERN` – Exclude matching files
- `-s`, `--separator STRING` – Separator string for expressions (default: `///`)
- `-p`, `--pair-arguments` – Use expression pairs (FROM, TO) instead of a separator
- `--no-renames` – Skip renaming files that match replacement rules

## Output

- Search and match details are saved in `search-results/` with timestamped filenames:
  - `search_matches-YYYYMMDD-HHMMSS.json`
  - `matches-YYYYMMDD-HHMMSS.json`

## Example Configs

### `gsr-config.json`

```json
[
  {
    "OldString": "Old1",
    "NewString": "New1",
    "Match": "none"
  }
]
```

### `gsr-valid-filetypes.json`

```json
[
  { "fileType": "*.json" },
  { "fileType": "*.cs" }
]
```

## Requirements

- Python 3.6+
- Git CLI

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
