# TagMeGently

A modern MP3 tagger with Discogs integration — built as a replacement for Tag&Rename, fixing its UTF-8/special character encoding bug when fetching metadata from Discogs.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

## Features

- **Explorer tree** — navigate your music library folder by folder; clicking a folder loads all MP3s recursively (including subfolders), sorted by album → track naturally
- **Discogs search** — searches by artist + album title (restricted to release title matches, not track titles); Master releases highlighted in gold; loads tracklist, total duration, and cover art
- **Correct UTF-8 encoding** — tags are always written with UTF-8 (mutagen ID3 encoding=3), fixing the Ö/Ü/Ä and Cyrillic corruption bug present in Tag&Rename
- **Cover handling** — covers are resized to max 600×600 px via Pillow; corrupt/non-JPEG covers are handled gracefully; existing APIC frames are replaced cleanly; `folder.jpg` is written alongside the MP3s automatically
- **Cover preview** — embedded cover of the selected file is shown in the left panel; cover column in the file list indicates which files have an embedded cover
- **Cover Quality Scanner** — scans a folder tree recursively and lists all albums with missing, corrupt, or undersized covers; double-click jumps directly to the album
- **File renaming** — mask-based renaming (`%1`=Artist, `%2`=Title, `%3`=Album, `%4`=Year, `%6`=Track, etc.); masks are saved persistently; supports creating subfolders via `\` in the mask
- **Persistent settings** — Discogs checkbox states, rename masks, Discogs API token, and last opened folder are saved to `~/.tagmegently.json`

## Screenshots

> Coming soon

## Installation

```bash
pip install PyQt6 mutagen requests Pillow
python tagger.py
```

Or double-click `start.bat` on Windows.

## Discogs API Token

Anonymous access is rate-limited to 25 requests/minute. For comfortable use:

1. Go to [discogs.com → Settings → Developers](https://www.discogs.com/settings/developers)
2. Click **Generate new token**
3. In TagMeGently: **Tools → Einstellungen** → paste the token

With a token: 60 requests/minute, cover images load reliably.

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

## Requirements

- Python 3.10+
- PyQt6 >= 6.6
- mutagen >= 1.47
- requests >= 2.31
- Pillow >= 10.0

## License

MIT
