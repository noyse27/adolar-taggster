"""
TagMeGently - MP3 Tagger
Modern MP3 tagging tool with Discogs integration
"""
import sys
import os
import re
import json
import requests
from pathlib import Path
from io import BytesIO

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QTreeView,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QDialog, QDialogButtonBox,
    QCheckBox, QComboBox, QHeaderView, QToolBar,
    QStatusBar, QFrame, QScrollArea, QMessageBox, QProgressBar,
    QGroupBox, QGridLayout, QSizePolicy, QAbstractItemView,
    QMenu, QTextEdit, QStyledItemDelegate
)
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QDir, QSortFilterProxyModel,
    QModelIndex, QTimer, QStandardPaths
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QImage, QAction, QFont, QColor, QPalette
)
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QTreeView

from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, ID3NoHeaderError, TIT2, TPE1, TPE2, TALB, TDRC, TCON, TRCK,
    APIC, TPOS, TPUB, COMM
)
from mutagen.id3._util import ID3NoHeaderError
from PIL import Image

DARK_STYLE = """
/* ── Base ── */
QMainWindow, QDialog, QWidget {
    background-color: #11111b;
    color: #cdd6f4;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}

/* ── Splitter ── */
QSplitter::handle {
    background-color: #1e1e2e;
    width: 3px;
}
QSplitter::handle:hover {
    background-color: #89b4fa;
}

/* ── Tree & Tables ── */
QTreeView, QTableWidget, QListWidget {
    background-color: #181825;
    border: none;
    border-radius: 0px;
    color: #cdd6f4;
    gridline-color: #1e1e2e;
    selection-background-color: transparent;
    outline: none;
    alternate-background-color: #1a1a2e;
}
QTableWidget { alternate-background-color: #1c1c2e; }
QTreeView::item, QTableWidget::item {
    padding: 3px 6px;
    border: none;
}
QTreeView::item:hover, QTableWidget::item:hover {
    background-color: #2a2a3e;
}
QTreeView::item:selected {
    background-color: #313244;
    color: #89b4fa;
    border-left: 2px solid #89b4fa;
}
QTableWidget::item:selected {
    background-color: #2d3149;
    color: #cdd6f4;
}
QTreeView::branch {
    background-color: #181825;
}

/* ── Header ── */
QHeaderView::section {
    background-color: #11111b;
    color: #6c7086;
    border: none;
    border-bottom: 2px solid #313244;
    padding: 5px 8px;
    font-size: 11px;
    font-weight: 700;

}
QHeaderView::section:hover {
    color: #a6adc8;
    background-color: #1e1e2e;
}

/* ── Buttons ── */
QPushButton {
    background-color: #89b4fa;
    color: #11111b;
    border: none;
    border-radius: 5px;
    padding: 5px 14px;
    font-weight: 700;
    font-size: 12px;
    min-height: 26px;

}
QPushButton:hover {
    background-color: #a8c7ff;
}
QPushButton:pressed {
    background-color: #6d9ee8;
    padding-top: 6px;
    padding-bottom: 4px;
}
QPushButton:disabled {
    background-color: #1e1e2e;
    color: #45475a;
    border: 1px solid #313244;
}
QPushButton#secondary {
    background-color: transparent;
    color: #a6adc8;
    border: 1px solid #313244;
}
QPushButton#secondary:hover {
    background-color: #1e1e2e;
    border-color: #585b70;
    color: #cdd6f4;
}
QPushButton#secondary:pressed {
    background-color: #313244;
}
QPushButton#danger {
    background-color: transparent;
    color: #f38ba8;
    border: 1px solid #f38ba8;
}
QPushButton#danger:hover {
    background-color: #4a2a2e;
}

/* ── Inputs ── */
QLineEdit, QComboBox, QTextEdit {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 5px;
    color: #cdd6f4;
    padding: 4px 8px;
    min-height: 26px;
    selection-background-color: #45475a;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border-color: #89b4fa;
    background-color: #24273a;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #6c7086;
    margin-right: 6px;
}
QComboBox:focus::down-arrow { border-top-color: #89b4fa; }
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    selection-background-color: #313244;
    color: #cdd6f4;
    padding: 2px;
}

/* ── Checkboxes ── */
QCheckBox { color: #cdd6f4; spacing: 7px; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border-radius: 3px;
    border: 1px solid #45475a;
    background-color: #1e1e2e;
}
QCheckBox::indicator:hover { border-color: #89b4fa; }
QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

/* ── GroupBox ── */
QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 10px;
    color: #6c7086;
    font-size: 11px;
    font-weight: 700;

}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    background-color: #11111b;
}

/* ── Status bar ── */
QStatusBar {
    background-color: #11111b;
    color: #6c7086;
    font-size: 11px;
    border-top: 1px solid #1e1e2e;
    padding: 0 6px;
}
QStatusBar::item { border: none; }

/* ── Menu bar ── */
QMenuBar {
    background-color: #11111b;
    color: #6c7086;
    font-size: 12px;
    padding: 2px 4px;
    border-bottom: 1px solid #1e1e2e;
}
QMenuBar::item:selected { background-color: #1e1e2e; color: #cdd6f4; border-radius: 4px; }
QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item { padding: 5px 20px 5px 10px; border-radius: 4px; }
QMenu::item:selected { background-color: #313244; }

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #313244;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background-color: #585b70; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: transparent;
    height: 6px;
}
QScrollBar::handle:horizontal {
    background-color: #313244;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover { background-color: #585b70; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Progress bar ── */
QProgressBar {
    background-color: #1e1e2e;
    border: none;
    border-radius: 3px;
    height: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #89b4fa, stop:1 #cba6f7);
    border-radius: 3px;
}

/* ── Labels ── */
QLabel#heading {
    color: #cdd6f4;
    font-weight: 700;
    font-size: 11px;

}
QLabel#cover {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 6px;
    color: #45475a;
}

/* ── Dialogs ── */
QDialogButtonBox QPushButton { min-width: 80px; }
"""


def load_mp3_tags(path):
    """Load tags from an MP3 file, returns dict."""
    tags = {
        'title': '', 'artist': '', 'album': '', 'year': '',
        'genre': '', 'tracknumber': '', 'duration': 0, 'bitrate': 0,
        'cover': None
    }
    try:
        audio = MP3(path)
        tags['duration'] = int(audio.info.length)
        tags['bitrate'] = int(audio.info.bitrate / 1000)
        try:
            id3 = ID3(path)
            tags['title'] = str(id3.get('TIT2', ''))
            tags['artist'] = str(id3.get('TPE1', ''))
            tags['album'] = str(id3.get('TALB', ''))
            tags['year'] = str(id3.get('TDRC', ''))
            tags['genre'] = str(id3.get('TCON', ''))
            tags['tracknumber'] = str(id3.get('TRCK', ''))
            for key in id3.keys():
                if key.startswith('APIC'):
                    tags['cover'] = id3[key].data
                    break
        except ID3NoHeaderError:
            pass
    except Exception:
        pass
    return tags


def write_mp3_tags(path, tag_data, cover_data=None):
    """Write tags to MP3 file using mutagen (proper UTF-8)."""
    try:
        try:
            id3 = ID3(path)
        except Exception:
            id3 = ID3()

        if tag_data.get('title'):
            id3['TIT2'] = TIT2(encoding=3, text=tag_data['title'])
        if tag_data.get('artist'):
            id3['TPE1'] = TPE1(encoding=3, text=tag_data['artist'])
        if tag_data.get('album'):
            id3['TALB'] = TALB(encoding=3, text=tag_data['album'])
        if tag_data.get('year'):
            id3['TDRC'] = TDRC(encoding=3, text=str(tag_data['year']))
        if tag_data.get('genre'):
            id3['TCON'] = TCON(encoding=3, text=tag_data['genre'])
        if tag_data.get('tracknumber'):
            id3['TRCK'] = TRCK(encoding=3, text=str(tag_data['tracknumber']))

        if tag_data.get('album_artist'):
            id3['TPE2'] = TPE2(encoding=3, text=tag_data['album_artist'])
        elif tag_data.get('artist'):
            # Write artist as album artist unless existing TPE2 contains "various"
            existing_tpe2 = str(id3.get('TPE2', ''))
            if 'various' not in existing_tpe2.lower():
                id3['TPE2'] = TPE2(encoding=3, text=tag_data['artist'])

        if cover_data:
            # Remove ALL existing APIC frames first (corrupt or otherwise)
            for key in list(id3.keys()):
                if key.startswith('APIC'):
                    del id3[key]
            id3['APIC:Cover'] = APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=cover_data
            )

        id3.save(path, v2_version=3)
        return True
    except Exception as e:
        print(f"Error writing tags to {path}: {e}")
        return False


def natural_sort_key(path):
    """Sort key that sorts '10-foo.mp3' after '9-foo.mp3'."""
    parts = re.split(r'(\d+)', path.name.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def format_duration(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def image_data_to_pixmap(data, size):
    """Convert raw image bytes (any format) to QPixmap via Pillow."""
    try:
        img = Image.open(BytesIO(data))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=90)
        qimg = QImage.fromData(buf.getvalue())
        if qimg.isNull():
            return None
        return QPixmap.fromImage(qimg).scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
    except Exception:
        return None


def resize_cover(image_data, max_size=600):
    """Resize cover image to max_size x max_size, returns JPEG bytes."""
    img = Image.open(BytesIO(image_data))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=90)
    return buf.getvalue()


class DiscogsSearchThread(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, artist, album, year, token=None):
        super().__init__()
        self.artist = artist
        self.album = album
        self.year = year
        self.token = token

    def run(self):
        try:
            headers = {'User-Agent': 'TagMeGently/1.0'}
            if self.token:
                headers['Authorization'] = f'Discogs token={self.token}'

            # When album is given use release_title= to restrict to album-title
            # matches only (not track titles). Artist goes into q= so special
            # chars like "Distain!" are handled correctly by the full-text index.
            # Use q= so both releases AND masters are returned,
            # then filter client-side by album title words
            parts = []
            if self.artist:
                parts.append(self.artist)
            if self.album:
                parts.append(self.album)
            params = {'per_page': 50, 'q': ' '.join(parts) if parts else '*'}
            if self.year:
                params['year'] = self.year

            r = requests.get(
                'https://api.discogs.com/database/search',
                headers=headers, params=params, timeout=15
            )
            r.raise_for_status()
            data = r.json()
            results = []
            for item in data.get('results', []):
                results.append({
                    'id': item.get('id'),
                    'title': item.get('title', ''),
                    'year': item.get('year', ''),
                    'label': ', '.join(item.get('label', [])),
                    'country': item.get('country', ''),
                    'format': ', '.join(item.get('format', [])),
                    'cover_url': item.get('cover_image', ''),
                    'thumb_url': item.get('thumb', ''),
                    'tracklist': [],
                    'genre': ', '.join(item.get('genre', [])),
                    'style': ', '.join(item.get('style', [])),
                    'catno': item.get('catno', ''),
                    'resource_url': item.get('resource_url', ''),
                    'is_master': item.get('type', '') == 'master',
                })
            # Client-side filter: all album search words must appear in the result title
            if self.album:
                words = self.album.lower().split()
                results = [r for r in results
                           if all(w in r['title'].lower() for w in words)]
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class DiscogsDetailThread(QThread):
    detail_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, resource_url, cover_url, token=None):
        super().__init__()
        self.resource_url = resource_url
        self.cover_url = cover_url
        self.token = token

    def run(self):
        try:
            headers = {'User-Agent': 'TagMeGently/1.0'}
            if self.token:
                headers['Authorization'] = f'Discogs token={self.token}'

            r = requests.get(self.resource_url, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()

            # If this is a master release, load the main release instead
            # to get full label/country info
            if 'main_release_url' in data:
                try:
                    r2 = requests.get(data['main_release_url'], headers=headers, timeout=15)
                    if r2.status_code == 200:
                        release_data = r2.json()
                        # Keep master's tracklist if release has none
                        if release_data.get('tracklist'):
                            data = release_data
                        else:
                            # Merge: keep master tracklist, take labels/country from release
                            data['labels'] = release_data.get('labels', [])
                            data['country'] = release_data.get('country', '')
                except Exception:
                    pass

            tracklist = []
            for t in data.get('tracklist', []):
                if t.get('type_', 'track') == 'track':
                    title = t.get('title', '')
                    # Per-track artists (compilation) → "Title /// Artist"
                    track_artists = t.get('artists', [])
                    if track_artists:
                        artist_str = ' & '.join(
                            a['name'].rstrip(' *') for a in track_artists
                        )
                        title = f"{title} /// {artist_str}"
                    tracklist.append({
                        'position': t.get('position', ''),
                        'title': title,
                        'duration': t.get('duration', ''),
                    })

            artists = data.get('artists', [])
            artist_name = ' & '.join(
                a['name'].rstrip(' *') for a in artists
            ) if artists else ''

            cover_data = None
            if self.cover_url:
                try:
                    cr = requests.get(self.cover_url, headers=headers, timeout=15)
                    if cr.status_code == 200:
                        cover_data = cr.content
                except Exception:
                    pass

            detail = {
                'artist': artist_name,
                'album': data.get('title', ''),
                'year': str(data.get('year', '')),
                'genre': ', '.join(data.get('genres', [])),
                'style': ', '.join(data.get('styles', [])),
                'label': ', '.join(l['name'] for l in data.get('labels', [])),
                'catno': ', '.join(l.get('catno', '') for l in data.get('labels', [])),
                'tracklist': tracklist,
                'cover_data': cover_data,
                'cover_url': self.cover_url,
                'country': data.get('country', ''),
                'notes': data.get('notes', ''),
            }
            self.detail_ready.emit(detail)
        except Exception as e:
            self.error.emit(str(e))


class DropCoverLabel(QLabel):
    """Cover-Vorschau mit Drag & Drop Support für Bilder aus Browser oder Explorer."""
    cover_changed = pyqtSignal(bytes)

    _BASE_STYLE = ("background-color:#1e1e2e; border:2px dashed {border};"
                   "border-radius:8px; color:{color}; font-size:11px;")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Kein Cover\n(Bild hierher ziehen)")
        self._cover_data = None
        self._set_idle()

    def _set_idle(self):
        self.setStyleSheet(self._BASE_STYLE.format(border='#45475a', color='#585b70'))

    def _set_hover(self):
        self.setStyleSheet(self._BASE_STYLE.format(border='#89b4fa', color='#89b4fa'))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()
            self._set_hover()

    def dragLeaveEvent(self, event):
        self._set_idle()

    def dropEvent(self, event):
        self._set_idle()
        data = None
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            try:
                if url.isLocalFile():
                    data = Path(url.toLocalFile()).read_bytes()
                else:
                    r = requests.get(url.toString(), timeout=15,
                                     headers={'User-Agent': 'TagMeGently/1.0'})
                    data = r.content
            except Exception as e:
                print(f"Cover drop error: {e}")
        elif event.mimeData().hasImage():
            qimg = QImage(event.mimeData().imageData())
            if not qimg.isNull():
                qimg = qimg.convertToFormat(QImage.Format.Format_RGB888)
                w, h = qimg.width(), qimg.height()
                ptr = qimg.bits()
                ptr.setsize(w * h * 3)
                pil_img = Image.frombuffer('RGB', (w, h), bytes(ptr))
                buf = BytesIO()
                pil_img.save(buf, format='JPEG', quality=90)
                data = buf.getvalue()
        if data:
            self.set_cover(data)
            self.cover_changed.emit(data)

    def set_cover(self, data):
        self._cover_data = data
        size = self.width() or 160
        pix = image_data_to_pixmap(data, size - 4)
        if pix:
            self.setPixmap(pix)
            self.setText("")
        else:
            self.setText("Cover Fehler")
        self._set_idle()

    def get_cover_data(self):
        return self._cover_data


class TrackMatchDialog(QDialog):
    """Zeigt lokale Dateien neben Discogs-Trackliste zum manuellen Abgleich."""
    tags_accepted = pyqtSignal(list)   # [(path, tag_dict, cover_bytes), ...]

    def __init__(self, files, detail, cfg_save=None, cfg_load=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Album Informationen")
        self.setMinimumSize(980, 700)
        self._detail = detail
        self._tracklist = detail.get('tracklist', [])
        self._cfg_save = cfg_save
        self._cfg_load = cfg_load

        # File paths (reorderable); pad with None if Discogs has more tracks
        paths = [f[0] for f in files]
        while len(paths) < len(self._tracklist):
            paths.append(None)
        self._file_paths = paths

        self._build_ui()
        self._fill_table()
        self._fill_meta(detail)
        if detail.get('cover_data'):
            self.cover_label.set_cover(detail['cover_data'])
        self._check_compilation()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── Toolbar ──
        tb = QHBoxLayout()
        for label, slot in [("☑ Alle", self._select_all), ("☐ Keine", self._select_none),
                             ("▲ Hoch", self._move_up), ("▼ Runter", self._move_down)]:
            b = QPushButton(label)
            b.setObjectName("secondary")
            b.setFixedHeight(26)
            b.clicked.connect(slot)
            tb.addWidget(b)
        tb.addStretch()
        cover_btn = QPushButton("🔍 Suche Cover Bild")
        cover_btn.setFixedHeight(26)
        cover_btn.clicked.connect(self._search_cover)
        tb.addWidget(cover_btn)
        layout.addLayout(tb)

        # ── Track matching table ──
        self.match_table = QTableWidget(0, 4)
        self.match_table.setHorizontalHeaderLabels(["", "Dateiname", "Titel (Discogs)", "Track"])
        hh = self.match_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.match_table.setColumnWidth(0, 28)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.match_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.match_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.match_table.setAlternatingRowColors(True)
        self.match_table.setShowGrid(False)
        self.match_table.verticalHeader().setVisible(False)
        self.match_table.verticalHeader().setDefaultSectionSize(22)
        self.match_table.cellClicked.connect(self._on_cell_clicked)
        self._move_files = True  # True=move files, False=move discogs tracks
        layout.addWidget(self.match_table, stretch=1)

        # ── Meta + Cover ──
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        # Meta fields
        meta = QWidget()
        mg = QGridLayout(meta)
        mg.setSpacing(6)
        mg.setContentsMargins(0, 0, 0, 0)

        saved = self._cfg_load() if self._cfg_load else {}
        cb_s = saved.get('trackmatch_checkboxes', {})

        self.cb_title = QCheckBox("Song Titel")
        self.cb_title.setChecked(cb_s.get('title', True))
        self.cb_tracknr = QCheckBox("Track Nummern")
        self.cb_tracknr.setChecked(cb_s.get('tracknr', True))
        self.cb_compilation = QCheckBox("Compilation (Various Artists)")
        self.cb_compilation.setChecked(False)
        mg.addWidget(self.cb_title, 0, 0)
        mg.addWidget(self.cb_tracknr, 0, 1)
        mg.addWidget(self.cb_compilation, 0, 2, 1, 2)

        rows = [
            ('cb_artist', 'artist_inp', 'Künstler', True),
            ('cb_album',  'album_inp',  'Album',    True),
            ('cb_year',   'year_inp',   'Jahr',     True),
            ('cb_genre',  'genre_inp',  'Genre',    True),
            ('cb_label',  'label_inp',  'Label',    False),
        ]
        for r, (cb_attr, inp_attr, lbl, default) in enumerate(rows, 1):
            cb = QCheckBox(lbl + ':')
            cb.setChecked(cb_s.get(cb_attr, default))
            setattr(self, cb_attr, cb)
            inp = QLineEdit()
            setattr(self, inp_attr, inp)
            mg.addWidget(cb, r, 0)
            mg.addWidget(inp, r, 1, 1, 3)

        bottom.addWidget(meta, stretch=3)

        # Cover
        cv = QVBoxLayout()
        self.cover_label = DropCoverLabel()
        self.cover_label.setFixedSize(160, 160)
        self.cover_label.cover_changed.connect(self._on_cover_changed)
        cv.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.cover_info = QLabel("")
        self.cover_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_info.setStyleSheet("color:#6c7086; font-size:10px;")
        cv.addWidget(self.cover_info)
        self.cb_cover = QCheckBox("Cover speichern")
        self.cb_cover.setChecked(cb_s.get('cover', True))
        cv.addWidget(self.cb_cover, alignment=Qt.AlignmentFlag.AlignHCenter)
        cv.addStretch()
        bottom.addLayout(cv, stretch=1)
        layout.addLayout(bottom)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Abbrechen")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        write = QPushButton("Schreibe ID-Tags")
        write.clicked.connect(self._write_tags)
        btn_row.addWidget(cancel)
        btn_row.addWidget(write)
        layout.addLayout(btn_row)

    def _fill_table(self):
        n = max(len(self._file_paths), len(self._tracklist))
        self.match_table.setRowCount(n)
        total = len(self._tracklist)
        for i in range(n):
            path = self._file_paths[i] if i < len(self._file_paths) else None
            track = self._tracklist[i] if i < len(self._tracklist) else {}

            cb_item = QTableWidgetItem()
            if path:
                cb_item.setCheckState(Qt.CheckState.Checked)
            else:
                cb_item.setCheckState(Qt.CheckState.Unchecked)
                cb_item.setFlags(cb_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.match_table.setItem(i, 0, cb_item)

            if path:
                fn = QTableWidgetItem(Path(path).name)
            else:
                fn = QTableWidgetItem("Datei nicht gefunden!")
                fn.setForeground(QColor('#f38ba8'))
            self.match_table.setItem(i, 1, fn)

            self.match_table.setItem(i, 2, QTableWidgetItem(track.get('title', '')))
            pos = track.get('position', '')
            self.match_table.setItem(i, 3, QTableWidgetItem(f"{pos}/{total}" if pos else ''))

    def _fill_meta(self, detail):
        self.artist_inp.setText(detail.get('artist', ''))
        self.album_inp.setText(detail.get('album', ''))
        self.year_inp.setText(detail.get('year', ''))
        self.genre_inp.setText(detail.get('genre') or detail.get('style', ''))
        self.label_inp.setText(detail.get('label', ''))

    def _check_compilation(self):
        if any(' /// ' in t.get('title', '') for t in self._tracklist):
            self.cb_compilation.setChecked(True)

    def _on_cell_clicked(self, row, col):
        self._move_files = (col <= 1)

    def _select_all(self):
        for i in range(self.match_table.rowCount()):
            it = self.match_table.item(i, 0)
            if it and (it.flags() & Qt.ItemFlag.ItemIsEnabled):
                it.setCheckState(Qt.CheckState.Checked)

    def _select_none(self):
        for i in range(self.match_table.rowCount()):
            it = self.match_table.item(i, 0)
            if it and (it.flags() & Qt.ItemFlag.ItemIsEnabled):
                it.setCheckState(Qt.CheckState.Unchecked)

    def _move_up(self):
        rows = [i.row() for i in self.match_table.selectionModel().selectedRows()]
        if not rows or min(rows) == 0:
            return
        r = rows[0]
        if self._move_files:
            if r < len(self._file_paths):
                self._file_paths[r], self._file_paths[r-1] = self._file_paths[r-1], self._file_paths[r]
        else:
            if r < len(self._tracklist):
                self._tracklist[r], self._tracklist[r-1] = self._tracklist[r-1], self._tracklist[r]
        self._fill_table()
        self.match_table.selectRow(r - 1)

    def _move_down(self):
        rows = [i.row() for i in self.match_table.selectionModel().selectedRows()]
        if not rows or max(rows) >= self.match_table.rowCount() - 1:
            return
        r = rows[0]
        if self._move_files:
            if r < len(self._file_paths) - 1:
                self._file_paths[r], self._file_paths[r+1] = self._file_paths[r+1], self._file_paths[r]
        else:
            if r < len(self._tracklist) - 1:
                self._tracklist[r], self._tracklist[r+1] = self._tracklist[r+1], self._tracklist[r]
        self._fill_table()
        self.match_table.selectRow(r + 1)

    def _search_cover(self):
        import webbrowser
        from urllib.parse import quote
        artist = self.artist_inp.text()
        album  = self.album_inp.text()
        year   = self.year_inp.text()
        q = quote(f"{artist} {album} {year} cover")
        webbrowser.open(f"https://www.google.com/images?hl=&q={q}&tbs=isz:lt,islt:qsvga")

    def _on_cover_changed(self, data):
        try:
            img = Image.open(BytesIO(data))
            self.cover_info.setText(f"{img.width}×{img.height} px  {len(data)//1024} KB")
        except Exception:
            pass

    def _write_tags(self):
        # Save checkbox states
        if self._cfg_save:
            self._cfg_save({'trackmatch_checkboxes': {
                'title': self.cb_title.isChecked(), 'tracknr': self.cb_tracknr.isChecked(),
                'cb_artist': self.cb_artist.isChecked(), 'cb_album': self.cb_album.isChecked(),
                'cb_year': self.cb_year.isChecked(), 'cb_genre': self.cb_genre.isChecked(),
                'cb_label': self.cb_label.isChecked(), 'cover': self.cb_cover.isChecked(),
            }})

        compilation = self.cb_compilation.isChecked()
        cover_bytes = b''
        if self.cb_cover.isChecked() and self.cover_label.get_cover_data():
            try:
                cover_bytes = resize_cover(self.cover_label.get_cover_data(), 600)
            except Exception:
                pass

        result = []
        for i in range(self.match_table.rowCount()):
            cb_item = self.match_table.item(i, 0)
            if not cb_item or cb_item.checkState() != Qt.CheckState.Checked:
                continue
            path = self._file_paths[i] if i < len(self._file_paths) else None
            if not path:
                continue
            track = self._tracklist[i] if i < len(self._tracklist) else {}

            td = {}
            raw_title = track.get('title', '')
            if self.cb_title.isChecked() and raw_title:
                if compilation and ' /// ' in raw_title:
                    parts = raw_title.split(' /// ', 1)
                    td['title'] = parts[0].strip()
                    td['track_artist'] = parts[1].strip()
                else:
                    td['title'] = raw_title

            if self.cb_tracknr.isChecked() and track.get('position'):
                td['tracknumber'] = f"{track['position']}/{len(self._tracklist)}"

            artist = self.artist_inp.text()
            if self.cb_artist.isChecked() and artist:
                if compilation:
                    td['artist'] = td.pop('track_artist', artist)
                    td['album_artist'] = 'Various Artists'
                else:
                    td['artist'] = artist
                    td['album_artist'] = artist

            if self.cb_album.isChecked() and self.album_inp.text():
                td['album'] = self.album_inp.text()
            if self.cb_year.isChecked() and self.year_inp.text():
                td['year'] = self.year_inp.text()
            if self.cb_genre.isChecked() and self.genre_inp.text():
                td['genre'] = self.genre_inp.text()
            if self.cb_label.isChecked() and self.label_inp.text():
                td['label'] = self.label_inp.text()

            result.append((path, td, cover_bytes))

        self.tags_accepted.emit(result)
        self.accept()


class DiscogsDialog(QDialog):
    def __init__(self, prefill, files, discogs_token=None, cfg_save=None, cfg_load=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Discogs Suche  [{len(files)} Dateien markiert]")
        self.setMinimumSize(860, 520)
        self.discogs_token = discogs_token
        self._files = files          # [(path, tags), ...]
        self._cfg_save = cfg_save
        self._cfg_load = cfg_load
        self._current_detail = None
        self._results = []
        self._build_ui(prefill)

    def _build_ui(self, prefill):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Search bar ──
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Künstler:"))
        self.artist_input = QLineEdit(prefill.get('artist', ''))
        search_row.addWidget(self.artist_input, 3)
        search_row.addWidget(QLabel("Album:"))
        self.album_input = QLineEdit(prefill.get('album', ''))
        search_row.addWidget(self.album_input, 3)
        search_row.addWidget(QLabel("Jahr:"))
        self.year_input = QLineEdit(prefill.get('year', ''))
        self.year_input.setMaximumWidth(70)
        search_row.addWidget(self.year_input)
        self.search_btn = QPushButton("Suchen")
        self.search_btn.clicked.connect(self._do_search)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        # ── Results table ──
        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["Künstler / Album", "Jahr", "Label", "Format", "Land"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setShowGrid(False)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.verticalHeader().setDefaultSectionSize(22)
        self.results_table.itemSelectionChanged.connect(self._on_result_selected)
        self.results_table.doubleClicked.connect(self._load_album)
        layout.addWidget(self.results_table)

        # ── Status + buttons ──
        self.status_label = QLabel("Bereit")
        self.status_label.setStyleSheet("color:#6c7086; font-size:11px;")
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        self.load_btn = QPushButton("Lade Album!")
        self.load_btn.setEnabled(False)
        self.load_btn.clicked.connect(self._load_album)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.load_btn)
        layout.addLayout(btn_row)

        # Auto-search on open
        QTimer.singleShot(100, self._do_search)

    def _do_search(self):
        self.search_btn.setEnabled(False)
        self.load_btn.setEnabled(False)
        self.status_label.setText("Suche läuft…")
        self.results_table.setRowCount(0)
        self._search_thread = DiscogsSearchThread(
            self.artist_input.text().strip(),
            self.album_input.text().strip(),
            self.year_input.text().strip(),
            self.discogs_token
        )
        self._search_thread.results_ready.connect(self._on_results)
        self._search_thread.error.connect(self._on_error)
        self._search_thread.start()

    def _on_results(self, results):
        self.search_btn.setEnabled(True)
        self._results = results
        self._detail_cache = {}  # idx → detail dict
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels(
            ["🖼", "Künstler / Album", "Jahr", "Label", "Format", "Land"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.results_table.setColumnWidth(0, 26)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.results_table.setRowCount(len(results))
        bold = QFont(); bold.setBold(True)
        for i, r in enumerate(results):
            master = r.get('is_master', False)
            has_cover = bool(r.get('cover_url', '')) and 'spacer' not in r.get('cover_url', '')
            cov = QTableWidgetItem('🖼' if has_cover else '')
            cov.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if has_cover:
                cov.setForeground(QColor('#a6e3a1'))
            self.results_table.setItem(i, 0, cov)
            items = [
                QTableWidgetItem(('★ ' if master else '') + r['title']),
                QTableWidgetItem(str(r['year'])),
                QTableWidgetItem(r['label']),
                QTableWidgetItem(r['format']),
                QTableWidgetItem(r['country']),
            ]
            for col, item in enumerate(items, 1):
                if master:
                    item.setFont(bold)
                    item.setForeground(QColor('#f9e2af'))
                self.results_table.setItem(i, col, item)
        self.status_label.setText(f"{len(results)} Ergebnis(se) — Doppelklick oder 'Lade Album!'")
        if results:
            self.results_table.selectRow(0)

    def _on_result_selected(self):
        rows = self.results_table.selectionModel().selectedRows()
        if not rows:
            return
        self.load_btn.setEnabled(True)
        idx = rows[0].row()
        if idx >= len(self._results):
            return
        # If already cached, show immediately
        if idx in self._detail_cache:
            self._show_detail_info(self._detail_cache[idx])
            return
        result = self._results[idx]
        self.status_label.setText("Lade Details…")
        self._preview_thread = DiscogsDetailThread(
            result['resource_url'], result['cover_url'], self.discogs_token
        )
        self._preview_thread.detail_ready.connect(lambda d, i=idx: self._on_preview_detail(i, d))
        self._preview_thread.error.connect(lambda e: self.status_label.setText(f"Fehler: {e}"))
        self._preview_thread.start()

    def _on_preview_detail(self, idx, detail):
        self._detail_cache[idx] = detail
        # Update cover indicator
        if detail.get('cover_data'):
            item = self.results_table.item(idx, 0)
            if item:
                item.setText('🖼')
                item.setForeground(QColor('#89b4fa'))
        self._show_detail_info(detail)

    def _show_detail_info(self, detail):
        tracks = detail.get('tracklist', [])
        total_secs = 0
        for t in tracks:
            dur = t.get('duration', '')
            if ':' in dur:
                p = dur.split(':')
                try:
                    total_secs += int(p[0])*60+int(p[1]) if len(p)==2 else int(p[0])*3600+int(p[1])*60+int(p[2])
                except ValueError:
                    pass
        dur_str = format_duration(total_secs) if total_secs else '–'
        cover_str = '🖼 Cover' if detail.get('cover_data') else '∅ Kein Cover'
        self.status_label.setText(
            f"{len(tracks)} Tracks  ·  {dur_str}  ·  {cover_str}"
        )

    def _load_album(self):
        rows = self.results_table.selectionModel().selectedRows()
        if not rows or not self._results:
            return
        idx = rows[0].row()
        if idx >= len(self._results):
            return
        # Use cached detail if available (already loaded on single-click)
        if idx in self._detail_cache:
            self._on_detail(self._detail_cache[idx])
            return
        result = self._results[idx]
        self.load_btn.setEnabled(False)
        self.status_label.setText("Lade Details und Cover…")
        self._detail_thread = DiscogsDetailThread(
            result['resource_url'], result['cover_url'], self.discogs_token
        )
        self._detail_thread.detail_ready.connect(self._on_detail)
        self._detail_thread.error.connect(self._on_error)
        self._detail_thread.start()

    def _on_detail(self, detail):
        self.load_btn.setEnabled(True)
        tracks = detail['tracklist']
        total_secs = 0
        for t in tracks:
            dur = t.get('duration', '')
            if ':' in dur:
                p = dur.split(':')
                try:
                    total_secs += int(p[0])*60 + int(p[1]) if len(p)==2 else int(p[0])*3600+int(p[1])*60+int(p[2])
                except ValueError:
                    pass
        dur_str = format_duration(total_secs) if total_secs else '–'
        self.status_label.setText(f"Geladen — {len(tracks)} Tracks — {dur_str}")

        dlg = TrackMatchDialog(
            self._files, detail,
            cfg_save=self._cfg_save, cfg_load=self._cfg_load,
            parent=self.parent()
        )
        dlg.tags_accepted.connect(self._forward_tags)
        if dlg.exec():
            self.accept()

    def _forward_tags(self, result):
        # bubble up to MainWindow
        self.parent()._apply_tags_from_trackmatch(result)

    def _on_error(self, msg):
        self.search_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        self.status_label.setText(f"Fehler: {msg}")


class RenameDialog(QDialog):
    masks_changed = pyqtSignal(list)

    def __init__(self, files, masks=None, last_mask='', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dateien umbenennen")
        self.setMinimumSize(750, 520)
        self.files = files
        self._masks = masks or ["%6-%2", "%1 - %6 - %2", "%1\\[%4] %3\\%6 - %2"]
        self._last_mask = last_mask
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "%1=Künstler  %2=Titel  %3=Album  %4=Jahr  %5=Genre  "
            "%6=Track-Nr.  %t=Dauer  %b=Bitrate  —  Ordner mit \\:  %1\\[%4] %3\\%6-%2"
        )
        info.setStyleSheet("color: #6c7086; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        mask_row = QHBoxLayout()
        mask_row.addWidget(QLabel("Maske:"))
        self.mask_input = QComboBox()
        self.mask_input.setEditable(True)
        self.mask_input.addItems(self._masks)
        if self._last_mask and self._last_mask in self._masks:
            self.mask_input.setCurrentText(self._last_mask)
        elif self._masks:
            self.mask_input.setCurrentText(self._masks[0])
        mask_row.addWidget(self.mask_input, stretch=1)

        save_btn = QPushButton("💾")
        save_btn.setToolTip("Aktuelle Maske speichern")
        save_btn.setObjectName("secondary")
        save_btn.setFixedWidth(32)
        save_btn.clicked.connect(self._save_mask)
        mask_row.addWidget(save_btn)

        del_btn = QPushButton("🗑")
        del_btn.setToolTip("Ausgewählte Maske löschen")
        del_btn.setObjectName("secondary")
        del_btn.setFixedWidth(32)
        del_btn.clicked.connect(self._delete_mask)
        mask_row.addWidget(del_btn)

        self.case_combo = QComboBox()
        self.case_combo.addItems(["Unverändert", "alles klein", "ALLES GROSS", "Erster Groß"])
        self.case_combo.setFixedWidth(130)
        mask_row.addWidget(self.case_combo)

        preview_btn = QPushButton("Vorschau")
        preview_btn.setObjectName("secondary")
        preview_btn.clicked.connect(self._update_preview)
        mask_row.addWidget(preview_btn)
        layout.addLayout(mask_row)

        self.preview_table = QTableWidget(0, 2)
        self.preview_table.setHorizontalHeaderLabels(["Aktueller Name", "Neuer Name"])
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.preview_table)

        btn_layout = QHBoxLayout()
        self.rename_btn = QPushButton("Umbenennen")
        self.rename_btn.clicked.connect(self._do_rename)
        cancel_btn = QPushButton("Schließen")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.rename_btn)
        layout.addLayout(btn_layout)

        self._update_preview()

    def _save_mask(self):
        mask = self.mask_input.currentText().strip()
        if not mask:
            return
        if mask not in self._masks:
            self._masks.append(mask)
            self.mask_input.addItem(mask)
        self.masks_changed.emit(list(self._masks))

    def _delete_mask(self):
        idx = self.mask_input.currentIndex()
        text = self.mask_input.currentText()
        if text in self._masks:
            self._masks.remove(text)
        if idx >= 0:
            self.mask_input.removeItem(idx)
        self.masks_changed.emit(list(self._masks))

    def _apply_mask(self, mask, tags):
        result = mask
        track = tags.get('tracknumber', '').split('/')[0].zfill(2)
        result = result.replace('%1', tags.get('artist', ''))
        result = result.replace('%2', tags.get('title', ''))
        result = result.replace('%3', tags.get('album', ''))
        result = result.replace('%4', tags.get('year', ''))
        result = result.replace('%5', tags.get('genre', ''))
        result = result.replace('%6', track)
        result = result.replace('%t', format_duration(tags.get('duration', 0)))
        result = result.replace('%b', str(tags.get('bitrate', 0)))
        # Clean illegal chars per path segment, preserve drive letter (X:\)
        parts = result.split('\\')
        clean = []
        for i, p in enumerate(parts):
            if i == 0 and len(p) == 2 and p[1] == ':':
                clean.append(p)  # drive letter — keep as-is
            else:
                clean.append(re.sub(r'[<>:"/|?*]', '', p).strip())
        return '\\'.join(clean)

    def _apply_case(self, s):
        case = self.case_combo.currentIndex()
        if case == 1:
            return s.lower()
        elif case == 2:
            return s.upper()
        elif case == 3:
            return s.title()
        return s

    def _resolve_dest(self, path, new_base):
        """Build destination Path from mask result — supports absolute paths."""
        if len(new_base) >= 3 and new_base[1] == ':' and new_base[2] == '\\':
            # Absolute path — use directly
            dest = Path(new_base + '.mp3')
            dest.parent.mkdir(parents=True, exist_ok=True)
        elif '\\' in new_base:
            sub, fname = new_base.rsplit('\\', 1)
            dest_dir = Path(path).parent / sub
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / (fname + '.mp3')
        else:
            dest = Path(path).parent / (new_base + '.mp3')
        return dest

    def _update_preview(self):
        mask = self.mask_input.currentText()
        self.preview_table.setRowCount(len(self.files))
        for i, (path, tags) in enumerate(self.files):
            old_name = Path(path).name
            new_base = self._apply_case(self._apply_mask(mask, tags))
            dest = self._resolve_dest(path, new_base)
            new_display = str(dest) if dest.is_absolute() else dest.name
            self.preview_table.setItem(i, 0, QTableWidgetItem(old_name))
            color = '#a6e3a1' if Path(path) != dest else '#6c7086'
            item = QTableWidgetItem(new_display)
            item.setForeground(QColor(color))
            self.preview_table.setItem(i, 1, item)

    def _do_rename(self):
        mask = self.mask_input.currentText()
        # Persist last used mask
        self.masks_changed.emit(list(self._masks))  # save mask list
        parent = self.parent()
        if parent and hasattr(parent, '_save_config'):
            parent._save_config({'last_rename_mask': mask})
        errors = []
        renamed = 0
        moved_folders = set()

        # Step 1: create folder.jpg from first MP3 tag cover if none exists yet
        if self.files:
            first_dir = Path(self.files[0][0]).parent
            folder_jpg = first_dir / 'folder.jpg'
            if not folder_jpg.exists():
                for path, tags in self.files:
                    cover_data = tags.get('cover')
                    if cover_data:
                        try:
                            folder_jpg.write_bytes(resize_cover(cover_data, 600))
                        except Exception:
                            pass
                        break

        for path, tags in self.files:
            new_base = self._apply_case(self._apply_mask(mask, tags))
            src = Path(path)
            dest = self._resolve_dest(path, new_base)
            if src == dest:
                continue
            try:
                src.rename(dest)
                renamed += 1
                moved_folders.add((src.parent, dest.parent))
            except Exception as e:
                errors.append(f"{src.name}: {e}")

        # Copy folder.jpg to each new destination folder
        import shutil
        for src_dir, dest_dir in moved_folders:
            if src_dir == dest_dir:
                continue
            folder_jpg = src_dir / 'folder.jpg'
            if folder_jpg.exists():
                try:
                    shutil.copy2(folder_jpg, dest_dir / 'folder.jpg')
                except Exception as e:
                    errors.append(f"folder.jpg → {dest_dir.name}: {e}")

        msg = f"{renamed} Datei(en) umbenannt/verschoben."
        if errors:
            msg += "\n\nFehler:\n" + "\n".join(errors)
        QMessageBox.information(self, "Umbenennen", msg)
        self.accept()


def check_cover(cover_data):
    """Returns (status, info): status = 'ok'|'corrupt'|'small'|'none'."""
    if not cover_data:
        return 'none', 'Kein Cover'
    try:
        img = Image.open(BytesIO(cover_data))
        img.load()  # Force full decode — catches truncated/corrupt data
        img.convert('RGB')  # Catches palette/mode errors
        w, h = img.size
        if w < 300 or h < 300:
            return 'small', f'{w}×{h} px (zu klein)'
        return 'ok', f'{w}×{h} px'
    except Exception as e:
        return 'corrupt', str(e)[:60]


class CoverScanThread(QThread):
    progress = pyqtSignal(int, int, str)   # done, total, current_path
    result = pyqtSignal(list)              # list of (folder, issues)

    def __init__(self, root):
        super().__init__()
        self.root = root

    def run(self):
        root = Path(self.root)
        # Collect all folders that contain MP3s
        folders = sorted({p.parent for p in root.rglob('*.mp3')})
        total = len(folders)
        bad = []
        for i, folder in enumerate(folders):
            self.progress.emit(i, total, str(folder))
            mp3s = sorted(folder.glob('*.mp3'), key=natural_sort_key)
            folder_issues = []
            for mp3 in mp3s:
                tags = load_mp3_tags(str(mp3))
                status, info = check_cover(tags.get('cover'))
                if status != 'ok':
                    folder_issues.append((str(mp3), status, info))
            if folder_issues:
                bad.append((str(folder), folder_issues))
        self.progress.emit(total, total, '')
        self.result.emit(bad)


class CoverScanDialog(QDialog):
    load_folder = pyqtSignal(str)

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cover-Qualitäts-Scanner")
        self.setMinimumSize(900, 600)
        self.root = root
        self._build_ui()
        QTimer.singleShot(100, self._start_scan)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.progress_label = QLabel(f"Scanne: {self.root}")
        self.progress_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        legend = QLabel(
            "🔴 Korruptes Cover   🟡 Cover zu klein (<300px)   ⚪ Kein Cover"
        )
        legend.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(legend)

        self.result_table = QTableWidget(0, 4)
        self.result_table.setHorizontalHeaderLabels(
            ["Album-Ordner", "Dateien mit Problem", "Problem-Typ", "Details"]
        )
        hh = self.result_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.result_table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.result_table)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8;")
        layout.addWidget(self.summary_label)

        btn_row = QHBoxLayout()
        hint = QLabel("Doppelklick auf Zeile → Ordner im Tagger laden")
        hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        btn_row.addWidget(hint)
        btn_row.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.setObjectName("secondary")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _start_scan(self):
        self._thread = CoverScanThread(self.root)
        self._thread.progress.connect(self._on_progress)
        self._thread.result.connect(self._on_result)
        self._thread.start()

    def _on_progress(self, done, total, path):
        self.progress_bar.setMaximum(max(total, 1))
        self.progress_bar.setValue(done)
        if path:
            short = path[-70:] if len(path) > 70 else path
            self.progress_label.setText(f"Scanne: …{short}")

    def _on_result(self, bad_folders):
        self.progress_label.setText(f"Scan abgeschlossen — {len(bad_folders)} Ordner mit Problemen")
        self.progress_bar.setValue(self.progress_bar.maximum())

        STATUS_ICON = {'corrupt': '🔴', 'small': '🟡', 'none': '⚪'}
        STATUS_PRIO = {'corrupt': 0, 'small': 1, 'none': 2}
        STATUS_COLOR = {'corrupt': '#f38ba8', 'small': '#f9e2af', 'none': '#6c7086'}

        self.result_table.setRowCount(len(bad_folders))
        self._folder_paths = []
        for i, (folder, issues) in enumerate(bad_folders):
            self._folder_paths.append(folder)
            # Worst status in this folder
            worst = min(issues, key=lambda x: STATUS_PRIO[x[1]])[1]
            color = STATUS_COLOR[worst]
            icon = STATUS_ICON[worst]

            types = sorted({s for _, s, _ in issues}, key=lambda s: STATUS_PRIO[s])
            type_str = '  '.join(STATUS_ICON[t] for t in types)
            details = ', '.join(sorted({info for _, _, info in issues}))

            items = [
                QTableWidgetItem(Path(folder).name),
                QTableWidgetItem(str(len(issues))),
                QTableWidgetItem(type_str),
                QTableWidgetItem(details),
            ]
            for item in items:
                item.setForeground(QColor(color))
                self.result_table.setItem(i, items.index(item), item)

        corrupt = sum(1 for _, iss in bad_folders if any(s == 'corrupt' for _, s, _ in iss))
        small   = sum(1 for _, iss in bad_folders if any(s == 'small'   for _, s, _ in iss))
        none_   = sum(1 for _, iss in bad_folders if any(s == 'none'    for _, s, _ in iss))
        self.summary_label.setText(
            f"🔴 Korrupt: {corrupt}   🟡 Zu klein: {small}   ⚪ Kein Cover: {none_}"
        )

    def _on_double_click(self, index):
        row = index.row()
        if row < len(self._folder_paths):
            self.load_folder.emit(self._folder_paths[row])
            self.accept()


class SettingsDialog(QDialog):
    def __init__(self, token, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Discogs Personal Access Token:"))
        self.token_input = QLineEdit(token or '')
        self.token_input.setPlaceholderText("Leer lassen für anonyme Suche (Rate-Limit)")
        layout.addWidget(self.token_input)

        hint = QLabel(
            "Token erstellen unter: discogs.com → Einstellungen → Entwickler\n"
            "Mit Token: 60 Anfragen/Min statt 25"
        )
        hint.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(hint)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_token(self):
        return self.token_input.text().strip()


class FolderTreeWidget(QTreeWidget):
    """Explorer-style folder tree with special folders, drives and libraries."""
    folder_selected = pyqtSignal(str)

    SPECIAL = [
        ('🎵  Musik',      QStandardPaths.StandardLocation.MusicLocation),
        ('⬇  Downloads',   QStandardPaths.StandardLocation.DownloadLocation),
        ('🖥  Desktop',    QStandardPaths.StandardLocation.DesktopLocation),
        ('📄  Dokumente',  QStandardPaths.StandardLocation.DocumentsLocation),
        ('🎬  Videos',     QStandardPaths.StandardLocation.MoviesLocation),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(18)
        self.setAnimated(True)
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #181825; border: none;
                color: #cdd6f4; outline: none;
            }
            QTreeWidget::item {
                padding: 3px 4px; border: none; min-height: 22px;
            }
            QTreeWidget::item:hover { background-color: #2a2a3e; }
            QTreeWidget::item:selected {
                background-color: #313244; color: #89b4fa;
                border-left: 2px solid #89b4fa;
            }
            QTreeWidget::branch { background-color: #181825; }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                border-image: none; image: none;
                background-color: #181825;
            }
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {
                border-image: none; image: none;
                background-color: #181825;
            }
        """)
        self.itemExpanded.connect(self._on_expand)
        self.itemCollapsed.connect(self._on_collapse)
        self.itemClicked.connect(self._on_click)
        self.itemDoubleClicked.connect(self._on_double_click)
        self.setExpandsOnDoubleClick(False)
        self._pending_item = None
        self._click_timer = None  # created lazily after event loop starts
        QTimer.singleShot(0, self._populate)  # populate after event loop starts

    @staticmethod
    def _safe_is_dir(path, timeout=0.5):
        """Check is_dir() in a thread with timeout to avoid network hangs."""
        import threading
        result = [False]
        def check():
            try:
                result[0] = Path(path).is_dir()
            except Exception:
                pass
        t = threading.Thread(target=check, daemon=True)
        t.start()
        t.join(timeout)
        return result[0]

    def _populate(self):
        # ── Special folders ──
        for label, loc in self.SPECIAL:
            paths = QStandardPaths.standardLocations(loc)
            if paths and self._safe_is_dir(paths[0]):
                item = self._make_item(label, paths[0])
                self.addTopLevelItem(item)

        # ── Dieser PC ──
        pc = QTreeWidgetItem(['💻  Dieser PC'])
        pc.setData(0, Qt.ItemDataRole.UserRole, '__group__')
        pc.setForeground(0, QColor('#6c7086'))
        self.addTopLevelItem(pc)
        import string, ctypes
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            # Use GetDriveType to avoid triggering network/removable media dialogs
            try:
                dt = ctypes.windll.kernel32.GetDriveTypeW(drive)
                if dt < 2:  # 0=unknown, 1=no root
                    continue
            except Exception:
                continue
            drive_item = self._make_item(f"  {letter}:", drive)
            pc.addChild(drive_item)
        pc.setExpanded(True)

        # ── Bibliotheken ──
        lib_paths = {
            '🎵  Musik':     QStandardPaths.standardLocations(QStandardPaths.StandardLocation.MusicLocation),
            '📷  Bilder':    QStandardPaths.standardLocations(QStandardPaths.StandardLocation.PicturesLocation),
            '📄  Dokumente': QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DocumentsLocation),
            '🎬  Videos':    QStandardPaths.standardLocations(QStandardPaths.StandardLocation.MoviesLocation),
        }
        libs = QTreeWidgetItem(['📚  Bibliotheken'])
        libs.setData(0, Qt.ItemDataRole.UserRole, '__group__')
        libs.setForeground(0, QColor('#6c7086'))
        self.addTopLevelItem(libs)
        for label, paths in lib_paths.items():
            if paths and self._safe_is_dir(paths[0]):
                libs.addChild(self._make_item(label, paths[0]))

    def _make_item(self, label, path):
        item = QTreeWidgetItem(['▶ ' + label])
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        if path and path not in ('__group__', '__ph__'):
            # Always add placeholder — avoids slow is_dir() calls on network drives
            ph = QTreeWidgetItem([''])
            ph.setData(0, Qt.ItemDataRole.UserRole, '__ph__')
            item.addChild(ph)
        return item

    def _on_expand(self, item):
        # Update arrow prefix
        t = item.text(0)
        if t.startswith('▶ '):
            item.setText(0, '▼ ' + t[2:])
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or path in ('__group__', '__ph__'):
            return
        if item.childCount() == 1 and item.child(0).data(0, Qt.ItemDataRole.UserRole) == '__ph__':
            item.takeChild(0)
            import os, threading
            dirs_result = []
            def _scan():
                try:
                    dirs_result.extend(sorted(
                        (Path(e.path) for e in os.scandir(path)
                         if e.is_dir(follow_symlinks=False) and not e.name.startswith('.')),
                        key=lambda p: p.name.lower()
                    ))
                except Exception:
                    pass
            t = threading.Thread(target=_scan, daemon=True)
            t.start()
            t.join(2.0)  # max 2s for any directory listing
            for d in dirs_result:
                item.addChild(self._make_item(d.name, str(d)))

    def _on_collapse(self, item):
        t = item.text(0)
        if t.startswith('▼ '):
            item.setText(0, '▶ ' + t[2:])

    def _get_timer(self):
        if self._click_timer is None:
            self._click_timer = QTimer(self)
            self._click_timer.setSingleShot(True)
            self._click_timer.setInterval(350)
            self._click_timer.timeout.connect(self._do_expand_pending)
        return self._click_timer

    def _on_click(self, item, col):
        """Single click: queue expand — cancelled if double-click follows."""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or path in ('__group__', '__ph__'):
            return
        t = self._get_timer()
        t.stop()
        self._pending_item = item
        t.start()

    def _do_expand_pending(self):
        """Fires 350ms after single click if no double-click came."""
        if self._pending_item:
            self._pending_item.setExpanded(not self._pending_item.isExpanded())
        self._pending_item = None

    def _on_double_click(self, item, col):
        """Double click: cancel pending expand and scan the folder."""
        if self._click_timer:
            self._click_timer.stop()
        self._pending_item = None
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or path in ('__group__', '__ph__'):
            return
        p = Path(path)
        if p == p.parent:  # root drive — just expand
            item.setExpanded(not item.isExpanded())
            return
        if self._safe_is_dir(path):
            self.folder_selected.emit(path)

    def navigate_to(self, path):
        """Expand tree to show a given path and select it."""
        parts = Path(path).parts
        # Find matching top-level drive item under "Dieser PC"
        for i in range(self.topLevelItemCount()):
            tl = self.topLevelItem(i)
            for j in range(tl.childCount()):
                child = tl.child(j)
                cp = child.data(0, Qt.ItemDataRole.UserRole) or ''
                if cp and Path(cp).drive == Path(path).drive:
                    self._expand_to(child, path)
                    return
        # Also check top-level special folders
        for i in range(self.topLevelItemCount()):
            tl = self.topLevelItem(i)
            cp = tl.data(0, Qt.ItemDataRole.UserRole) or ''
            if cp and path.startswith(cp):
                self._expand_to(tl, path)
                return

    def _expand_to(self, start_item, target_path):
        """Recursively expand items until we reach target_path."""
        try:
            self._on_expand(start_item)
            start_item.setExpanded(True)
            for i in range(start_item.childCount()):
                child = start_item.child(i)
                cp = child.data(0, Qt.ItemDataRole.UserRole) or ''
                if cp and target_path.startswith(cp):
                    if cp == target_path:
                        self.setCurrentItem(child)
                        self.scrollToItem(child)
                        return
                    self._expand_to(child, target_path)
                    return
        except Exception:
            pass


class FolderScanThread(QThread):
    progress = pyqtSignal(int, str)   # count, current filename
    scan_done = pyqtSignal(object)    # [(path, tags), ...] — object avoids list copy overhead

    def __init__(self, path):
        super().__init__()
        self.path = path
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        results = []
        try:
            for mp3 in Path(self.path).rglob('*.mp3'):
                if self._cancel:
                    return
                tags = load_mp3_tags(str(mp3))
                results.append((str(mp3), tags))
                self.progress.emit(len(results), mp3.name)
        except Exception:
            pass
        if not self._cancel:
            results.sort(key=lambda x: (
                x[1].get('album', '').lower(),
                natural_sort_key(Path(x[0]))
            ))
            self.scan_done.emit(results)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TagMeGently")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)
        self._current_folder = None
        self._current_folder_jpg = None
        self._files = []  # list of (path, tags)
        self._discogs_token = self._load_token()
        self._build_ui()
        self._build_menu()
        # _restore_last_folder disabled — crashes Qt on network paths (QFileSystemModel.index)

    def _load_config(self):
        cfg = Path.home() / '.tagmegently.json'
        if cfg.exists():
            try:
                return json.loads(cfg.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _save_config(self, data):
        cfg = Path.home() / '.tagmegently.json'
        existing = self._load_config()
        existing.update(data)
        cfg.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')

    def _restore_last_folder(self):
        last = self._load_config().get('last_folder', '')
        if not last:
            return
        import threading
        result = [False]
        def check():
            try:
                p = Path(last)
                result[0] = p.is_dir() and p != p.parent
            except Exception:
                pass
        t = threading.Thread(target=check, daemon=True)
        t.start()
        t.join(1.5)
        if result[0]:
            self._load_folder(last)  # skip fs_model.index() — crashes on network paths

    def _load_token(self):
        return self._load_config().get('discogs_token', '')

    def _save_token(self, token):
        self._save_config({'discogs_token': token})

    def _load_masks(self):
        default = ["%6-%2", "%1 - %6 - %2", "%1\\[%4] %3\\%6 - %2", "%1\\%3\\%6 - %2"]
        return self._load_config().get('rename_masks', default)

    def _save_masks(self, masks):
        self._save_config({'rename_masks': masks})

    def _clear_last_folder(self):
        self._save_config({'last_folder': ''})

    def _build_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar { background-color: #181825; color: #cdd6f4; }
            QMenuBar::item:selected { background-color: #313244; }
            QMenu { background-color: #24273a; color: #cdd6f4; border: 1px solid #45475a; }
            QMenu::item:selected { background-color: #45475a; }
        """)
        tools_menu = menubar.addMenu("Tools")
        settings_action = QAction("Einstellungen (Discogs Token)", self)
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)
        clear_folder_action = QAction("Letzten Ordner vergessen", self)
        clear_folder_action.triggered.connect(self._clear_last_folder)
        tools_menu.addAction(clear_folder_action)

        about_menu = menubar.addMenu("Über")
        about_action = QAction("Über TagMeGently", self)
        about_action.triggered.connect(self._open_about)
        about_menu.addAction(about_action)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Compact toolbar
        toolbar_widget = QWidget()
        toolbar_widget.setStyleSheet("background-color: #181825; border-radius: 4px;")
        toolbar_widget.setFixedHeight(36)
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(6, 2, 6, 2)
        toolbar_layout.setSpacing(4)

        primary_ss = """
            QPushButton { min-height:24px; padding:2px 12px; font-size:12px; font-weight:700;
                          background-color:#89b4fa; color:#11111b; border:none; border-radius:5px; }
            QPushButton:hover { background-color:#a8c7ff; }
            QPushButton:pressed { background-color:#6d9ee8; }
            QPushButton:disabled { background-color:#1e1e2e; color:#45475a; border:1px solid #313244; }
        """
        secondary_ss = """
            QPushButton { min-height:24px; padding:2px 10px; font-size:12px; font-weight:600;
                          background-color:transparent; color:#a6adc8; border:1px solid #313244; border-radius:5px; }
            QPushButton:hover { background-color:#1e1e2e; color:#cdd6f4; border-color:#585b70; }
            QPushButton:pressed { background-color:#313244; }
            QPushButton:disabled { color:#45475a; border-color:#1e1e2e; }
        """

        self.discogs_btn = QPushButton("🔍  Discogs")
        self.discogs_btn.setEnabled(False)
        self.discogs_btn.setStyleSheet(primary_ss)
        self.discogs_btn.clicked.connect(self._open_discogs)

        self.rename_btn = QPushButton("✏️  Umbenennen")
        self.rename_btn.setEnabled(False)
        self.rename_btn.setStyleSheet(secondary_ss)
        self.rename_btn.clicked.connect(self._open_rename)

        self.quick_rename_btn = QPushButton("⚡")
        self.quick_rename_btn.setEnabled(False)
        self.quick_rename_btn.setFixedWidth(30)
        self.quick_rename_btn.setStyleSheet(secondary_ss)
        self.quick_rename_btn.clicked.connect(self._quick_rename)
        self._update_quick_rename_tooltip()

        self.autonumber_btn = QPushButton("# Nummerierung")
        self.autonumber_btn.setEnabled(False)
        self.autonumber_btn.setToolTip(
            "Schreibt Track-Nummern (1, 2, 3…) in die Tags der markierten Dateien\n"
            "in der Reihenfolge wie sie in der Liste erscheinen"
        )
        self.autonumber_btn.setStyleSheet(secondary_ss)
        self.autonumber_btn.clicked.connect(self._autonumber_tracks)

        self.select_all_btn = QPushButton("Alle")
        self.select_all_btn.setStyleSheet(secondary_ss)
        self.select_all_btn.clicked.connect(self._select_all)

        self.deselect_btn = QPushButton("Keine")
        self.deselect_btn.setStyleSheet(secondary_ss)
        self.deselect_btn.clicked.connect(self._deselect_all)

        self.cover_scan_btn = QPushButton("🔍  Cover-Scan")
        self.cover_scan_btn.setEnabled(False)
        self.cover_scan_btn.setStyleSheet(secondary_ss)
        self.cover_scan_btn.setToolTip("Scannt alle Unterordner auf kaputte/fehlende Cover")
        self.cover_scan_btn.clicked.connect(self._open_cover_scan)

        self.cancel_scan_btn = QPushButton("✕ Abbrechen")
        self.cancel_scan_btn.setStyleSheet("""
            QPushButton { min-height:24px; padding:2px 10px; font-size:12px; font-weight:600;
                          background-color:transparent; color:#f38ba8; border:1px solid #f38ba8; border-radius:5px; }
            QPushButton:hover { background-color:#4a2a2e; }
        """)
        self.cancel_scan_btn.setVisible(False)
        self.cancel_scan_btn.clicked.connect(self._cancel_scan)

        toolbar_layout.addWidget(self.discogs_btn)
        toolbar_layout.addWidget(self.rename_btn)
        toolbar_layout.addWidget(self.quick_rename_btn)
        toolbar_layout.addWidget(self.autonumber_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self.select_all_btn)
        toolbar_layout.addWidget(self.deselect_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self.cover_scan_btn)
        toolbar_layout.addWidget(self.cancel_scan_btn)
        toolbar_layout.addStretch()

        self.folder_label = QLabel("Kein Ordner ausgewählt")
        self.folder_label.setStyleSheet("color: #6c7086; font-size: 11px;")
        toolbar_layout.addWidget(self.folder_label)

        main_layout.addWidget(toolbar_widget)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: folder tree + cover preview
        tree_widget = QWidget()
        tree_layout = QVBoxLayout(tree_widget)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(4)

        tree_label = QLabel("Explorer")
        tree_label.setObjectName("heading")
        tree_layout.addWidget(tree_label)

        # Special folder quick-access
        from PyQt6.QtCore import QStandardPaths
        special = [
            ('🎵 Musik',     QStandardPaths.StandardLocation.MusicLocation),
            ('⬇ Downloads', QStandardPaths.StandardLocation.DownloadLocation),
            ('🖥 Desktop',  QStandardPaths.StandardLocation.DesktopLocation),
            ('📄 Dokumente', QStandardPaths.StandardLocation.DocumentsLocation),
            ('🎬 Videos',   QStandardPaths.StandardLocation.MoviesLocation),
        ]
        quick_widget = QWidget()
        quick_widget.setStyleSheet("background-color: #181825;")
        quick_layout = QVBoxLayout(quick_widget)
        quick_layout.setContentsMargins(4, 4, 4, 2)
        quick_layout.setSpacing(1)
        quick_btn_style = ("QPushButton { text-align:left; background:transparent; color:#a6adc8;"
                           " border:none; padding:3px 6px; font-size:12px; border-radius:4px; }"
                           "QPushButton:hover { background:#313244; color:#cdd6f4; }")
        for label, loc in special:
            paths = QStandardPaths.standardLocations(loc)
            if paths:
                path = paths[0]
                btn = QPushButton(label)
                btn.setStyleSheet(quick_btn_style)
                btn.clicked.connect(lambda checked, p=path: self._navigate_tree(p))
                quick_layout.addWidget(btn)
        tree_layout.addWidget(quick_widget)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #313244;")
        tree_layout.addWidget(sep)

        self.fs_model = QFileSystemModel()
        # Disable file watcher — prevents crashes on network/UNC paths
        self.fs_model.setOption(QFileSystemModel.Option.DontWatchForChanges)
        self.fs_model.setRootPath('')
        self.fs_model.setFilter(QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot)
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.fs_model)
        self.tree_view.setRootIndex(self.fs_model.index(''))
        for col in range(1, 4):
            self.tree_view.hideColumn(col)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(12)
        self.tree_view.setStyleSheet("""
            QTreeView { background-color: #181825; }
            QTreeView::item { padding: 3px 4px; min-height: 20px; }
            QTreeView::item:hover { background-color: #2a2a3e; }
            QTreeView::item:selected { background-color: #313244; color: #89b4fa; }
            QTreeView::branch { background-color: #181825; }
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings { border-image: none; image: none; }
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings { border-image: none; image: none; }
        """)

        class ArrowDelegate(QStyledItemDelegate):
            def __init__(self, view):
                super().__init__(view)
                self._view = view
            def initStyleOption(self, option, index):
                super().initStyleOption(option, index)
                if index.model() and index.model().hasChildren(index):
                    arrow = '▼ ' if self._view.isExpanded(index) else '▶ '
                    option.text = arrow + option.text
                else:
                    option.text = '    ' + option.text

        self.tree_view.setItemDelegate(ArrowDelegate(self.tree_view))
        self.tree_view.selectionModel().selectionChanged.connect(
            lambda: self.cover_scan_btn.setEnabled(self.tree_view.currentIndex().isValid())
        )
        self.tree_view.setExpandsOnDoubleClick(False)
        self._tree_click_timer = QTimer()
        self._tree_click_timer.setSingleShot(True)
        self._tree_click_timer.setInterval(220)
        self._tree_pending_index = None
        self._tree_click_timer.timeout.connect(self._do_tree_expand)
        self.tree_view.clicked.connect(self._on_folder_clicked)
        self.tree_view.doubleClicked.connect(self._on_folder_double_clicked)
        tree_layout.addWidget(self.tree_view)

        # Cover previews: folder.jpg (left) + tag cover (right)
        cover_row = QHBoxLayout()
        cover_row.setSpacing(4)

        cover_lbl_style = ("background-color:#1e1e2e; border:1px solid #313244;"
                           "border-radius:5px; color:#45475a; font-size:10px;")

        left_col = QVBoxLayout()
        left_col.setSpacing(2)
        folder_hdr = QLabel("folder.jpg")
        folder_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        folder_hdr.setStyleSheet("color:#6c7086; font-size:10px;")
        left_col.addWidget(folder_hdr)
        self.folder_cover = QLabel("–")
        self.folder_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.folder_cover.setFixedSize(128, 128)
        self.folder_cover.setStyleSheet(cover_lbl_style)
        self.folder_cover.setScaledContents(False)
        left_col.addWidget(self.folder_cover)
        cover_row.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.setSpacing(2)
        tag_hdr = QLabel("Tag Cover")
        tag_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag_hdr.setStyleSheet("color:#6c7086; font-size:10px;")
        right_col.addWidget(tag_hdr)
        self.cover_preview = QLabel("–")
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_preview.setFixedSize(128, 128)
        self.cover_preview.setStyleSheet(cover_lbl_style)
        self.cover_preview.setScaledContents(False)
        right_col.addWidget(self.cover_preview)
        cover_row.addLayout(right_col)

        tree_layout.addLayout(cover_row)

        self.folder_to_tag_btn = QPushButton("folder.jpg als Tag-Cover setzen")
        self.folder_to_tag_btn.setVisible(False)
        self.folder_to_tag_btn.setStyleSheet("""
            QPushButton { background-color:#313244; color:#a6e3a1; border:1px solid #a6e3a1;
                          border-radius:5px; padding:3px 8px; font-size:11px; }
            QPushButton:hover { background-color:#3a4a3a; }
        """)
        self.folder_to_tag_btn.clicked.connect(self._write_folder_jpg_to_tags)
        tree_layout.addWidget(self.folder_to_tag_btn)

        self.cover_info_label = QLabel("")
        self.cover_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_info_label.setStyleSheet("color: #6c7086; font-size: 10px;")
        self.cover_info_label.setFixedHeight(14)
        tree_layout.addWidget(self.cover_info_label)

        splitter.addWidget(tree_widget)

        # Right: file table
        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(4)

        files_label = QLabel("Dateien")
        files_label.setObjectName("heading")
        files_layout.addWidget(files_label)

        # 9 columns: Cover, Track, Dateiname, Künstler, Album, Titel, Jahr, Genre, Dauer
        # path stored in col 2 (Dateiname) via UserRole
        self.file_table = QTableWidget(0, 9)
        self.file_table.setHorizontalHeaderLabels([
            "🖼", "Track", "Dateiname", "Künstler", "Album", "Titel", "Jahr", "Genre", "Dauer"
        ])
        hh = self.file_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.file_table.setColumnWidth(0, 28)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_table.setSortingEnabled(True)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.verticalHeader().setDefaultSectionSize(22)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setShowGrid(False)
        self.file_table.itemSelectionChanged.connect(self._on_selection_changed)
        files_layout.addWidget(self.file_table)

        splitter.addWidget(files_widget)
        splitter.setSizes([280, 900])
        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit")

    def _navigate_tree(self, path):
        """Expand the tree to show path and select it (without scanning)."""
        def do_navigate():
            try:
                idx = self.fs_model.index(path)
                if idx.isValid():
                    self.tree_view.setCurrentIndex(idx)
                    self.tree_view.expand(idx)
                    self.tree_view.scrollTo(idx)
            except Exception:
                pass
        QTimer.singleShot(0, do_navigate)

    def _on_folder_clicked(self, index):
        """Single click: queue expand — cancelled if double-click follows within 300ms."""
        self._tree_click_timer.stop()
        self._tree_pending_index = index
        self._tree_click_timer.start()

    def _do_tree_expand(self):
        """Fires 300ms after single click if no double-click came."""
        if self._tree_pending_index is not None:
            idx = self._tree_pending_index
            self.tree_view.setExpanded(idx, not self.tree_view.isExpanded(idx))
        self._tree_pending_index = None

    def _on_folder_double_clicked(self, index):
        """Double click: cancel pending expand and scan."""
        self._tree_click_timer.stop()
        self._tree_pending_index = None
        path = self.fs_model.filePath(index)
        if path:
            self._load_folder(path)

    def _load_folder(self, path):
        self._current_folder = path
        self._save_config({'last_folder': path})
        self.folder_label.setText(path)
        self.discogs_btn.setEnabled(False)
        self.rename_btn.setEnabled(False)
        self.quick_rename_btn.setEnabled(False)
        self.autonumber_btn.setEnabled(False)

        # Each scan gets a unique ID — stale results from old scans are dropped
        self._scan_id = getattr(self, '_scan_id', 0) + 1
        current_id = self._scan_id

        # Cancel any running scan
        if hasattr(self, '_scan_thread') and self._scan_thread.isRunning():
            self._scan_thread.cancel()
            self._scan_thread.wait(300)

        # Clear table
        self._files = []
        self.file_table.setSortingEnabled(False)
        self.file_table.setRowCount(0)
        self.cancel_scan_btn.setVisible(True)
        self.status_bar.showMessage(f"Scanne {path} …")

        self._scan_thread = FolderScanThread(path)
        self._scan_thread.progress.connect(self._on_scan_progress)
        self._scan_thread.scan_done.connect(
            lambda results, sid=current_id: self._on_scan_done(results, sid)
        )
        self._scan_thread.start()

    def _cancel_scan(self):
        if hasattr(self, '_scan_thread'):
            self._scan_thread.cancel()
        self._scan_id = getattr(self, '_scan_id', 0) + 1  # invalidate pending result
        self.cancel_scan_btn.setVisible(False)
        self.status_bar.showMessage("Scan abgebrochen")

    def _on_scan_progress(self, count, filename):
        self.status_bar.showMessage(f"Lese … {count} Dateien  —  {filename}")

    def _on_scan_done(self, results, scan_id):
        if scan_id != self._scan_id:
            return  # stale result from a cancelled/replaced scan — discard
        self.cancel_scan_btn.setVisible(False)
        self._populate_file_table(results)
        self._update_folder_cover()  # folder.jpg — independent of selection

    def _populate_file_table(self, raw):
        self._files = []
        self.file_table.setSortingEnabled(False)
        self.file_table.setRowCount(len(raw))

        for i, (path_str, tags) in enumerate(raw):
            mp3_path = Path(path_str)
            self._files.append((path_str, tags))

            has_cover = tags['cover'] is not None
            cover_item = QTableWidgetItem('♪' if has_cover else '')
            cover_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if has_cover:
                cover_item.setForeground(QColor('#a6e3a1'))
            self.file_table.setItem(i, 0, cover_item)

            track = tags['tracknumber'].split('/')[0]
            self.file_table.setItem(i, 1, QTableWidgetItem(track.zfill(2) if track else ''))

            fname_item = QTableWidgetItem(mp3_path.name)
            fname_item.setData(Qt.ItemDataRole.UserRole, path_str)
            self.file_table.setItem(i, 2, fname_item)

            self.file_table.setItem(i, 3, QTableWidgetItem(tags['artist']))
            self.file_table.setItem(i, 4, QTableWidgetItem(tags['album']))
            self.file_table.setItem(i, 5, QTableWidgetItem(tags['title']))
            self.file_table.setItem(i, 6, QTableWidgetItem(tags['year']))
            self.file_table.setItem(i, 7, QTableWidgetItem(tags['genre']))
            self.file_table.setItem(i, 8, QTableWidgetItem(format_duration(tags['duration'])))

        self.file_table.setSortingEnabled(True)
        self._select_all()
        self.status_bar.showMessage(
            f"{len(raw)} MP3-Datei(en) geladen  —  {self._current_folder}"
        )

    def _select_all(self):
        self.file_table.selectAll()
        self._on_selection_changed()

    def _deselect_all(self):
        self.file_table.clearSelection()
        self._on_selection_changed()

    def _on_selection_changed(self):
        rows = self.file_table.selectionModel().selectedRows()
        selected = len(rows)
        has_sel = selected > 0
        self.discogs_btn.setEnabled(has_sel)
        self.rename_btn.setEnabled(has_sel)
        self.quick_rename_btn.setEnabled(has_sel)
        self.autonumber_btn.setEnabled(has_sel)
        if self._files:
            self.status_bar.showMessage(
                f"{selected} von {len(self._files)} Datei(en) markiert  —  {self._current_folder}"
            )
        # Show cover of the last-clicked (or first selected) file
        self._update_cover_preview(rows)

    def _set_cover_label(self, label, data, size=124):
        if data:
            pix = image_data_to_pixmap(data, size)
            if pix:
                label.setPixmap(pix)
                label.setText("")
                return True
            else:
                label.setPixmap(QPixmap())
                label.setText("Fehler")
        else:
            label.setPixmap(QPixmap())
            label.setText("–")
        return False

    def _update_folder_cover(self):
        """Load and show folder.jpg — called once after folder scan completes."""
        self._current_folder_jpg = None
        folder_jpg_data = None
        if self._current_folder:
            fjpg = Path(self._current_folder) / 'folder.jpg'
            if fjpg.exists():
                try:
                    folder_jpg_data = fjpg.read_bytes()
                    self._current_folder_jpg = folder_jpg_data
                except Exception:
                    pass
        self._set_cover_label(self.folder_cover, folder_jpg_data)
        self._refresh_folder_btn()

    def _refresh_folder_btn(self):
        """Show 'folder.jpg → Tag' button when folder.jpg exists but current tag cover is missing."""
        has_folder_jpg = self._current_folder_jpg is not None
        # Check first selected file (or first file if none selected)
        rows = self.file_table.selectionModel().selectedRows()
        tag_cover = None
        source_rows = rows if rows else []
        if not source_rows and self._files:
            # No selection — check first file
            for r in range(self.file_table.rowCount()):
                p = self.file_table.item(r, 2)
                if p:
                    path = p.data(Qt.ItemDataRole.UserRole)
                    tag_cover = {p: t for p, t in self._files}.get(path, {}).get('cover')
                    break
        elif source_rows:
            path = self.file_table.item(source_rows[0].row(), 2).data(Qt.ItemDataRole.UserRole)
            tag_cover = {p: t for p, t in self._files}.get(path, {}).get('cover')
        self.folder_to_tag_btn.setVisible(has_folder_jpg and tag_cover is None)

    def _update_cover_preview(self, rows):
        """Update tag cover display based on current selection."""
        tag_cover_data = None
        if rows:
            path = self.file_table.item(rows[0].row(), 2).data(Qt.ItemDataRole.UserRole)
            if path:
                tag_cover_data = {p: t for p, t in self._files}.get(path, {}).get('cover')
        elif self._files:
            # Nothing selected — show cover from first file
            for r in range(min(self.file_table.rowCount(), 1)):
                p = self.file_table.item(r, 2)
                if p:
                    path = p.data(Qt.ItemDataRole.UserRole)
                    tag_cover_data = {p: t for p, t in self._files}.get(path, {}).get('cover')

        if tag_cover_data:
            self._set_cover_label(self.cover_preview, tag_cover_data)
            try:
                orig = Image.open(BytesIO(tag_cover_data))
                self.cover_info_label.setText(
                    f"Tag: {orig.width}×{orig.height}px  {len(tag_cover_data)//1024}KB"
                )
            except Exception:
                self.cover_info_label.setText("")
        else:
            self._set_cover_label(self.cover_preview, None)
            self.cover_info_label.setText("")

        self._refresh_folder_btn()

    def _get_selected_files(self):
        # Use path stored in UserRole (col 2) — safe even when table is sorted
        path_to_tags = {path: tags for path, tags in self._files}
        result = []
        for idx in self.file_table.selectionModel().selectedRows():
            path = self.file_table.item(idx.row(), 2).data(Qt.ItemDataRole.UserRole)
            if path and path in path_to_tags:
                result.append((path, path_to_tags[path]))
        return result

    def _get_prefill(self):
        selected = self._get_selected_files()
        if not selected:
            return {}
        _, tags = selected[0]
        return {
            'artist': tags.get('artist', ''),
            'album': tags.get('album', ''),
            'year': tags.get('year', ''),
        }

    def _open_discogs(self):
        selected = self._get_selected_files()
        if not selected:
            return
        dlg = DiscogsDialog(
            self._get_prefill(), selected,
            self._discogs_token,
            cfg_save=self._save_config,
            cfg_load=self._load_config,
            parent=self
        )
        dlg.exec()

    def _apply_tags_from_trackmatch(self, result):
        """Handle [(path, tag_dict, cover_bytes), ...] from TrackMatchDialog."""
        errors = []
        cover_written = False
        for path, tag_data, cover_bytes in result:
            cover = cover_bytes if cover_bytes else None
            ok = write_mp3_tags(path, tag_data, cover)
            if not ok:
                errors.append(path)
            if cover and not cover_written and self._current_folder:
                try:
                    (Path(self._current_folder) / 'folder.jpg').write_bytes(cover)
                    cover_written = True
                except Exception as e:
                    errors.append(f"folder.jpg: {e}")
        if self._current_folder:
            self._load_folder(self._current_folder)
        msg = f"{len(result)} Datei(en) getaggt."
        if errors:
            msg += f"  {len(errors)} Fehler."
        self.status_bar.showMessage(msg)

    def _apply_tags_to_selected(self, tag_data, cover_bytes):
        selected = self._get_selected_files()
        use_tracknumber = tag_data.pop('use_tracknumber', False)
        tracklist = tag_data.pop('tracklist', []) if use_tracknumber else []
        cover = cover_bytes if cover_bytes else None
        errors = []

        for i, (path, _) in enumerate(selected):
            file_tags = dict(tag_data)
            if use_tracknumber and tracklist:
                if i < len(tracklist):
                    t = tracklist[i]
                    pos = t['position'].lstrip('0') or str(i + 1)
                    file_tags['tracknumber'] = f"{pos}/{len(tracklist)}"
                    if not file_tags.get('title'):
                        file_tags['title'] = t['title']

            ok = write_mp3_tags(path, file_tags, cover)
            if not ok:
                errors.append(path)

        # Write folder.jpg
        if cover and self._current_folder:
            try:
                folder_jpg = Path(self._current_folder) / 'folder.jpg'
                folder_jpg.write_bytes(cover)
            except Exception as e:
                errors.append(f"folder.jpg: {e}")

        # Reload folder
        if self._current_folder:
            self._load_folder(self._current_folder)

        msg = f"{len(selected)} Datei(en) getaggt."
        if errors:
            msg += f"\n{len(errors)} Fehler."
        self.status_bar.showMessage(msg)

    def _open_rename(self):
        selected = self._get_selected_files()
        if not selected:
            return
        fresh = []
        for path, _ in selected:
            tags = load_mp3_tags(path)
            fresh.append((path, tags))
        masks = self._load_masks()
        last_mask = self._load_config().get('last_rename_mask', '')
        dlg = RenameDialog(fresh, masks=masks, last_mask=last_mask, parent=self)
        dlg.masks_changed.connect(self._save_masks)
        dlg.exec()
        if self._current_folder:
            self._load_folder(self._current_folder)

    def _write_folder_jpg_to_tags(self):
        if not self._current_folder_jpg:
            return
        try:
            cover_bytes = resize_cover(self._current_folder_jpg, 600)
        except Exception:
            cover_bytes = self._current_folder_jpg
        selected = self._get_selected_files()
        if not selected:
            selected = self._files
        errors = []
        for path, _ in selected:
            ok = write_mp3_tags(path, {}, cover_bytes)
            if not ok:
                errors.append(path)
        if self._current_folder:
            self._load_folder(self._current_folder)
        msg = f"{len(selected)} Datei(en) mit folder.jpg getaggt."
        if errors:
            msg += f"  {len(errors)} Fehler."
        self.status_bar.showMessage(msg)

    def _open_cover_scan(self):
        # Use currently selected tree folder, fall back to last scanned folder
        scan_root = None
        idx = self.tree_view.currentIndex()
        if idx.isValid():
            scan_root = self.fs_model.filePath(idx)
        if not scan_root:
            scan_root = self._current_folder
        if not scan_root:
            return
        dlg = CoverScanDialog(scan_root, parent=self)
        dlg.load_folder.connect(self._load_folder)
        dlg.exec()

    def _update_quick_rename_tooltip(self):
        mask = self._load_config().get('last_rename_mask', '')
        if not mask:
            masks = self._load_masks()
            mask = masks[0] if masks else ''
        self.quick_rename_btn.setToolTip(f"Schnell-Umbenennen\nMaske: {mask}")

    def _quick_rename(self):
        """Rename selected files using the last saved mask without opening a dialog."""
        selected = self._get_selected_files()
        if not selected:
            return
        mask = self._load_config().get('last_rename_mask', '')
        if not mask:
            masks = self._load_masks()
            mask = masks[0] if masks else '%6-%2'
        # Reload fresh tags and build a temporary RenameDialog to reuse its logic
        fresh = [(p, load_mp3_tags(p)) for p, _ in selected]
        dlg = RenameDialog(fresh, masks=self._load_masks(),
                           last_mask=mask, parent=self)
        dlg.mask_input.setCurrentText(mask)
        dlg._do_rename()  # runs rename and calls self.accept()

    def _autonumber_tracks(self):
        """Write sequential track numbers into tags of selected files."""
        selected = self._get_selected_files()
        if not selected:
            return
        total = len(selected)
        if total < 10:
            width = 1
        elif total < 100:
            width = 2
        else:
            width = 3
        errors = []
        for i, (path, _) in enumerate(selected, 1):
            nr = str(i).zfill(width)
            ok = write_mp3_tags(path, {'tracknumber': f"{nr}/{total}"})
            if not ok:
                errors.append(path)
        if self._current_folder:
            self._load_folder(self._current_folder)
        msg = f"# {total} Dateien nummeriert (1–{total}, {width}-stellig)."
        if errors:
            msg += f"  {len(errors)} Fehler."
        self.status_bar.showMessage(msg)

    def _open_about(self):
        import webbrowser
        dlg = QDialog(self)
        dlg.setWindowTitle("Über TagMeGently")
        dlg.setFixedSize(340, 260)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("TagMeGently")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #89b4fa;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        for text, style in [
            ("Version: 1.1", "color: #a6adc8; font-size: 12px;"),
            ("© PolzeSoft 2026", "color: #6c7086; font-size: 12px;"),
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet(style)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)

        layout.addSpacing(6)

        web_btn = QPushButton("https://polze.net")
        web_btn.setStyleSheet("QPushButton { background:transparent; color:#89b4fa; border:none; font-size:12px; text-decoration:underline; } QPushButton:hover { color:#b4d0ff; }")
        web_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        web_btn.clicked.connect(lambda: webbrowser.open("https://polze.net"))
        web_btn.setAlignment = lambda *a: None  # suppress warning
        layout.addWidget(web_btn)

        mail_btn = QPushButton("tagmegently@polze.net")
        mail_btn.setStyleSheet("QPushButton { background:transparent; color:#89b4fa; border:none; font-size:12px; text-decoration:underline; } QPushButton:hover { color:#b4d0ff; }")
        mail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mail_btn.clicked.connect(lambda: webbrowser.open("mailto:tagmegently@polze.net"))
        layout.addWidget(mail_btn)

        layout.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)

        dlg.exec()

    def _open_settings(self):
        dlg = SettingsDialog(self._discogs_token, parent=self)
        if dlg.exec():
            self._discogs_token = dlg.get_token()
            self._save_token(self._discogs_token)


def _make_icon():
    """Generate app icon programmatically via Pillow."""
    try:
        from PIL import ImageDraw, ImageFont
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # Rounded background
        d.rounded_rectangle([0, 0, 63, 63], radius=14, fill='#1e1e2e')
        # Tag shape
        d.polygon([(6,10),(42,10),(58,32),(42,54),(6,54)], outline='#cba6f7', width=3)
        d.ellipse([12,26,22,36], fill='#cba6f7')
        # Music note
        d.text((34, 18), '♪', fill='#89b4fa', font=ImageFont.load_default(size=22))
        buf = BytesIO()
        img.save(buf, format='PNG')
        pix = QPixmap()
        pix.loadFromData(buf.getvalue())
        return QIcon(pix)
    except Exception:
        return QIcon()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')        # must come before setStyleSheet
    app.setStyleSheet(DARK_STYLE)
    window = MainWindow()
    window.setWindowIcon(_make_icon())
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
