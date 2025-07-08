# Git Search and Replace (GSR)

A Python-based tool for search-and-replace operations across Git repositories, with support for regular expressions, structured logging, file filtering, and Azure DevOps compatibility. This version is optimized for use in pipelines and `.exe` packaging.

## 🔧 Features

- Regular expression-based search and replace
- File and filename replacements (optional)
- Filter files by include/exclude patterns (glob)
- Config-driven match types: `full`, `left`, `right`, `none`
- UTF-8 and Latin-1 decoding support
- Timestamped JSON logs for matches and replacements
- Works with Git LFS and Azure DevOps repositories
- Compatible with PyInstaller `.exe` builds

## 📁 Project Structure

| File | Description |
|------|-------------|
| `gsr_main.py` | Minimal entry point that runs the main logic |
| `gsr_module.py` | Full implementation of the search-replace engine |
| `gsr-config.json` | Search expressions (OldString, NewString, Match) |
| `gsr-filetypes-config.json` | File glob patterns to include/exclude |
| `template-gsr-config.json` | Sample template for expressions |
| `template-gsr-filetypes-config.json` | Sample file filtering template |
| `build_gsr.bat` / `build_gsr.sh` | Scripts to compile the `.exe` |

## 🚀 Usage

The tool requires two JSON config files:

- `gsr-config.json`: List of expressions with optional match modes
- `gsr-filetypes-config.json`: Include/exclude rules for file types

### Example Command

```bash
# Run on current repo with in-place fixes using default configs
python gsr_main.py --fix
```

### PyInstaller Executable

Build with:

```bash
pyinstaller --onefile --name gsr gsr_main.py
```

Then use:

```bash
./gsr.exe --fix
```

## 🔤 Match Modes

| Match | Description |
|-------|-------------|
| `full` | Matches the entire string |
| `left` | Must match start of string |
| `right` | Must match end of string |
| `none` (default) | Matches any occurrence |

## ⚙️ Sample Configs

### `gsr-config.json`

```json
[
  {
    "OldString": "/OldPath/",
    "NewString": "/NewPath/",
    "Match": "none"
  },
  {
    "OldString": "FOO",
    "NewString": "BAR",
    "Match": "left"
  }
]
```

### `gsr-filetypes-config.json`

```json
[
  { "fileType": "*.json", "option": "include" },
  { "fileType": "*.cs", "option": "include" },
  { "fileType": "*.yml", "option": "include" }
]
```

> Longest or most specific match wins if multiple patterns apply.

## 🧾 Output

Search logs and matches are saved to:

```
search-results/
├── search_matches-YYYYMMDD-HHMMSS.json  # Preview mode
└── matches-YYYYMMDD-HHMMSS.json         # After --fix
```

## 🛠 Build Instructions

### Windows

```bat
@echo off
REM Build standalone gsr.exe from gsr_main.py
pyinstaller --onefile --name gsr gsr_main.py
```

### Unix/macOS

```sh
#!/bin/bash
# Build standalone gsr executable
pyinstaller --onefile --name gsr gsr_main.py
```

## 📦 Requirements

- Python 3.6+
- Git CLI
- PyInstaller (for `.exe` builds): `pip install pyinstaller`

## 📄 License

MIT License — see `LICENSE` for details.

## 🙏 Credits

Based on [`git-search-replace`](https://github.com/da-x/git-search-replace) by [da-x](https://github.com/da-x), customized and enhanced for Azure DevOps and pipeline integration.
