# TagMeGently

A modern MP3 tagger with Discogs integration — built as a replacement for Tag&Rename, fixing its UTF-8/special character encoding bug when fetching metadata from Discogs.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

## Features

### Explorer & File List
- Folder tree on the left — click a folder to load all MP3s recursively (including subfolders)
- Files sorted by album → track number (natural sort, so track 10 comes after 9)
- Cover column shows `♪` for files with an embedded cover
- Clicking a file previews its embedded cover in the left panel

### Discogs Integration
- Search by Artist + Album (restricted to release title matches — no false positives from track titles)
- **Single click** on a result loads track count, total duration and cover status instantly
- Master releases highlighted in gold with ★
- Cover indicator column in results list
- Detail cache — no double-download when browsing results then loading an album

### TrackMatch Dialog (Tag&Rename-style workflow)
- Local filenames and Discogs tracklist shown side by side
- **▲/▼ moves files OR Discogs tracks independently** — click the file column to move files, click the Discogs column to move tracks
- `Datei nicht gefunden!` shown in red when Discogs has more tracks than local files
- Compilation auto-detection: `Title /// Artist` format splits automatically, sets Album Artist = "Various Artists"
- **Drag & drop cover** from browser directly into the cover field
- **Google Images search** button opens browser pre-filled with artist/album/year

### Tag Writing
- Correct UTF-8 encoding via mutagen (fixes the Ö/Ü/Ä and Cyrillic bug in Tag&Rename)
- Corrupt APIC frames are fully replaced, not stacked
- **Album Artist (TPE2)** always written alongside Artist — skipped if existing TPE2 contains "Various"
- Cover resized to max 600×600 px via Pillow
- `folder.jpg` written to album folder alongside tags

### Cover Quality Scanner
- Scans a folder tree recursively, checks every embedded cover via Pillow (full decode — catches truncated data Qt misses)
- Categories: 🔴 Corrupt · 🟡 Too small (<300px) · ⚪ No cover
- Double-click any result to load that album directly in the tagger

### File Renaming
- Mask-based renaming with persistent custom masks (save/delete per mask)
- **Absolute path masks supported**: `I:\Musik\%1\[%4] %3\%6-%2` moves files to a different drive/folder
- `folder.jpg` is copied to the destination folder automatically when files are moved
- Preview shows full destination path for absolute masks

### Settings
- Discogs Personal Access Token (60 req/min vs 25 anonymous)
- All checkbox states, rename masks, and last opened folder persist across sessions (`~/.tagmegently.json`)

## Installation

```bash
pip install PyQt6 mutagen requests Pillow
python tagger.py
```

Or double-click `start.bat` on Windows.

## Discogs API Token

1. Go to [discogs.com → Settings → Developers](https://www.discogs.com/settings/developers)
2. Click **Generate new token**
3. In TagMeGently: **Tools → Einstellungen** → paste the token

## Rename Mask Variables

| Variable | Value        |
|----------|-------------|
| `%1`     | Artist       |
| `%2`     | Title        |
| `%3`     | Album        |
| `%4`     | Year         |
| `%5`     | Genre        |
| `%6`     | Track number |
| `%t`     | Duration     |
| `%b`     | Bitrate      |

Use `\` to create subfolders: `%1\[%4] %3\%6 - %2`  
Use an absolute path to move files: `I:\Musik\%1\[%4] %3\%6 - %2`

## Requirements

- Python 3.10+
- PyQt6 >= 6.6
- mutagen >= 1.47
- requests >= 2.31
- Pillow >= 10.0

## Changelog

### v0.2
- TrackMatch dialog: side-by-side file ↔ Discogs track matching with independent ▲/▼
- Drag & drop cover from browser
- Compilation support (Various Artists, `/// Artist` auto-detection)
- Album Artist (TPE2) tag always written
- Discogs single-click detail preview with cover indicator
- Absolute path rename masks + folder.jpg copied on move
- Dark theme refinements

### v0.1
- Initial release: Explorer tree, Discogs search, Cover Quality Scanner, mask-based renaming

## License

MIT
