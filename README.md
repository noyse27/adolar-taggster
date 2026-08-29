# Adolar Taggster

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-yellow?style=for-the-badge&logo=buy-me-a-coffee)](https://buymeacoffee.com/noyse27)

A modern MP3 tagger with Discogs integration — built as a replacement for Tag&Rename, fixing its UTF-8/special character encoding bug when fetching metadata from Discogs.

![Version](https://img.shields.io/badge/version-2.1-blue)
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
- Optional Windows Explorer context-menu entry: right-click a folder → **Mit Adolar Taggster öffnen**
- Explorer launches are forwarded to the existing Taggster window and immediately load the selected folder's MP3s
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
- **Original-Jahr (TDOR)** editable separately from Jahr (TDRC) for compilations whose release year differs from the songs' original year
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

### File → Tag
- Reverse of Rename: extracts Artist/Title/Album/Year/Genre/Track-Nr. from the file path/name using the same `%1`–`%6` mask syntax
- Preview table shows detected values per file before writing
- ⚡ quick-apply button for the last-used mask

### Undo
- Single-slot undo for the last Rename or File → Tag batch operation
- Restores previous tag values, or moves renamed files back (including cleanup of any `folder.jpg` newly copied to the destination)

### Adolar Integration
- Connect to a running [Adolar](https://github.com/noyse27) music library instance via admin API token
- Pick a library, map its path to a local folder
- Every tag/cover write or rename in Taggster automatically triggers a scoped rescan (or path-rename notice) in Adolar — debounced, so rapid edits don't spam the server
- Adolar bar above the favorites list — one click jumps to the mapped library folder
- Failed sync attempts are logged and retryable via the Sync button; last 20 successful syncs viewable in "Letzte Syncs"

---

## Installation

```bash
pip install PyQt6 mutagen requests Pillow
python tagger.py
```

Or download `AdolarTaggster.exe` from [Releases](https://github.com/noyse27/adolar-taggster/releases) — no Python required.

The optional Explorer entry can be enabled or removed under **Tools → Einstellungen → Windows Explorer**. On Windows 11 it may appear under **Weitere Optionen anzeigen**.

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

### v2.4 (current)
- Bugfix: Das Jahr-Feld (TDRC/TDOR) wird beim Speichern jetzt immer auf eine reine 4-stellige Jahreszahl gekürzt, unabhängig von der Quelle (getippt, eingefügt, aus Discogs/MusicBrainz übernommen) — z.B. "1958-05-03" wird zu "1958" statt unverändert übernommen zu werden

### v2.3
- Bugfix: Bei manchen Compilations/Dateien enthielt das ID3-Jahr-Feld (TDRC) intern zwei identische Werte; Taggster zeigte fälschlich "1958,1958" statt "1958" an, und dieser Wert wurde beim Speichern unverändert zurückgeschrieben. Mehrwertige TDRC/TDOR-Frames werden jetzt beim Laden auf den ersten Wert normalisiert.

### v2.2
- Originaljahr-Suche (MusicBrainz): Fortschrittsbalken in der Statusleiste zeigt den Suchfortschritt zusätzlich zum bisherigen Text
- Originaljahr-Suche: robustere Retries bei MusicBrainz-Verbindungsfehlern/503-Überlastung, verständlichere Fehlermeldungen statt roher Exception-Texte
- Originaljahr-Suche: Dateien mit bereits gesetztem Original-Jahr werden standardmäßig übersprungen; optionale erneute Abfrage per Checkbox, deren Wahl für die laufende Session erhalten bleibt (Standard nach Neustart: nur leere Original-Jahre prüfen)
- Discogs/MusicBrainz-Suche: bei erkannter Compilation (Album Artist "Various" oder unterschiedliche Künstler unter den markierten Tracks) wird das Suchfeld mit "Various Artists" statt dem Künstler des ersten Tracks vorbelegt

### v2.1
- Optional per-user Windows Explorer context-menu integration ("Mit Adolar Taggster öffnen"), configurable in Settings without an installer or administrator rights
- Single-instance folder forwarding: Explorer opens the selected folder in the running Taggster window and starts the MP3 scan immediately instead of opening a duplicate window
- New **Original-Jahr (TDOR)** field in the single-file and batch tag editors, plus an optional table column — distinguishes a compilation's release year from the original song's year (e.g. "Now Yearbook '91" released 2025, songs from 1991); prep work for the in-progress Adolar Songster year-guessing feature
- Discogs: master search results whose master resource itself no longer resolves (deleted/merged, but still indexed) are now dropped instead of left as a clickable-but-broken gold entry
- Quick-Umbenennen/Quick-Datei→Tag tooltips now refresh after each use instead of only reflecting the mask from app startup

### v2.0
- **File → Tag**: reverse of Rename — extracts tags from file path/name using the same mask syntax, with preview and quick-apply
- **Undo**: single-slot undo for the last Rename or File → Tag batch (restores tags, or moves files back + cleans up any newly-copied folder.jpg)
- **Adolar Integration**: connect Taggster to a running Adolar instance (admin API token), map a library to a local folder, and every write/rename automatically triggers a scoped, debounced sync — with a dedicated Adolar bar, sync log/retry, and sync history
- Discogs/Rename toolbar buttons reorganized to make room for the new File → Tag controls

### v1.7
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
