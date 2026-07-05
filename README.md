# Adolar Taggster

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-yellow?style=for-the-badge&logo=buy-me-a-coffee)](https://buymeacoffee.com/noyse27)

A modern MP3 tagger with Discogs integration — built as a replacement for Tag&Rename, fixing its UTF-8/special character encoding bug when fetching metadata from Discogs.

![Version](https://img.shields.io/badge/version-1.7-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

## Screenshots

### Main Window
![Main Window](docs/screenshots/main.png)

### Discogs Search — with Master releases (★) and single-click detail preview
![Discogs Search](docs/screenshots/discogs_search.png)

### TrackMatch Dialog — side-by-side file ↔ Discogs track matching
![TrackMatch](docs/screenshots/track_match.png)

### Cover Quality Scanner
![Cover Scanner](docs/screenshots/cover_scanner.png)

### File Renaming with absolute path masks
![Rename](docs/screenshots/rename.png)

---

## Features

### Explorer & File List
- Special folder shortcuts (Musik, Downloads, Desktop, Dokumente, Videos) above the tree
- Full folder tree — single click expands, double click scans MP3s
- Files sorted by album → track number (natural sort)
- Cover column (♪) indicates embedded covers; click a file to preview its cover
- Dual cover panel: **folder.jpg** left, **tag cover** right
- "folder.jpg als Tag-Cover setzen" button — appears when folder.jpg exists but tag cover is missing

### Discogs Search
- Search by Artist + Album — returns both **releases and Master releases** (★ gold)
- Single click on result loads track count, total duration and cover status instantly
- Client-side album title filter — no false positives from track title matches
- Detail cache — no double-download when browsing results

### TrackMatch Dialog
- Local filenames and Discogs tracklist shown side by side
- ▲/▼ moves **files OR Discogs tracks independently** — click the column to choose side
- `Datei nicht gefunden!` in red when Discogs has more tracks than local files
- **Compilation auto-detection** — per-track artists from Discogs API → `Title /// Artist` format → splits title/artist, sets Album Artist = "Various Artists"
- **Master releases** automatically load their main release for full label/country data
- **Drag & drop cover** from browser directly into the cover field
- **Google Images search** button opens browser pre-filled with artist/album/year

### BPM Calculation
- **♩ BPM** button calculates beats per minute via librosa beat detection
- Runs in background thread — UI stays responsive
- Loads max 60 seconds per file for speed (sufficient for accurate detection)
- Skips files that already have a BPM tag

### Configurable File Table
- Columns **Album Artist** and **BPM** shown by default
- Optional columns (hidden by default): Bitrate, Kommentar, Label, Disc#
- **Right-click any column header** to show/hide columns
- **Drag & drop** columns to reorder — layout persists across sessions

### Tag Writing
- Correct UTF-8 encoding via mutagen (fixes the Ö/Ü/Ä and Cyrillic bug in Tag&Rename)
- Corrupt APIC frames fully replaced, not stacked
- **Album Artist (TPE2)** always written alongside Artist
- Cover resized to max 600×600 px via Pillow
- `folder.jpg` written to album folder alongside tags

### Cover Quality Scanner
- Scans folder tree recursively, checks every embedded cover via full Pillow decode
- Categories: 🔴 Corrupt · 🟡 Too small (<300px) · ⚪ No cover
- Activated as soon as any folder is selected in the tree — uses selected folder as root
- Double-click any result to load that album directly in the tagger

### File Renaming
- Mask-based renaming with persistent custom masks (save/delete per mask)
- **Absolute path masks** — `I:\Musik\%1\[%4] %3\%6-%2` moves files to any drive/folder
- Before renaming: extracts cover from first MP3 tag and saves as `folder.jpg` if none exists
- `folder.jpg` copied to all destination folders when files are moved

### Background Scanning
- Folder scan runs in background thread — UI stays fully responsive
- Cancel button (✕) visible during scan
- Scan ID mechanism — stale results from cancelled scans are discarded

---

## Installation

```bash
pip install PyQt6 mutagen requests Pillow
python tagger.py
```

Or download `AdolarTaggster.exe` from [Releases](https://github.com/noyse27/adolar-taggster/releases) — no Python required.

## Discogs API Token

1. Go to [discogs.com → Settings → Developers](https://www.discogs.com/settings/developers)
2. Click **Generate new token**
3. In Adolar Taggster: **Tools → Einstellungen** → paste the token

With token: 60 requests/min · without: 25/min

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

### v1.7 (current)
- Cover Quality Scanner: save/load scan results (no rescan needed for large folders), explicit "Scannen" button instead of auto-scan on open
- New toolbar button "X→Y": table-based find/replace rules applied to generated filenames during rename, with per-row delete
- Settings dialog: Discogs token masked with reveal toggle; new "numeric track display" option normalizes Vinyl/Cassette-style positions (A1/B1) to sequential zero-padded numbers (01/14...14/14), both displayed and saved
- DropCoverLabel (TrackMatch, Tag editors): thicker red border when a loaded cover is under 300px on either side
- TrackMatch: cover dimensions now shown for covers loaded from Discogs (previously only shown for drag & drop)
- Main file table: ▲ Hoch / ▼ Runter buttons to manually reorder a selected row (useful before # Nummerierung)
- Tools menu: "Einstellungen (Discogs Token)" renamed to "Einstellungen"
- Fixed clipped icon-only buttons (rename dialog save/delete, token reveal)

### v1.6
- Discogs search: master results expand into one row per medium (Vinyl, CD, Cassette, ...) instead of a single unpredictable main release
- Discogs search: Year/Format/Land columns now all manually resizable
- Discogs search: cover pixel dimensions shown in status line (e.g. `🖼 150×150 px`) when previewing a result

### v1.5
- Cover-Scanner öffnet sich nicht-modal — Hauptfenster bleibt bedienbar, Ergebniszeilen werden nach Doppelklick abgehakt
- Tag-Editor (Einzeldatei & Batch): Cover-Drop-Feld für Drag & Drop direkt aus Browser/Explorer
- Tag-Editor: "Cover suchen" öffnet Google-Bildersuche mit Künstler/Album
- Cover wird beim Speichern zusätzlich als `folder.jpg` abgelegt
- Batch-Editor: Künstler/Album/Album Artist als Dropdown mit vorhandenen Werten der markierten Tracks statt reinem Textfeld

### v1.4
- App umbenannt zu **Adolar Taggster**

### v1.3
- Tag editor: double-click or right-click → single-file editor or batch editor with `<beibehalten>` fields
- Discogs: artist disambiguation numbers stripped, comments loaded, files sorted by track tag
- Explorer: right-click folder → add/remove favorites (⭐), delete to recycle bin
- Favorites shown in quick-access panel above tree
- Tree navigation: expands all parents and scrolls to selected folder
- Table columns: interactive resize, horizontal scrollbar
- Selection preserved after all tag operations

### v1.3 (details)
- **Tag editor** — double-click or right-click any file → edit all tags in a dedicated dialog
- **Batch tag editor** — select multiple files, right-click → fields default to `<beibehalten>` (keep), confirmation before writing
- Discogs artist names: disambiguation numbers stripped automatically (`Artist (2)` → `Artist`)
- Discogs comments/notes loaded into TrackMatch and written to COMM tag
- Files sorted by track tag (or filename) before passing to Discogs TrackMatch
- Rename dialog: preview auto-updates when mask changes
- Table columns: interactive resize (drag border), horizontal scrollbar when needed
- Selection preserved after tag write, BPM calculation, rename

### v1.2
- BPM calculation button (♩ BPM) — librosa beat detection, background thread, skips existing BPM tags
- Album Artist and BPM as new default-visible table columns
- Optional columns: Bitrate, Kommentar, Label, Disc# (right-click header to toggle)
- Drag & drop column reordering, persisted across sessions

### v1.1
- Quick rename button (⚡) — applies last saved mask instantly without dialog; tooltip shows current mask
- Auto-numbering button (#) — writes sequential track numbers to selected files with smart zero-padding
- About dialog (Über menu) with version, copyright, website and contact links

### v0.4
- Compilation auto-detection via Discogs per-track artist API field
- Master releases now load correctly (via main_release_url)
- Discogs search includes both releases and masters; client-side album filter
- Cover-Scan enabled from tree selection (no folder scan required first)
- Rename: auto-creates folder.jpg from tag cover before renaming
- Various crash fixes for network drives

### v0.3
- Explorer with special folder shortcuts (Musik, Downloads, Desktop etc.)
- Background folder scan with cancel button; scan ID for stale result prevention
- Dual cover panel (folder.jpg + tag cover); folder.jpg → tag button
- QFileSystemModel with DontWatchForChanges — no network drive crashes
- ▶/▼ text arrows via QStyledItemDelegate

### v0.2
- TrackMatch dialog (Tag&Rename-style workflow)
- Drag & drop cover from browser
- Album Artist (TPE2) tag
- Absolute path rename masks + folder.jpg copied on move

### v0.1
- Initial release: Explorer tree, Discogs search, Cover Quality Scanner, mask-based renaming

## Support

If Adolar Taggster saves you time, consider buying me a coffee ☕

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/noyse27)

## License

MIT
