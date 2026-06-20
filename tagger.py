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
    QMenu, QTextEdit
)
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QDir, QSortFilterProxyModel,
    QModelIndex, QTimer
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QImage, QAction, QFont, QColor, QPalette
)

from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TDRC, TCON, TRCK,
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
    letter-spacing: 0.5px;
    text-transform: uppercase;
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
    letter-spacing: 0.3px;
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
    background-color: #f38ba820;
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
    letter-spacing: 0.5px;
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
    letter-spacing: 1px;
    text-transform: uppercase;
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
            params = {'per_page': 25}
            if self.album:
                params['type'] = 'release'
                params['release_title'] = self.album
                if self.artist:
                    params['artist'] = self.artist
            else:
                params['type'] = 'release'
                if self.artist:
                    params['q'] = self.artist
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

            tracklist = []
            for t in data.get('tracklist', []):
                if t.get('type_', 'track') == 'track':
                    tracklist.append({
                        'position': t.get('position', ''),
                        'title': t.get('title', ''),
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


class DiscogsDialog(QDialog):
    tags_accepted = pyqtSignal(dict, bytes)  # tag_data, cover_data

    def __init__(self, prefill, file_count, discogs_token=None, cfg_save=None, cfg_load=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Discogs Suche")
        self.setMinimumSize(1000, 650)
        self.discogs_token = discogs_token
        self.current_detail = None
        self.cover_data = None
        self._cfg_save = cfg_save  # callable(dict)
        self._cfg_load = cfg_load  # callable() -> dict
        self._build_ui(prefill, file_count)

    def _build_ui(self, prefill, file_count):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Search bar
        search_group = QGroupBox("Suche")
        sg_layout = QGridLayout(search_group)

        sg_layout.addWidget(QLabel("Künstler:"), 0, 0)
        self.artist_input = QLineEdit(prefill.get('artist', ''))
        sg_layout.addWidget(self.artist_input, 0, 1)

        sg_layout.addWidget(QLabel("Album:"), 0, 2)
        self.album_input = QLineEdit(prefill.get('album', ''))
        sg_layout.addWidget(self.album_input, 0, 3)

        sg_layout.addWidget(QLabel("Jahr:"), 0, 4)
        self.year_input = QLineEdit(prefill.get('year', ''))
        self.year_input.setMaximumWidth(80)
        sg_layout.addWidget(self.year_input, 0, 5)

        self.search_btn = QPushButton("Suchen")
        self.search_btn.clicked.connect(self._do_search)
        sg_layout.addWidget(self.search_btn, 0, 6)

        layout.addWidget(search_group)

        # Results + Detail splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Results table
        results_widget = QWidget()
        rl = QVBoxLayout(results_widget)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("Suchergebnisse:"))
        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["Künstler / Album", "Jahr", "Label", "Format", "Land"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setShowGrid(False)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.verticalHeader().setDefaultSectionSize(22)
        self.results_table.itemSelectionChanged.connect(self._on_result_selected)
        rl.addWidget(self.results_table)
        splitter.addWidget(results_widget)

        # Detail panel
        detail_widget = QWidget()
        dl = QVBoxLayout(detail_widget)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.addWidget(QLabel("Album Details:"))

        # Cover
        self.cover_label = QLabel("Kein Cover")
        self.cover_label.setObjectName("cover")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setFixedSize(200, 200)
        dl.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        cover_info_layout = QHBoxLayout()
        self.cover_size_label = QLabel("")
        self.cover_size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_info_layout.addWidget(self.cover_size_label)
        dl.addLayout(cover_info_layout)

        # Checkboxes for what to apply — restore saved state
        saved = self._cfg_load() if self._cfg_load else {}
        cb_state = saved.get('discogs_checkboxes', {})

        self.cb_artist = QCheckBox("Künstler:")
        self.cb_artist.setChecked(cb_state.get('artist', True))
        self.detail_artist = QLineEdit()
        self.cb_album = QCheckBox("Album:")
        self.cb_album.setChecked(cb_state.get('album', True))
        self.detail_album = QLineEdit()
        self.cb_year = QCheckBox("Jahr:")
        self.cb_year.setChecked(cb_state.get('year', True))
        self.detail_year = QLineEdit()
        self.cb_genre = QCheckBox("Genre:")
        self.cb_genre.setChecked(cb_state.get('genre', True))
        self.detail_genre = QLineEdit()
        self.cb_label = QCheckBox("Label:")
        self.cb_label.setChecked(cb_state.get('label', False))
        self.detail_label = QLineEdit()
        self.cb_tracknumber = QCheckBox("Track-Nr.")
        self.cb_tracknumber.setChecked(cb_state.get('tracknumber', True))
        self.cb_cover = QCheckBox("Cover (→ max 600×600)")
        self.cb_cover.setChecked(cb_state.get('cover', True))

        fields = [
            (self.cb_artist, self.detail_artist),
            (self.cb_album, self.detail_album),
            (self.cb_year, self.detail_year),
            (self.cb_genre, self.detail_genre),
            (self.cb_label, self.detail_label),
        ]
        for cb, field in fields:
            row = QHBoxLayout()
            cb.setFixedWidth(110)
            row.addWidget(cb)
            row.addWidget(field)
            dl.addLayout(row)

        dl.addWidget(self.cb_tracknumber)
        dl.addWidget(self.cb_cover)

        # Tracklist preview
        dl.addWidget(QLabel("Trackliste:"))
        self.tracklist_widget = QTableWidget(0, 3)
        self.tracklist_widget.setHorizontalHeaderLabels(["#", "Titel", "Zeit"])
        self.tracklist_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tracklist_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tracklist_widget.setMaximumHeight(180)
        dl.addWidget(self.tracklist_widget)
        dl.addStretch()

        splitter.addWidget(detail_widget)
        splitter.setSizes([550, 450])
        layout.addWidget(splitter)

        # Status + buttons
        self.status_label = QLabel(f"Markierte Dateien: {file_count}")
        self.status_label.setStyleSheet("color: #a6adc8;")
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        self.apply_btn = QPushButton("Tags schreiben")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply_tags)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.apply_btn)
        layout.addLayout(btn_layout)

    def _do_search(self):
        self.search_btn.setEnabled(False)
        self.status_label.setText("Suche läuft...")
        self.results_table.setRowCount(0)
        self.apply_btn.setEnabled(False)

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
        self.results_table.setRowCount(len(results))
        bold_font = QFont()
        bold_font.setBold(True)
        for i, r in enumerate(results):
            is_master = r.get('is_master', False)
            title_text = ('★ ' if is_master else '') + r['title']
            items = [
                QTableWidgetItem(title_text),
                QTableWidgetItem(str(r['year'])),
                QTableWidgetItem(r['label']),
                QTableWidgetItem(r['format']),
                QTableWidgetItem(r['country']),
            ]
            for item in items:
                if is_master:
                    item.setFont(bold_font)
                    item.setForeground(QColor('#f9e2af'))
                self.results_table.setItem(i, items.index(item), item)
        self.status_label.setText(f"{len(results)} Ergebnis(se) gefunden")
        if results:
            self.results_table.selectRow(0)

    def _on_result_selected(self):
        rows = self.results_table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if idx >= len(self._results if hasattr(self, '_results') else []):
            return
        result = self._results[idx]
        self.status_label.setText("Lade Details...")
        self.apply_btn.setEnabled(False)
        self._detail_thread = DiscogsDetailThread(
            result['resource_url'], result['cover_url'], self.discogs_token
        )
        self._detail_thread.detail_ready.connect(self._on_detail)
        self._detail_thread.error.connect(self._on_error)
        self._detail_thread.start()

    def _on_detail(self, detail):
        self.current_detail = detail
        self.detail_artist.setText(detail['artist'])
        self.detail_album.setText(detail['album'])
        self.detail_year.setText(detail['year'])
        self.detail_genre.setText(detail['genre'] or detail['style'])
        self.detail_label.setText(detail['label'])

        # Tracklist
        tracks = detail['tracklist']
        self.tracklist_widget.setRowCount(len(tracks))
        for i, t in enumerate(tracks):
            self.tracklist_widget.setItem(i, 0, QTableWidgetItem(t['position']))
            self.tracklist_widget.setItem(i, 1, QTableWidgetItem(t['title']))
            self.tracklist_widget.setItem(i, 2, QTableWidgetItem(t['duration']))

        # Cover
        self.cover_data = None
        if detail['cover_data']:
            try:
                img_data = detail['cover_data']
                pix = image_data_to_pixmap(img_data, 200)
                if pix:
                    self.cover_label.setPixmap(pix)
                    self.cover_label.setText("")
                    orig_img = Image.open(BytesIO(img_data))
                    self.cover_size_label.setText(
                        f"Cover: {orig_img.width}×{orig_img.height} px"
                    )
                    self.cover_data = img_data
                else:
                    self.cover_label.setText("Cover Fehler")
            except Exception:
                self.cover_label.setText("Cover Fehler")
        else:
            self.cover_label.setText("Kein Cover")
            self.cover_label.setPixmap(QPixmap())
            self.cover_size_label.setText("")

        self.apply_btn.setEnabled(True)
        # Calculate total duration from tracklist
        total_secs = 0
        for t in tracks:
            dur = t.get('duration', '')
            if dur and ':' in dur:
                parts = dur.split(':')
                try:
                    if len(parts) == 2:
                        total_secs += int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        total_secs += int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                except ValueError:
                    pass
        duration_str = format_duration(total_secs) if total_secs else '–'
        self.status_label.setText(
            f"Details geladen — {len(tracks)} Tracks — Gesamtzeit: {duration_str}"
        )

    def _on_error(self, msg):
        self.search_btn.setEnabled(True)
        self.status_label.setText(f"Fehler: {msg}")

    def _apply_tags(self):
        # Persist checkbox states
        if self._cfg_save:
            self._cfg_save({'discogs_checkboxes': {
                'artist':      self.cb_artist.isChecked(),
                'album':       self.cb_album.isChecked(),
                'year':        self.cb_year.isChecked(),
                'genre':       self.cb_genre.isChecked(),
                'label':       self.cb_label.isChecked(),
                'tracknumber': self.cb_tracknumber.isChecked(),
                'cover':       self.cb_cover.isChecked(),
            }})

        tag_data = {}
        if self.cb_artist.isChecked():
            tag_data['artist'] = self.detail_artist.text()
        if self.cb_album.isChecked():
            tag_data['album'] = self.detail_album.text()
        if self.cb_year.isChecked():
            tag_data['year'] = self.detail_year.text()
        if self.cb_genre.isChecked():
            tag_data['genre'] = self.detail_genre.text()
        if self.cb_label.isChecked():
            tag_data['label'] = self.detail_label.text()
        if self.cb_tracknumber.isChecked():
            tag_data['use_tracknumber'] = True
            tag_data['tracklist'] = (
                self.current_detail['tracklist'] if self.current_detail else []
            )

        cover_bytes = b''
        if self.cb_cover.isChecked() and self.cover_data:
            try:
                cover_bytes = resize_cover(self.cover_data, 600)
            except Exception as e:
                print(f"Cover resize error: {e}")

        self.tags_accepted.emit(tag_data, cover_bytes)
        self.accept()


class RenameDialog(QDialog):
    masks_changed = pyqtSignal(list)

    def __init__(self, files, masks=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dateien umbenennen")
        self.setMinimumSize(750, 520)
        self.files = files
        self._masks = masks or ["%6-%2", "%1 - %6 - %2", "%1\\[%4] %3\\%6 - %2"]
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
        if self._masks:
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
        # Clean illegal chars (except path separator)
        parts = result.split('\\')
        clean_parts = []
        for p in parts:
            p = re.sub(r'[<>:"/|?*]', '', p).strip()
            clean_parts.append(p)
        result = '\\'.join(clean_parts)
        return result

    def _apply_case(self, s):
        case = self.case_combo.currentIndex()
        if case == 1:
            return s.lower()
        elif case == 2:
            return s.upper()
        elif case == 3:
            return s.title()
        return s

    def _update_preview(self):
        mask = self.mask_input.currentText()
        self.preview_table.setRowCount(len(self.files))
        self._new_names = []
        for i, (path, tags) in enumerate(self.files):
            old_name = Path(path).name
            new_base = self._apply_mask(mask, tags)
            new_base = self._apply_case(new_base)
            # Handle sub-folders in mask
            if '\\' in new_base:
                parts = new_base.rsplit('\\', 1)
                new_name = parts[-1] + '.mp3'
            else:
                new_name = new_base + '.mp3'
            self._new_names.append((path, new_base, new_name))
            self.preview_table.setItem(i, 0, QTableWidgetItem(old_name))
            color = '#a6e3a1' if old_name != new_name else '#6c7086'
            item = QTableWidgetItem(new_name)
            item.setForeground(QColor(color))
            self.preview_table.setItem(i, 1, item)

    def _do_rename(self):
        mask = self.mask_input.currentText()
        errors = []
        renamed = 0
        for path, tags in self.files:
            new_base = self._apply_mask(mask, tags)
            new_base = self._apply_case(new_base)
            src = Path(path)
            if '\\' in new_base:
                sub, fname = new_base.rsplit('\\', 1)
                dest_dir = src.parent / sub
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / (fname + '.mp3')
            else:
                dest = src.parent / (new_base + '.mp3')
            if src == dest:
                continue
            try:
                src.rename(dest)
                renamed += 1
            except Exception as e:
                errors.append(f"{src.name}: {e}")

        msg = f"{renamed} Datei(en) umbenannt."
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TagMeGently")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)
        self._current_folder = None
        self._files = []  # list of (path, tags)
        self._discogs_token = self._load_token()
        self._build_ui()
        self._build_menu()
        QTimer.singleShot(200, self._restore_last_folder)

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
        p = Path(last) if last else None
        # Skip root drives (e.g. X:\) — only restore real sub-folders
        if not p or not p.is_dir() or p == p.parent:
            return
        idx = self.fs_model.index(last)
        if idx.isValid():
            parent = idx.parent()
            while parent.isValid():
                self.tree_view.expand(parent)
                parent = parent.parent()
            self.tree_view.expand(idx)
            self.tree_view.scrollTo(idx)
            self.tree_view.setCurrentIndex(idx)
            self._load_folder(last)

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

        self.select_all_btn = QPushButton("Alle")
        self.select_all_btn.setStyleSheet(secondary_ss)
        self.select_all_btn.clicked.connect(self._select_all)

        self.deselect_btn = QPushButton("Keine")
        self.deselect_btn.setStyleSheet(secondary_ss)
        self.deselect_btn.clicked.connect(self._deselect_all)

        self.cover_scan_btn = QPushButton("🔍  Cover-Scan")
        self.cover_scan_btn.setEnabled(False)
        self.cover_scan_btn.setStyleSheet(secondary_ss)
        self.cover_scan_btn.setEnabled(False)
        self.cover_scan_btn.setToolTip("Scannt alle Unterordner auf kaputte/fehlende Cover")
        self.cover_scan_btn.clicked.connect(self._open_cover_scan)

        toolbar_layout.addWidget(self.discogs_btn)
        toolbar_layout.addWidget(self.rename_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self.select_all_btn)
        toolbar_layout.addWidget(self.deselect_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self.cover_scan_btn)
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

        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath('')
        self.fs_model.setFilter(QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot)

        self.tree_view = QTreeView()
        self.tree_view.setModel(self.fs_model)
        self.tree_view.setRootIndex(self.fs_model.index(''))
        for col in range(1, 4):
            self.tree_view.hideColumn(col)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.clicked.connect(self._on_folder_clicked)
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(16)
        # Base64 SVG arrows — the only reliable way to show branch indicators in Qt stylesheets
        arrow_right = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iMTAiIHZpZXdCb3g9IjAgMCAxMCAxMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cG9seWdvbiBwb2ludHM9IjIsMSA4LDUgMiw5IiBmaWxsPSIjNTg1YjcwIi8+PC9zdmc+"
        arrow_down  = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iMTAiIHZpZXdCb3g9IjAgMCAxMCAxMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cG9seWdvbiBwb2ludHM9IjEsMiA5LDIgNSw4IiBmaWxsPSIjODllNGZhIi8+PC9zdmc+"
        self.tree_view.setStyleSheet(f"""
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {{
                image: url("{arrow_right}");
            }}
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings {{
                image: url("{arrow_down}");
            }}
        """)
        tree_layout.addWidget(self.tree_view)

        # Cover preview at bottom of left panel
        self.cover_preview = QLabel("Kein Cover")
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_preview.setFixedHeight(130)
        self.cover_preview.setStyleSheet(
            "background-color: #24273a; border: 1px solid #313244; "
            "border-radius: 6px; color: #585b70; font-size: 11px;"
        )
        tree_layout.addWidget(self.cover_preview)

        self.cover_info_label = QLabel("")
        self.cover_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_info_label.setStyleSheet("color: #6c7086; font-size: 10px;")
        self.cover_info_label.setFixedHeight(16)
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

    def _on_folder_clicked(self, index):
        path = self.fs_model.filePath(index)
        self._load_folder(path)

    def _load_folder(self, path):
        self._current_folder = path
        self._save_config({'last_folder': path})
        self.folder_label.setText(path)
        self.cover_scan_btn.setEnabled(True)
        folder = Path(path)
        # Load tags first so we can sort by album → track naturally
        raw = [(p, load_mp3_tags(str(p))) for p in folder.rglob('*.mp3')]
        raw.sort(key=lambda x: (
            x[1].get('album', '').lower(),
            natural_sort_key(x[0])
        ))
        mp3_files = [p for p, _ in raw]
        prefetched = {str(p): t for p, t in raw}

        self._files = []
        self.file_table.setSortingEnabled(False)
        self.file_table.setRowCount(0)
        self.file_table.setRowCount(len(mp3_files))

        for i, mp3_path in enumerate(mp3_files):
            tags = prefetched[str(mp3_path)]
            self._files.append((str(mp3_path), tags))

            # Col 0: cover indicator
            has_cover = tags['cover'] is not None
            cover_item = QTableWidgetItem('♪' if has_cover else '')
            cover_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if has_cover:
                cover_item.setForeground(QColor('#a6e3a1'))
            self.file_table.setItem(i, 0, cover_item)

            track = tags['tracknumber'].split('/')[0]
            self.file_table.setItem(i, 1, QTableWidgetItem(track.zfill(2) if track else ''))

            # Col 2: filename — store full path in UserRole for sort-safe lookup
            fname_item = QTableWidgetItem(mp3_path.name)
            fname_item.setData(Qt.ItemDataRole.UserRole, str(mp3_path))
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
            f"{len(mp3_files)} MP3-Datei(en) geladen  —  {path}"
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
        if self._files:
            self.status_bar.showMessage(
                f"{selected} von {len(self._files)} Datei(en) markiert  —  {self._current_folder}"
            )
        # Show cover of the last-clicked (or first selected) file
        self._update_cover_preview(rows)

    def _update_cover_preview(self, rows):
        if not rows:
            self.cover_preview.setText("Kein Cover")
            self.cover_preview.setPixmap(QPixmap())
            self.cover_info_label.setText("")
            return
        path = self.file_table.item(rows[0].row(), 2).data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        path_to_tags = {p: t for p, t in self._files}
        tags = path_to_tags.get(path, {})
        cover_data = tags.get('cover')
        if cover_data:
            pix = image_data_to_pixmap(cover_data, 178)
            if pix:
                self.cover_preview.setPixmap(pix)
                self.cover_preview.setText("")
                try:
                    orig = Image.open(BytesIO(cover_data))
                    self.cover_info_label.setText(
                        f"{orig.width}×{orig.height} px  {len(cover_data)//1024} KB"
                    )
                except Exception:
                    self.cover_info_label.setText("")
            else:
                self.cover_preview.setText("Cover Fehler")
                self.cover_info_label.setText("")
        else:
            self.cover_preview.setText("Kein Cover")
            self.cover_preview.setPixmap(QPixmap())
            self.cover_info_label.setText("")

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
            self._get_prefill(), len(selected),
            self._discogs_token,
            cfg_save=self._save_config,
            cfg_load=self._load_config,
            parent=self
        )
        dlg.tags_accepted.connect(self._apply_tags_to_selected)
        dlg.exec()

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
        dlg = RenameDialog(fresh, masks=masks, parent=self)
        dlg.masks_changed.connect(self._save_masks)
        dlg.exec()
        if self._current_folder:
            self._load_folder(self._current_folder)

    def _open_cover_scan(self):
        if not self._current_folder:
            return
        dlg = CoverScanDialog(self._current_folder, parent=self)
        dlg.load_folder.connect(self._load_folder)
        dlg.exec()

    def _open_settings(self):
        dlg = SettingsDialog(self._discogs_token, parent=self)
        if dlg.exec():
            self._discogs_token = dlg.get_token()
            self._save_token(self._discogs_token)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
