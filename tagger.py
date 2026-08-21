"""
Adolar Taggster - MP3 Tagger
Modern MP3 tagging tool with Discogs integration
"""
import sys
import os
import re
import json
import getpass
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QTreeView,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QDialog, QDialogButtonBox,
    QCheckBox, QComboBox, QHeaderView, QToolBar,
    QStatusBar, QFrame, QScrollArea, QMessageBox, QProgressBar,
    QGroupBox, QGridLayout, QSizePolicy, QAbstractItemView,
    QMenu, QTextEdit, QStyledItemDelegate, QFileDialog
)
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QDir, QSortFilterProxyModel,
    QModelIndex, QTimer, QStandardPaths, QObject
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtGui import (
    QIcon, QPixmap, QImage, QAction, QFont, QColor, QPalette
)
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QTreeView

from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, ID3NoHeaderError, TIT2, TPE1, TPE2, TALB, TDRC, TDOR, TCON, TRCK,
    APIC, TPOS, TPUB, COMM
)
from mutagen.id3._util import ID3NoHeaderError
from PIL import Image


APP_NAME = "Adolar Taggster"
EXPLORER_VERB_KEY = r"Software\Classes\Directory\shell\AdolarTaggster"


def _launch_command():
    """Command registered with Explorer for the current app location."""
    if getattr(sys, 'frozen', False):
        launcher = f'"{Path(sys.executable).resolve()}"'
    else:
        launcher = f'"{Path(sys.executable).resolve()}" "{Path(__file__).resolve()}"'
    return f'{launcher} --folder "%1"'


def _shell_icon_path():
    """Create a stable icon file for Explorer's context menu."""
    base = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'AdolarTaggster'
    icon_path = base / 'AdolarTaggster.ico'
    try:
        base.mkdir(parents=True, exist_ok=True)
        _create_icon_image(256).save(
            icon_path, format='ICO', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
        return str(icon_path)
    except Exception:
        # Explorer can still extract the embedded/default icon from the EXE.
        return f'{Path(sys.executable).resolve()},0'


def _explorer_integration_status():
    """Return 'installed', 'outdated', 'missing', or 'unsupported'."""
    if sys.platform != 'win32':
        return 'unsupported'
    try:
        import winreg
        command_key = EXPLORER_VERB_KEY + r'\command'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, command_key) as key:
            command, _ = winreg.QueryValueEx(key, '')
        return 'installed' if command == _launch_command() else 'outdated'
    except FileNotFoundError:
        return 'missing'
    except OSError:
        return 'missing'


def _install_explorer_integration():
    if sys.platform != 'win32':
        raise OSError("Die Explorer-Integration ist nur unter Windows verfügbar.")
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, EXPLORER_VERB_KEY) as key:
        winreg.SetValueEx(key, '', 0, winreg.REG_SZ, 'Mit Adolar Taggster öffnen')
        winreg.SetValueEx(key, 'MUIVerb', 0, winreg.REG_SZ, 'Mit Adolar Taggster öffnen')
        winreg.SetValueEx(key, 'Icon', 0, winreg.REG_SZ, _shell_icon_path())
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, EXPLORER_VERB_KEY + r'\command') as key:
        winreg.SetValueEx(key, '', 0, winreg.REG_SZ, _launch_command())


def _remove_explorer_integration():
    if sys.platform != 'win32':
        raise OSError("Die Explorer-Integration ist nur unter Windows verfügbar.")
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, EXPLORER_VERB_KEY + r'\command')
    except FileNotFoundError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, EXPLORER_VERB_KEY)
    except FileNotFoundError:
        pass


def _single_instance_name():
    """Use a stable per-user pipe name so different Windows users don't clash."""
    identity = f'{getpass.getuser()}|{Path.home()}'.encode('utf-8', errors='replace')
    suffix = hashlib.sha256(identity).hexdigest()[:16]
    return f'AdolarTaggster-{suffix}'


def _folder_from_arguments(arguments):
    try:
        index = arguments.index('--folder')
    except ValueError:
        return None
    if index + 1 >= len(arguments):
        return None
    value = arguments[index + 1].strip().strip('"')
    return os.path.normpath(value) if value else None


class SingleInstanceController(QObject):
    """Forward launch requests to the already running Taggster window."""
    message_received = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server_name = _single_instance_name()
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._accept_connections)

    def send_to_primary(self, message, timeout=750):
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(timeout):
            return False
        payload = json.dumps(message, ensure_ascii=False).encode('utf-8') + b'\n'
        accepted = socket.write(payload) == len(payload)
        socket.flush()
        socket.waitForBytesWritten(timeout)
        acknowledged = socket.waitForReadyRead(timeout) and bytes(socket.readAll()).startswith(b'OK\n')
        socket.disconnectFromServer()
        return accepted and acknowledged

    def listen(self):
        return self.server.listen(self.server_name)

    def _accept_connections(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket._taggster_buffer = bytearray()
            socket.readyRead.connect(lambda s=socket: self._read_socket(s))
            socket.disconnected.connect(lambda s=socket: self._finish_socket(s))
            if socket.bytesAvailable():
                self._read_socket(socket)

    def _finish_socket(self, socket):
        self._read_socket(socket)
        socket.deleteLater()

    def _read_socket(self, socket):
        socket._taggster_buffer.extend(bytes(socket.readAll()))
        while b'\n' in socket._taggster_buffer:
            raw, _, remainder = socket._taggster_buffer.partition(b'\n')
            socket._taggster_buffer = bytearray(remainder)
            try:
                message = json.loads(raw.decode('utf-8'))
                socket.write(b'OK\n')
                socket.flush()
                self.message_received.emit(message)
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass

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
        'title': '', 'artist': '', 'album': '', 'year': '', 'original_year': '',
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
            tags['original_year'] = str(id3.get('TDOR', ''))
            tags['genre'] = str(id3.get('TCON', ''))
            tags['tracknumber'] = str(id3.get('TRCK', ''))
            tags['bpm'] = str(id3.get('TBPM', ''))
            tags['album_artist'] = str(id3.get('TPE2', ''))
            tags['comment'] = str(id3.get('COMM::eng', '') or id3.get('COMM::deu', '') or
                                   next((str(id3[k]) for k in id3.keys() if k.startswith('COMM')), ''))
            tags['label'] = str(id3.get('TPUB', ''))
            tags['discnumber'] = str(id3.get('TPOS', ''))
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
        if tag_data.get('original_year'):
            id3['TDOR'] = TDOR(encoding=3, text=str(tag_data['original_year']))
        if tag_data.get('genre'):
            id3['TCON'] = TCON(encoding=3, text=tag_data['genre'])
        if tag_data.get('tracknumber'):
            id3['TRCK'] = TRCK(encoding=3, text=str(tag_data['tracknumber']))
        if tag_data.get('discnumber'):
            from mutagen.id3 import TPOS
            id3['TPOS'] = TPOS(encoding=3, text=str(tag_data['discnumber']))
        if tag_data.get('bpm'):
            from mutagen.id3 import TBPM
            id3['TBPM'] = TBPM(encoding=3, text=str(tag_data['bpm']))
        if tag_data.get('label'):
            id3['TPUB'] = TPUB(encoding=3, text=tag_data['label'])
        if 'comment' in tag_data:
            # Remove all existing COMM frames, then write if non-empty
            for k in list(id3.keys()):
                if k.startswith('COMM'):
                    del id3[k]
            if tag_data['comment']:
                id3['COMM::eng'] = COMM(encoding=3, lang='eng', desc='', text=tag_data['comment'])

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


def clean_artist(name):
    """Strip Discogs disambiguation suffix: 'Artist (2)' → 'Artist'."""
    return re.sub(r'\s*\(\d+\)\s*$', '', name.rstrip(' *')).strip()


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
            headers = {'User-Agent': 'AdolarTaggster/1.0'}
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

            # Expand each master into one row per available medium (Vinyl, CD, Cassette, ...)
            # so the user can pick the right one instead of getting a random main release.
            # _expand_master returns: a non-empty list (expanded rows), None (keep the
            # original master row as-is), or [] (drop it — a stale/deleted master that
            # would otherwise 404 when clicked).
            expanded = []
            for r in results:
                variants = self._expand_master(r, headers) if r['is_master'] else None
                if variants is None:
                    expanded.append(r)
                else:
                    expanded.extend(variants)

            self.results_ready.emit(expanded)
        except Exception as e:
            self.error.emit(str(e))

    def _expand_master(self, r, headers):
        """Fetch a master's versions and return one representative row per medium.
        Returns None to keep the original master row unchanged, or [] to drop it
        entirely (the master resource itself no longer resolves — some deleted/
        merged masters still return HTTP 200 with an empty versions list here,
        which would otherwise leave an unusable, 404-on-click entry in results)."""
        try:
            resp = requests.get(
                f"https://api.discogs.com/masters/{r['id']}/versions",
                headers=headers, params={'per_page': 100}, timeout=15
            )
            if resp.status_code != 200:
                return None
            versions = resp.json().get('versions', [])
            if not versions:
                try:
                    check = requests.get(
                        f"https://api.discogs.com/masters/{r['id']}",
                        headers=headers, timeout=10
                    )
                    if check.status_code == 404:
                        return []
                except requests.exceptions.RequestException:
                    pass
                return None
            by_medium = {}
            for v in versions:
                majors = v.get('major_formats') or []
                key = majors[0] if majors else (v.get('format', '').split(',')[0].strip() or 'Unbekannt')
                if key not in by_medium:
                    by_medium[key] = v
            out = []
            for v in by_medium.values():
                out.append({
                    'id': v.get('id'),
                    'title': r['title'],
                    'year': v.get('released', '') or r['year'],
                    'label': v.get('label', ''),
                    'country': v.get('country', ''),
                    'format': v.get('format', ''),
                    'cover_url': v.get('thumb', '') or r.get('cover_url', ''),
                    'thumb_url': v.get('thumb', '') or r.get('thumb_url', ''),
                    'tracklist': [],
                    'genre': r.get('genre', ''),
                    'style': r.get('style', ''),
                    'catno': v.get('catno', ''),
                    'resource_url': v.get('resource_url', ''),
                    'is_master': False,
                })
            return out
        except Exception:
            return None


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
            headers = {'User-Agent': 'AdolarTaggster/1.0'}
            if self.token:
                headers['Authorization'] = f'Discogs token={self.token}'

            r = requests.get(self.resource_url, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()

            # If this is a master release, load the main release instead
            # to get full label/country info
            if 'main_release_url' in data:
                master_id = data.get('id')
                try:
                    r2 = requests.get(data['main_release_url'], headers=headers, timeout=15)
                    if r2.status_code == 200:
                        release_data = r2.json()
                        # Main release is often Vinyl/Cassette (side A/B track numbers) —
                        # prefer a CD/normal-numbered version from the master's other versions
                        if master_id and self._is_vinyl_or_cassette(release_data):
                            better = self._find_better_version(master_id, headers)
                            if better:
                                release_data = better
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
                            clean_artist(a['name']) for a in track_artists
                        )
                        title = f"{title} /// {artist_str}"
                    tracklist.append({
                        'position': t.get('position', ''),
                        'title': title,
                        'duration': t.get('duration', ''),
                    })

            artists = data.get('artists', [])
            artist_name = ' & '.join(
                clean_artist(a['name']) for a in artists
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

    def _is_vinyl_or_cassette(self, release_data):
        names = {f.get('name', '').lower() for f in release_data.get('formats', [])}
        return bool(names & {'vinyl', 'cassette'})

    def _find_better_version(self, master_id, headers):
        """Pick a non-Vinyl/Cassette version from the master's release list, preferring CD."""
        try:
            r = requests.get(
                f'https://api.discogs.com/masters/{master_id}/versions',
                headers=headers, params={'per_page': 100}, timeout=15
            )
            if r.status_code != 200:
                return None
            versions = r.json().get('versions', [])
            bad = ('vinyl', 'cassette')
            candidates = [v for v in versions
                          if not any(b in v.get('format', '').lower() for b in bad)]
            if not candidates:
                return None
            candidates.sort(key=lambda v: 0 if 'cd' in v.get('format', '').lower() else 1)
            rel = requests.get(candidates[0]['resource_url'], headers=headers, timeout=15)
            if rel.status_code == 200:
                return rel.json()
        except Exception:
            pass
        return None


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
        self._too_small = False
        self._set_idle()

    _WARN_STYLE = ("background-color:#1e1e2e; border:3px solid #f38ba8;"
                   "border-radius:8px; color:#f38ba8; font-size:11px;")

    def _set_idle(self):
        if getattr(self, '_too_small', False):
            self.setStyleSheet(self._WARN_STYLE)
        else:
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
                                     headers={'User-Agent': 'AdolarTaggster/1.0'})
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
        self._too_small = False
        try:
            img = Image.open(BytesIO(data))
            self._too_small = img.width < 300 or img.height < 300
        except Exception:
            pass
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
            self._on_cover_changed(detail['cover_data'])
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

        # Comment row
        next_row = len(rows) + 1
        self.cb_comment = QCheckBox('Kommentar:')
        self.cb_comment.setChecked(cb_s.get('cb_comment', True))
        self.comment_inp = QLineEdit()
        mg.addWidget(self.cb_comment, next_row, 0)
        mg.addWidget(self.comment_inp, next_row, 1, 1, 3)

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
        numeric_display = False
        parent = self.parent()
        if parent and hasattr(parent, '_load_config'):
            numeric_display = parent._load_config().get('numeric_track_display', False)
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
            if track and numeric_display:
                width = len(str(total)) if total else 1
                display_pos = str(i + 1).zfill(width)
            else:
                display_pos = pos
            self.match_table.setItem(i, 3, QTableWidgetItem(f"{display_pos}/{total}" if display_pos else ''))

    def _fill_meta(self, detail):
        self.artist_inp.setText(detail.get('artist', ''))
        self.album_inp.setText(detail.get('album', ''))
        self.year_inp.setText(detail.get('year', ''))
        self.genre_inp.setText(detail.get('genre') or detail.get('style', ''))
        self.label_inp.setText(detail.get('label', ''))
        self.comment_inp.setText(detail.get('notes', ''))

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
                'cb_comment': self.cb_comment.isChecked(),
            }})

        compilation = self.cb_compilation.isChecked()
        cover_bytes = b''
        if self.cb_cover.isChecked() and self.cover_label.get_cover_data():
            try:
                cover_bytes = resize_cover(self.cover_label.get_cover_data(), 600)
            except Exception:
                pass

        numeric_display = False
        parent = self.parent()
        if parent and hasattr(parent, '_load_config'):
            numeric_display = parent._load_config().get('numeric_track_display', False)
        total_tracks = len(self._tracklist)
        track_width = len(str(total_tracks)) if total_tracks else 1

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

            if self.cb_tracknr.isChecked():
                if numeric_display and track:
                    td['tracknumber'] = f"{str(i + 1).zfill(track_width)}/{total_tracks}"
                elif track.get('position'):
                    td['tracknumber'] = f"{track['position']}/{total_tracks}"

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
            if self.cb_comment.isChecked():
                # Write comment; empty string clears existing comment
                td['comment'] = self.comment_inp.text()

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
        rh = self.results_table.horizontalHeader()
        rh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.results_table.setColumnWidth(0, 26)
        rh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        rh.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.results_table.setColumnWidth(2, 60)
        rh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        rh.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.results_table.setColumnWidth(4, 110)
        rh.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.results_table.setColumnWidth(5, 90)
        rh.setStretchLastSection(False)
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
        cover_data = detail.get('cover_data')
        if cover_data:
            try:
                img = Image.open(BytesIO(cover_data))
                cover_str = f"🖼 {img.width}×{img.height} px"
            except Exception:
                cover_str = '🖼 Cover'
        else:
            cover_str = '∅ Kein Cover'
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


class ReplaceRulesDialog(QDialog):
    """Table of find/replace rules applied to the generated filename during rename."""

    def __init__(self, rules, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ersetzungsregeln beim Umbenennen")
        self.setMinimumSize(480, 380)
        self._rules = [list(r) for r in rules]
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Wird beim Umbenennen auf den generierten Dateinamen angewendet, "
            "z.B. \"(\" → \"[\" um Klammern im Tag zu eckigen Klammern im Dateinamen zu machen."
        )
        info.setStyleSheet("color:#6c7086; font-size:11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Suchen", "Ersetzen durch", ""])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 32)
        layout.addWidget(self.table)
        self._reload_table()

        row_btns = QHBoxLayout()
        add_btn = QPushButton("+ Zeile")
        add_btn.setObjectName("secondary")
        add_btn.clicked.connect(self._add_row)
        row_btns.addWidget(add_btn)
        row_btns.addStretch()
        layout.addLayout(row_btns)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _reload_table(self):
        self.table.setRowCount(len(self._rules))
        for i, (src, dst) in enumerate(self._rules):
            self.table.setItem(i, 0, QTableWidgetItem(src))
            self.table.setItem(i, 1, QTableWidgetItem(dst))
            self._add_delete_button(i)

    def _add_delete_button(self, row):
        btn = QPushButton("🗑")
        btn.setFixedWidth(28)
        btn.setStyleSheet(
            "QPushButton { border:none; background-color:#313244; color:#f38ba8; "
            "border-radius:4px; padding:2px; min-height:22px; } "
            "QPushButton:hover { background-color:#45475a; }"
        )
        btn.clicked.connect(lambda: self._delete_row_at(btn))
        self.table.setCellWidget(row, 2, btn)

    def _delete_row_at(self, btn):
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 2) is btn:
                self.table.removeRow(row)
                break

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self._add_delete_button(row)

    def get_rules(self):
        rules = []
        for row in range(self.table.rowCount()):
            src_item = self.table.item(row, 0)
            dst_item = self.table.item(row, 1)
            src = src_item.text() if src_item else ''
            dst = dst_item.text() if dst_item else ''
            if src:
                rules.append([src, dst])
        return rules

    def _save(self):
        rules = self.get_rules()
        parent = self.parent()
        if parent and hasattr(parent, '_save_config'):
            parent._save_config({'rename_replacements': rules})
        self.accept()


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
        self.mask_input.currentTextChanged.connect(self._update_preview)
        mask_row.addWidget(self.mask_input, stretch=1)

        save_btn = QPushButton("💾")
        save_btn.setToolTip("Aktuelle Maske speichern")
        save_btn.setObjectName("secondary")
        save_btn.setFixedWidth(32)
        save_btn.setStyleSheet("padding: 2px; font-size: 14px;")
        save_btn.clicked.connect(self._save_mask)
        mask_row.addWidget(save_btn)

        del_btn = QPushButton("🗑")
        del_btn.setToolTip("Ausgewählte Maske löschen")
        del_btn.setObjectName("secondary")
        del_btn.setFixedWidth(32)
        del_btn.setStyleSheet("padding: 2px; font-size: 14px;")
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

    def _apply_replacements(self, s):
        parent = self.parent()
        rules = []
        if parent and hasattr(parent, '_load_config'):
            rules = parent._load_config().get('rename_replacements', [])
        for rule in rules:
            if isinstance(rule, (list, tuple)) and len(rule) == 2 and rule[0]:
                s = s.replace(rule[0], rule[1])
        return s

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
            new_base = self._apply_case(self._apply_replacements(self._apply_mask(mask, tags)))
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
        moves = []  # undo snapshot: (old_path, new_path)

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
            new_base = self._apply_case(self._apply_replacements(self._apply_mask(mask, tags)))
            src = Path(path)
            dest = self._resolve_dest(path, new_base)
            if src == dest:
                continue
            try:
                src.rename(dest)
                renamed += 1
                moves.append((str(src), str(dest)))
                moved_folders.add((src.parent, dest.parent))
            except Exception as e:
                errors.append(f"{src.name}: {e}")

        # Copy folder.jpg to each new destination folder
        import shutil
        folder_jpg_created = []  # undo snapshot: folder.jpg paths newly created at destination
        for src_dir, dest_dir in moved_folders:
            if src_dir == dest_dir:
                continue
            folder_jpg = src_dir / 'folder.jpg'
            dest_folder_jpg = dest_dir / 'folder.jpg'
            if folder_jpg.exists():
                existed_before = dest_folder_jpg.exists()
                try:
                    shutil.copy2(folder_jpg, dest_folder_jpg)
                    if not existed_before:
                        folder_jpg_created.append(str(dest_folder_jpg))
                except Exception as e:
                    errors.append(f"folder.jpg → {dest_dir.name}: {e}")

        if moves and parent and hasattr(parent, '_set_undo'):
            parent._set_undo({
                'type': 'rename',
                'moves': moves,
                'folder_jpg_created': folder_jpg_created,
                'label': f"Umbenennen von {len(moves)} Datei(en) rückgängig machen",
            })
        if moves and parent and hasattr(parent, '_notify_adolar_renames'):
            parent._notify_adolar_renames(moves)

        msg = f"{renamed} Datei(en) umbenannt/verschoben."
        if errors:
            msg += "\n\nFehler:\n" + "\n".join(errors)
        QMessageBox.information(self, "Umbenennen", msg)
        self.accept()


_MASK_PLACEHOLDER_RE = re.compile(r'%[1-6]')
_MASK_FIELD_MAP = {'1': 'artist', '2': 'title', '3': 'album', '4': 'year', '5': 'genre', '6': 'tracknumber'}


def _compile_mask_segment(seg):
    """Turn one path-segment mask (e.g. '[%4]-%3') into a regex with named groups f1..f6.
    All but the last placeholder in a segment match non-greedily; the last one is greedy
    so it can absorb the same separator character if it occurs inside the actual value."""
    placeholders = _MASK_PLACEHOLDER_RE.findall(seg)
    literals = _MASK_PLACEHOLDER_RE.split(seg)
    pattern = '^'
    for i, lit in enumerate(literals):
        pattern += re.escape(lit)
        if i < len(placeholders):
            digit = placeholders[i][1]
            greedy = (i == len(placeholders) - 1)
            pattern += f'(?P<f{digit}>.+)' if greedy else f'(?P<f{digit}>.+?)'
    pattern += '$'
    return re.compile(pattern)


def parse_path_with_mask(path, mask):
    """Reverse of the rename mask: extract %1-%6 field values from a file's path/name.
    Returns a dict of only the non-empty matched fields (e.g. {'artist': ..., 'title': ...}),
    or {} if the path doesn't match the mask's folder-depth/segment structure."""
    segments = mask.split('\\')
    if not segments:
        return {}
    regexes = [_compile_mask_segment(seg) for seg in segments]
    p = Path(path)
    folder_needed = segments[:-1]
    if folder_needed:
        parent_parts = p.parent.parts
        if len(parent_parts) < len(folder_needed):
            return {}
        targets = list(parent_parts[-len(folder_needed):]) + [p.stem]
    else:
        targets = [p.stem]
    extracted = {}
    for regex, target in zip(regexes, targets):
        m = regex.match(target)
        if not m:
            return {}
        for key, val in m.groupdict().items():
            if val:
                extracted[_MASK_FIELD_MAP[key[1]]] = val.strip()
    return extracted


class FileToTagDialog(QDialog):
    """Reverse of RenameDialog: parses tag values out of the file path/name using a mask."""
    masks_changed = pyqtSignal(list)

    FIELDS = [('Künstler', 'artist'), ('Titel', 'title'), ('Album', 'album'),
              ('Jahr', 'year'), ('Genre', 'genre'), ('Track', 'tracknumber')]

    def __init__(self, files, masks=None, last_mask='', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Datei → Tag")
        self.setMinimumSize(820, 520)
        self.files = files  # [(path, tags), ...] — tags = current tags, used as undo snapshot
        self._masks = masks or ["%1\\%3\\%6-%2", "%1\\[%4]-%3\\%6-%1-%2"]
        self._last_mask = last_mask
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "%1=Künstler  %2=Titel  %3=Album  %4=Jahr  %5=Genre  %6=Track-Nr.  —  "
            "liest Werte aus Pfad/Dateiname, z.B. %1\\[%4]-%3\\%6-%1-%2"
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
        self.mask_input.currentTextChanged.connect(self._update_preview)
        mask_row.addWidget(self.mask_input, stretch=1)

        save_btn = QPushButton("💾")
        save_btn.setToolTip("Aktuelle Maske speichern")
        save_btn.setObjectName("secondary")
        save_btn.setFixedWidth(32)
        save_btn.setStyleSheet("padding: 2px; font-size: 14px;")
        save_btn.clicked.connect(self._save_mask)
        mask_row.addWidget(save_btn)

        del_btn = QPushButton("🗑")
        del_btn.setToolTip("Ausgewählte Maske löschen")
        del_btn.setObjectName("secondary")
        del_btn.setFixedWidth(32)
        del_btn.setStyleSheet("padding: 2px; font-size: 14px;")
        del_btn.clicked.connect(self._delete_mask)
        mask_row.addWidget(del_btn)

        preview_btn = QPushButton("Vorschau")
        preview_btn.setObjectName("secondary")
        preview_btn.clicked.connect(self._update_preview)
        mask_row.addWidget(preview_btn)
        layout.addLayout(mask_row)

        cols = ["Dateiname"] + [lbl for lbl, _ in self.FIELDS]
        self.preview_table = QTableWidget(0, len(cols))
        self.preview_table.setHorizontalHeaderLabels(cols)
        hh = self.preview_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(cols)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.preview_table)

        btn_layout = QHBoxLayout()
        self.write_btn = QPushButton("Schreibe Tags")
        self.write_btn.clicked.connect(self._write_tags)
        cancel_btn = QPushButton("Schließen")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.write_btn)
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

    def _extract(self, path, mask):
        try:
            return parse_path_with_mask(path, mask)
        except Exception:
            return {}

    def _update_preview(self):
        mask = self.mask_input.currentText()
        self.preview_table.setRowCount(len(self.files))
        for i, (path, _tags) in enumerate(self.files):
            extracted = self._extract(path, mask)
            self.preview_table.setItem(i, 0, QTableWidgetItem(Path(path).name))
            for col, (_, key) in enumerate(self.FIELDS, start=1):
                val = extracted.get(key, '')
                item = QTableWidgetItem(val)
                if not val:
                    item.setForeground(QColor('#45475a'))
                self.preview_table.setItem(i, col, item)

    def _write_tags(self):
        mask = self.mask_input.currentText()
        self.masks_changed.emit(list(self._masks))
        parent = self.parent()
        if parent and hasattr(parent, '_save_config'):
            parent._save_config({'last_filetotag_mask': mask})

        entries = []  # undo snapshot: (path, old_tags)
        written = 0
        errors = []
        for path, old_tags in self.files:
            extracted = self._extract(path, mask)
            if not extracted:
                continue
            ok = write_mp3_tags(path, extracted)
            if ok:
                written += 1
                entries.append((path, dict(old_tags)))
            else:
                errors.append(Path(path).name)

        if entries and parent and hasattr(parent, '_set_undo'):
            parent._set_undo({
                'type': 'tag_write',
                'entries': entries,
                'label': f"Datei→Tag ({len(entries)} Datei(en)) rückgängig machen",
            })

        msg = f"{written} Datei(en) getaggt."
        if not self.files:
            msg = "Keine Dateien ausgewählt."
        elif written == 0:
            msg = "Keine Datei passte zur Maske — nichts geschrieben."
        if errors:
            msg += "\n\nFehler:\n" + "\n".join(errors)
        QMessageBox.information(self, "Datei → Tag", msg)
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
        self._bad_folders = []
        self._visited_rows = set()
        self._scan_done = False
        self._scanning = False
        self._build_ui()
        cached = self._get_cache()
        if cached and cached.get('root') == str(self.root):
            self._load_cache(cached)
        else:
            self.progress_label.setText(f"Bereit — Ordner: {self.root}")

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
        hint = QLabel("Doppelklick auf Zeile → Ordner im Tagger laden (Dialog bleibt offen)")
        hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        btn_row.addWidget(hint)
        btn_row.addStretch()
        self.rescan_btn = QPushButton("🔍 Scannen")
        self.rescan_btn.setObjectName("secondary")
        self.rescan_btn.setToolTip("Scannt den aktuell ausgewählten Ordner neu")
        self.rescan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self.rescan_btn)
        self.load_btn = QPushButton("📂 Letzte laden")
        self.load_btn.setObjectName("secondary")
        self.load_btn.clicked.connect(self._load_last_clicked)
        btn_row.addWidget(self.load_btn)
        self.save_btn = QPushButton("💾 Speichern")
        self.save_btn.setObjectName("secondary")
        self.save_btn.clicked.connect(self._save_scan_result)
        btn_row.addWidget(self.save_btn)
        close_btn = QPushButton("Schließen")
        close_btn.setObjectName("secondary")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _get_cache(self):
        parent = self.parent()
        if parent and hasattr(parent, '_load_config'):
            return parent._load_config().get('cover_scan_cache')
        return None

    def _load_cache(self, cache):
        self.root = cache.get('root', self.root)
        self._on_result(cache.get('bad_folders', []))
        ts = cache.get('timestamp', '?')
        self.progress_label.setText(f"Gespeicherte Suche geladen ({ts}) — {self.root}")
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(1)

    def _load_last_clicked(self):
        if self._scanning:
            QMessageBox.information(self, "Hinweis", "Scan läuft noch — bitte warten oder abbrechen.")
            return
        cache = self._get_cache()
        if not cache:
            QMessageBox.information(self, "Hinweis", "Keine gespeicherte Suche vorhanden.")
            return
        self._load_cache(cache)

    def _save_scan_result(self):
        parent = self.parent()
        if not (parent and hasattr(parent, '_save_config')):
            return
        if not self._scan_done:
            QMessageBox.information(self, "Hinweis", "Noch kein abgeschlossenes Scan-Ergebnis zum Speichern.")
            return
        remaining = [bf for i, bf in enumerate(self._bad_folders) if i not in self._visited_rows]
        data = {
            'root': str(self.root),
            'bad_folders': remaining,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }
        parent._save_config({'cover_scan_cache': data})
        QMessageBox.information(self, "Gespeichert",
                                 f"{len(remaining)} offene(r) Ordner für {Path(self.root).name} gespeichert "
                                 f"({len(self._visited_rows)} abgehakte übersprungen) — kann später ohne erneuten Scan geladen werden.")

    def _start_scan(self):
        if self._scanning:
            return
        self._scanning = True
        self.rescan_btn.setEnabled(False)
        self.load_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.result_table.setRowCount(0)
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
        self._bad_folders = bad_folders
        self._visited_rows = set()
        self._scan_done = True
        self._scanning = False
        self.rescan_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
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
            self._visited_rows.add(row)
            # Mark row as visited (strikethrough + dimmed) but keep dialog open
            for col in range(self.result_table.columnCount()):
                item = self.result_table.item(row, col)
                if item:
                    f = item.font()
                    f.setStrikeOut(True)
                    item.setFont(f)
                    item.setForeground(QColor('#45475a'))


class TagEditorDialog(QDialog):
    """Single-file tag editor opened by double-clicking a row."""
    def __init__(self, path, tags, parent=None):
        super().__init__(parent)
        self.path = path
        self.setWindowTitle(f"Tags — {Path(path).name}")
        self.setMinimumSize(520, 580)
        self._build_ui(tags)

    def _build_ui(self, tags):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Cover drop area + fields side by side
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self._cover_label = DropCoverLabel()
        self._cover_label.setFixedSize(120, 120)
        if tags.get('cover'):
            self._cover_label.set_cover(tags['cover'])
        top_row.addWidget(self._cover_label, 0)

        grid = QGridLayout()
        grid.setSpacing(6)
        fields = [
            ('Titel',        'title',        tags.get('title', '')),
            ('Künstler',     'artist',       tags.get('artist', '')),
            ('Album',        'album',        tags.get('album', '')),
            ('Album Artist', 'album_artist', tags.get('album_artist', '')),
            ('Jahr',         'year',         tags.get('year', '')),
            ('Original-Jahr', 'original_year', tags.get('original_year', '')),
            ('Genre',        'genre',        tags.get('genre', '')),
            ('Track',        'tracknumber',  tags.get('tracknumber', '')),
            ('Disc#',        'discnumber',   tags.get('discnumber', '')),
            ('BPM',          'bpm',          tags.get('bpm', '')),
            ('Label',        'label',        tags.get('label', '')),
        ]
        self._inputs = {}
        for row, (label, key, val) in enumerate(fields):
            grid.addWidget(QLabel(label + ':'), row, 0)
            inp = QLineEdit(val)
            if key == 'original_year':
                inp.setToolTip(
                    "Erscheinungsjahr des Original-Songs (ID3 TDOR), falls abweichend\n"
                    "vom Jahr dieser Edition — z.B. bei Compilations wie \"Now Yearbook '91\"\n"
                    "(Compilation von 2025, Songs von 1991)."
                )
            self._inputs[key] = inp
            grid.addWidget(inp, row, 1)
        top_row.addLayout(grid, 1)
        layout.addLayout(top_row)

        layout.addWidget(QLabel('Kommentar:'))
        self._comment = QTextEdit()
        self._comment.setPlainText(tags.get('comment', ''))
        self._comment.setMaximumHeight(70)
        layout.addWidget(self._comment)

        # Read-only info
        info = QLabel(
            f"Datei: {Path(self.path).name}  |  "
            f"Bitrate: {tags.get('bitrate', '?')} kbps  |  "
            f"Dauer: {format_duration(tags.get('duration', 0))}"
        )
        info.setStyleSheet("color:#6c7086; font-size:11px;")
        layout.addWidget(info)

        btn_row = QHBoxLayout()
        cover_btn = QPushButton("🔍 Cover suchen")
        cover_btn.setObjectName("secondary")
        cover_btn.clicked.connect(self._search_cover)
        btn_row.addWidget(cover_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.setObjectName("secondary")
        close_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(close_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _search_cover(self):
        import webbrowser
        from urllib.parse import quote
        artist = self._inputs.get('artist', QLineEdit()).text()
        album  = self._inputs.get('album',  QLineEdit()).text()
        q = quote(f"{artist} {album} cover")
        webbrowser.open(f"https://www.google.com/images?hl=&q={q}&tbs=isz:lt,islt:qsvga")

    def _save(self):
        tag_data = {k: inp.text() for k, inp in self._inputs.items()}
        tag_data['comment'] = self._comment.toPlainText()
        cover = self._cover_label.get_cover_data()
        ok = write_mp3_tags(self.path, tag_data, cover_data=cover if cover else None)
        if ok:
            if cover:
                try:
                    (Path(self.path).parent / 'folder.jpg').write_bytes(resize_cover(cover, 600))
                except Exception:
                    pass
            self.accept()
        else:
            QMessageBox.warning(self, "Fehler", "Tags konnten nicht gespeichert werden.")


KEEP = '<beibehalten>'

BATCH_FIELDS = [
    ('Künstler',     'artist'),
    ('Album',        'album'),
    ('Album Artist', 'album_artist'),
    ('Jahr',         'year'),
    ('Original-Jahr', 'original_year'),
    ('Genre',        'genre'),
    ('Label',        'label'),
    ('BPM',          'bpm'),
    ('Disc#',        'discnumber'),
    ('Kommentar',    'comment'),
]

COMBO_FIELDS = {'artist', 'album', 'album_artist'}

class BatchTagEditorDialog(QDialog):
    """Multi-file tag editor. Empty fields = keep existing; filled = overwrite all."""

    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.files = files  # [(path, tags), ...]
        n = len(files)
        self.setWindowTitle(f"Tags bearbeiten — {n} Dateien")
        self.setMinimumSize(480, 480)
        self._build_ui()

    def _collect_values(self, key):
        """Return sorted list of unique non-empty tag values across all files."""
        seen = []
        for _, tags in self.files:
            v = tags.get(key, '').strip()
            if v and v not in seen:
                seen.append(v)
        return seen

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        hint = QLabel(f"Felder mit <beibehalten> werden nicht verändert. Nur geänderte Felder werden für alle {len(self.files)} Dateien gesetzt.")
        hint.setStyleSheet("color:#a6adc8; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self._cover_label = DropCoverLabel()
        self._cover_label.setFixedSize(120, 120)
        self._cover_label.setText("Cover für alle\n(Bild hierher ziehen)")
        top_row.addWidget(self._cover_label, 0)

        grid = QGridLayout()
        grid.setSpacing(6)
        self._inputs = {}
        for row, (label, key) in enumerate(BATCH_FIELDS):
            lbl = QLabel(label + ':')
            grid.addWidget(lbl, row, 0)
            if key in COMBO_FIELDS:
                cb = QComboBox()
                cb.setEditable(True)
                cb.addItem(KEEP)
                for v in self._collect_values(key):
                    cb.addItem(v)
                cb.setCurrentIndex(0)
                cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                cb.lineEdit().setPlaceholderText(KEEP)
                self._inputs[key] = cb
                grid.addWidget(cb, row, 1)
            else:
                inp = QLineEdit()
                inp.setPlaceholderText(KEEP)
                if key == 'original_year':
                    inp.setToolTip(
                        "Erscheinungsjahr des Original-Songs (ID3 TDOR), falls abweichend\n"
                        "vom Jahr dieser Edition — z.B. bei Compilations wie \"Now Yearbook '91\"\n"
                        "(Compilation von 2025, Songs von 1991). Praktisch um es für alle\n"
                        "markierten Tracks einer Compilation auf einmal zu setzen."
                    )
                self._inputs[key] = inp
                grid.addWidget(inp, row, 1)
        top_row.addLayout(grid, 1)
        layout.addLayout(top_row)

        btn_row = QHBoxLayout()
        cover_btn = QPushButton("🔍 Cover suchen")
        cover_btn.setObjectName("secondary")
        cover_btn.clicked.connect(self._search_cover)
        btn_row.addWidget(cover_btn)
        btn_row.addStretch()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self._confirm_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _search_cover(self):
        import webbrowser
        from urllib.parse import quote
        artist = self._get_value('artist') or next(
            (tags.get('artist', '') for _, tags in self.files if tags.get('artist')), '')
        album  = self._get_value('album') or next(
            (tags.get('album', '')  for _, tags in self.files if tags.get('album')),  '')
        q = quote(f"{artist} {album} cover")
        webbrowser.open(f"https://www.google.com/images?hl=&q={q}&tbs=isz:lt,islt:qsvga")

    def _get_value(self, key):
        w = self._inputs[key]
        if isinstance(w, QComboBox):
            v = w.currentText()
            return '' if v == KEEP else v
        return w.text()

    def _confirm_save(self):
        changes = {k: self._get_value(k) for k in self._inputs if self._get_value(k)}
        cover = self._cover_label.get_cover_data()
        if not changes and not cover:
            QMessageBox.information(self, "Hinweis", "Keine Felder ausgefüllt — nichts zu tun.")
            return

        label_map = {key: lbl for lbl, key in BATCH_FIELDS}
        lines = '\n'.join(f"  • {label_map[k]}: {v}" for k, v in changes.items())
        if cover:
            lines += ('\n' if lines else '') + "  • Cover: neues Bild"
        msg = (f"Folgende Werte werden für alle {len(self.files)} markierten Dateien gesetzt:\n\n"
               f"{lines}\n\nFortfahren?")
        reply = QMessageBox.question(self, "Bestätigung", msg,
                                     QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Ok:
            errors = []
            for path, _ in self.files:
                ok = write_mp3_tags(path, changes, cover_data=cover if cover else None)
                if not ok:
                    errors.append(Path(path).name)
            if cover and self.files:
                try:
                    folder = Path(self.files[0][0]).parent
                    (folder / 'folder.jpg').write_bytes(resize_cover(cover, 600))
                except Exception:
                    pass
            if errors:
                QMessageBox.warning(self, "Fehler", f"Fehler bei:\n" + '\n'.join(errors))
            self.accept()
        # else: dialog stays open


class AdolarSyncHistoryDialog(QDialog):
    """Shows the last N successful Adolar syncs (file/folder + date)."""

    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Letzte Adolar-Syncs")
        self.setMinimumSize(560, 400)
        layout = QVBoxLayout(self)

        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Datei/Ordner", "Datum"])
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setRowCount(len(history))
        for i, entry in enumerate(history):
            if entry.get('type') == 'rename':
                label = f"{entry.get('old_path', '')} → {entry.get('new_path', '')}"
            else:
                label = entry.get('path', '')
            table.setItem(i, 0, QTableWidgetItem(label))
            table.setItem(i, 1, QTableWidgetItem(entry.get('timestamp', '')))
        layout.addWidget(table)

        if not history:
            hint = QLabel("Noch keine erfolgreichen Syncs.")
            hint.setStyleSheet("color:#6c7086; font-size:11px;")
            layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.setObjectName("secondary")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


class AdolarConfigDialog(QDialog):
    """Connect Taggster to an Adolar instance: token auth, library pick, path mapping."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Adolar-Verbindung")
        self.setMinimumWidth(480)
        self._config = dict(config)
        self._libraries = []
        self._result = None
        self._retry_used = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Adolar-URL:"))
        self.url_input = QLineEdit(self._config.get('url', ''))
        self.url_input.setPlaceholderText("http://192.168.1.10:5000")
        layout.addWidget(self.url_input)

        layout.addWidget(QLabel("API-Token:"))
        token_row = QHBoxLayout()
        self.token_input = QLineEdit(self._config.get('token', ''))
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        token_row.addWidget(self.token_input, 1)
        self.toggle_token_btn = QPushButton("👁")
        self.toggle_token_btn.setObjectName("secondary")
        self.toggle_token_btn.setFixedWidth(32)
        self.toggle_token_btn.setStyleSheet("padding: 2px; font-size: 14px;")
        self.toggle_token_btn.setCheckable(True)
        self.toggle_token_btn.setEnabled(bool(self._config.get('token')))
        self.toggle_token_btn.toggled.connect(
            lambda checked: self.token_input.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password))
        self.token_input.textChanged.connect(lambda t: self.toggle_token_btn.setEnabled(bool(t)))
        token_row.addWidget(self.toggle_token_btn)
        layout.addLayout(token_row)

        hint = QLabel("Token erzeugen unter: Adolar → Einstellungen → Benutzerverwaltung → API-Zugriff")
        hint.setStyleSheet("color:#a6adc8; font-size:11px;")
        layout.addWidget(hint)

        connect_row = QHBoxLayout()
        connect_row.addStretch()
        self.connect_btn = QPushButton("Verbinden")
        self.connect_btn.setObjectName("secondary")
        self.connect_btn.clicked.connect(self._connect)
        connect_row.addWidget(self.connect_btn)
        layout.addLayout(connect_row)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#a6adc8; font-size:11px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("Bibliothek:"))
        self.library_combo = QComboBox()
        self.library_combo.setEnabled(False)
        layout.addWidget(self.library_combo)
        if self._config.get('library_id'):
            self.library_combo.addItem(
                self._config.get('library_name') or self._config['library_id'],
                self._config['library_id']
            )
            self.library_combo.setEnabled(True)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Lokaler Pfad:"))
        self.local_path_input = QLineEdit(self._config.get('local_path', ''))
        path_row.addWidget(self.local_path_input, 1)
        browse_btn = QPushButton("…")
        browse_btn.setObjectName("secondary")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._browse_local_path)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        sync_row = QHBoxLayout()
        self.sync_btn = QPushButton("Sync")
        self.sync_btn.setObjectName("secondary")
        self.sync_btn.setEnabled(bool(self._config.get('sync_log')))
        self.sync_btn.setToolTip("Ungesyncte Änderungen erneut an Adolar senden")
        self.sync_btn.clicked.connect(self._do_sync)
        sync_row.addWidget(self.sync_btn)
        history_btn = QPushButton("Letzte Syncs")
        history_btn.setObjectName("secondary")
        history_btn.clicked.connect(self._show_history)
        sync_row.addWidget(history_btn)
        sync_row.addStretch()
        layout.addLayout(sync_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _do_sync(self):
        parent = self.parent()
        if not (parent and hasattr(parent, '_sync_pending_adolar_changes')):
            return
        parent._sync_pending_adolar_changes()
        if hasattr(parent, '_load_adolar_config'):
            self._config = parent._load_adolar_config()
        self.sync_btn.setEnabled(bool(self._config.get('sync_log')))

    def _show_history(self):
        parent = self.parent()
        config = parent._load_adolar_config() if parent and hasattr(parent, '_load_adolar_config') else self._config
        history = config.get('sync_history', [])
        dlg = AdolarSyncHistoryDialog(history, parent=self)
        dlg.exec()

    def _browse_local_path(self):
        path = QFileDialog.getExistingDirectory(
            self, "Lokalen Bibliotheksordner wählen", self.local_path_input.text() or "")
        if path:
            self.local_path_input.setText(path)

    def _connect(self):
        url = self.url_input.text().strip().rstrip('/')
        token = self.token_input.text().strip()
        if not url or not token:
            self.status_label.setText("URL und Token werden benötigt.")
            return
        self.connect_btn.setEnabled(False)
        self.status_label.setText("Verbinde…")
        QApplication.processEvents()
        try:
            r = requests.get(f"{url}/api/me", headers={'Authorization': f'Bearer {token}'}, timeout=5)
        except requests.exceptions.RequestException as e:
            self.connect_btn.setEnabled(True)
            self.status_label.setText("Keine Verbindung möglich.")
            QMessageBox.warning(self, "Adolar", f"Keine Verbindung zu {url} möglich.\n\n{e}")
            return
        self.connect_btn.setEnabled(True)
        if r.status_code == 200:
            data = r.json()
            if data.get('role') != 'admin':
                self.status_label.setText("Angemeldet, aber kein Admin-Konto — Token benötigt Admin-Rechte.")
                return
            self._retry_used = False
            self.status_label.setText(f"Verbunden als {data.get('username', '?')} (Admin).")
            self._load_libraries(url, token)
            return
        if r.status_code in (401, 403):
            if not self._retry_used:
                self._retry_used = True
                self.status_label.setText("Token ungültig oder abgelaufen.")
                QMessageBox.warning(self, "Adolar",
                                     "Token ungültig oder abgelaufen. Bitte erneut eingeben und verbinden.")
                self.token_input.clear()
                self.token_input.setFocus()
            else:
                self.status_label.setText("Zugangsdaten weiterhin ungültig.")
                QMessageBox.critical(self, "Adolar",
                                      "Zugangsdaten weiterhin ungültig. Bitte in den Einstellungen prüfen — "
                                      "es wird kein weiterer Verbindungsversuch unternommen.")
            return
        self.status_label.setText(f"Unerwartete Antwort: HTTP {r.status_code}")

    def _load_libraries(self, url, token):
        try:
            r = requests.get(f"{url}/api/admin/libraries",
                              headers={'Authorization': f'Bearer {token}'}, timeout=5)
        except requests.exceptions.RequestException as e:
            self.status_label.setText(f"Verbunden, aber Bibliotheken konnten nicht geladen werden: {e}")
            return
        if r.status_code != 200:
            self.status_label.setText(f"Bibliotheken konnten nicht geladen werden (HTTP {r.status_code}).")
            return
        data = r.json()
        self._libraries = data.get('libraries', [])
        self.library_combo.clear()
        for lib in self._libraries:
            self.library_combo.addItem(lib.get('name', lib['id']), lib['id'])
        self.library_combo.setEnabled(bool(self._libraries))
        target_id = self._config.get('library_id') or data.get('active_id')
        if target_id:
            idx = self.library_combo.findData(target_id)
            if idx >= 0:
                self.library_combo.setCurrentIndex(idx)

    def _save(self):
        url = self.url_input.text().strip().rstrip('/')
        token = self.token_input.text().strip()
        lib_id = self.library_combo.currentData()
        lib_name = self.library_combo.currentText() if lib_id else ''
        local_path = self.local_path_input.text().strip()
        adolar_path = self._config.get('adolar_path', '')
        for lib in self._libraries:
            if lib['id'] == lib_id:
                adolar_path = lib.get('music_path', '')
                break
        self._result = {
            'url': url,
            'token': token,
            'library_id': lib_id or '',
            'library_name': lib_name,
            'adolar_path': adolar_path,
            'local_path': local_path,
            'sync_log': self._config.get('sync_log', []),
        }
        self.accept()

    def get_config(self):
        return self._result


class SettingsDialog(QDialog):
    def __init__(self, token, numeric_track=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Discogs Personal Access Token:"))
        token_row = QHBoxLayout()
        self.token_input = QLineEdit(token or '')
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Leer lassen für anonyme Suche (Rate-Limit)")
        token_row.addWidget(self.token_input, 1)
        self.toggle_token_btn = QPushButton("👁")
        self.toggle_token_btn.setObjectName("secondary")
        self.toggle_token_btn.setFixedWidth(32)
        self.toggle_token_btn.setStyleSheet("padding: 2px; font-size: 14px;")
        self.toggle_token_btn.setCheckable(True)
        self.toggle_token_btn.setEnabled(bool(token))
        self.toggle_token_btn.toggled.connect(
            lambda checked: self.token_input.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password))
        self.token_input.textChanged.connect(
            lambda t: self.toggle_token_btn.setEnabled(bool(t)))
        token_row.addWidget(self.toggle_token_btn)
        layout.addLayout(token_row)

        hint = QLabel(
            "Token erstellen unter: discogs.com → Einstellungen → Entwickler\n"
            "Mit Token: 60 Anfragen/Min statt 25"
        )
        hint.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(hint)

        layout.addSpacing(10)
        self.cb_numeric_track = QCheckBox("Tracknummer in Discogs-Suche immer numerisch anzeigen (1/n, 2/n, …)")
        self.cb_numeric_track.setChecked(numeric_track)
        self.cb_numeric_track.setToolTip(
            "Zeigt und speichert im Track-Match-Dialog immer fortlaufend numerierte\n"
            "Tracknummern (z.B. 01/14 … 14/14), unabhängig davon was Discogs liefert\n"
            "(z.B. Vinyl-Seiten A1/B2 statt echter Tracknummern)."
        )
        layout.addWidget(self.cb_numeric_track)

        layout.addSpacing(12)
        explorer_group = QGroupBox("Windows Explorer")
        explorer_layout = QVBoxLayout(explorer_group)
        explorer_hint = QLabel(
            "Fügt bei Ordnern den Befehl „Mit Adolar Taggster öffnen“ hinzu.\n"
            "Unter Windows 11 steht er gegebenenfalls unter „Weitere Optionen anzeigen“.")
        explorer_hint.setWordWrap(True)
        explorer_hint.setStyleSheet("color: #a6adc8; font-size: 11px;")
        explorer_layout.addWidget(explorer_hint)

        self.explorer_status_label = QLabel()
        explorer_layout.addWidget(self.explorer_status_label)

        explorer_buttons = QHBoxLayout()
        self.explorer_install_btn = QPushButton("Eintrag hinzufügen")
        self.explorer_install_btn.clicked.connect(self._install_explorer_entry)
        self.explorer_remove_btn = QPushButton("Eintrag entfernen")
        self.explorer_remove_btn.setObjectName("secondary")
        self.explorer_remove_btn.clicked.connect(self._remove_explorer_entry)
        explorer_buttons.addWidget(self.explorer_install_btn)
        explorer_buttons.addWidget(self.explorer_remove_btn)
        explorer_buttons.addStretch()
        explorer_layout.addLayout(explorer_buttons)
        layout.addWidget(explorer_group)
        self._refresh_explorer_status()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def get_token(self):
        return self.token_input.text().strip()

    def get_numeric_track(self):
        return self.cb_numeric_track.isChecked()

    def _refresh_explorer_status(self):
        status = _explorer_integration_status()
        if status == 'installed':
            self.explorer_status_label.setText("✓ Kontextmenü-Eintrag ist installiert.")
            self.explorer_status_label.setStyleSheet("color: #a6e3a1;")
            self.explorer_install_btn.setText("Eintrag reparieren")
            self.explorer_remove_btn.setEnabled(True)
        elif status == 'outdated':
            self.explorer_status_label.setText("⚠ Der gespeicherte Programmpfad ist nicht mehr aktuell.")
            self.explorer_status_label.setStyleSheet("color: #f9e2af;")
            self.explorer_install_btn.setText("Eintrag reparieren")
            self.explorer_remove_btn.setEnabled(True)
        elif status == 'unsupported':
            self.explorer_status_label.setText("Nur unter Windows verfügbar.")
            self.explorer_status_label.setStyleSheet("color: #6c7086;")
            self.explorer_install_btn.setEnabled(False)
            self.explorer_remove_btn.setEnabled(False)
        else:
            self.explorer_status_label.setText("Kontextmenü-Eintrag ist nicht installiert.")
            self.explorer_status_label.setStyleSheet("color: #a6adc8;")
            self.explorer_install_btn.setText("Eintrag hinzufügen")
            self.explorer_remove_btn.setEnabled(False)

    def _install_explorer_entry(self):
        try:
            _install_explorer_integration()
            self._refresh_explorer_status()
            QMessageBox.information(
                self, "Windows Explorer",
                "Der Eintrag „Mit Adolar Taggster öffnen“ wurde hinzugefügt.")
        except OSError as exc:
            QMessageBox.warning(self, "Windows Explorer", f"Der Eintrag konnte nicht erstellt werden:\n{exc}")

    def _remove_explorer_entry(self):
        try:
            _remove_explorer_integration()
            self._refresh_explorer_status()
            QMessageBox.information(self, "Windows Explorer", "Der Kontextmenü-Eintrag wurde entfernt.")
        except OSError as exc:
            QMessageBox.warning(self, "Windows Explorer", f"Der Eintrag konnte nicht entfernt werden:\n{exc}")


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


class BpmCalculationThread(QThread):
    progress = pyqtSignal(int, int, str)   # done, total, filename
    finished = pyqtSignal(int, int)        # written, skipped

    def __init__(self, files):
        super().__init__()
        self.files = files  # [(path, tags), ...]
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        written = 0
        skipped = 0
        total = len(self.files)
        for i, (path, tags) in enumerate(self.files):
            if self._cancel:
                return
            fname = Path(path).name
            self.progress.emit(i, total, fname)
            # Skip if BPM already set
            existing = tags.get('bpm', '')
            if existing and existing != '0':
                skipped += 1
                continue
            try:
                import librosa, numpy as np
                # Load max 60s — enough for reliable BPM, much faster than full file
                y, sr = librosa.load(path, sr=22050, mono=True, duration=60)
                tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
                # librosa 0.10+ returns ndarray — extract scalar safely
                bpm = int(round(float(np.atleast_1d(tempo)[0])))
                if bpm > 0:
                    try:
                        id3 = ID3(path)
                    except Exception:
                        id3 = ID3()
                    from mutagen.id3 import TBPM
                    id3['TBPM'] = TBPM(encoding=3, text=str(bpm))
                    id3.save(path, v2_version=3)
                    written += 1
            except Exception as e:
                print(f"BPM error {fname}: {e}")
        self.finished.emit(written, skipped)


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
        self.setWindowTitle("Adolar Taggster")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)
        self._current_folder = None
        self._current_folder_jpg = None
        self._files = []  # list of (path, tags)
        self._last_undo = None  # single-slot undo: {'type': 'rename'|'tag_write', ...}
        self._adolar_active = False  # True once the Adolar bar has connected successfully
        self._adolar_pending_folders = set()
        self._adolar_debounce_timer = None
        self._discogs_token = self._load_token()
        self._build_ui()
        self._build_menu()
        # _restore_last_folder disabled — crashes Qt on network paths (QFileSystemModel.index)

    def _load_config(self):
        cfg = Path.home() / '.adolartaggster.json'
        if cfg.exists():
            try:
                return json.loads(cfg.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _save_config(self, data):
        cfg = Path.home() / '.adolartaggster.json'
        existing = self._load_config()
        existing.update(data)
        cfg.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')

    def _load_adolar_config(self):
        """Separate config file for Adolar connection settings — kept apart from
        the general config since it holds a token and a per-instance sync log."""
        cfg = Path.home() / '.adolartaggster-adolar.json'
        if cfg.exists():
            try:
                return json.loads(cfg.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _save_adolar_config(self, data):
        cfg = Path.home() / '.adolartaggster-adolar.json'
        existing = self._load_adolar_config()
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

    def _load_filetotag_masks(self):
        default = ["%1\\%3\\%6-%2", "%1\\[%4]-%3\\%6-%1-%2"]
        return self._load_config().get('filetotag_masks', default)

    def _save_filetotag_masks(self, masks):
        self._save_config({'filetotag_masks': masks})

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
        settings_action = QAction("Einstellungen", self)
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)

        adolar_config_action = QAction("Adolar-Verbindung…", self)
        adolar_config_action.triggered.connect(self._open_adolar_config)
        tools_menu.addAction(adolar_config_action)

        about_menu = menubar.addMenu("Über")
        about_action = QAction("Über Adolar Taggster", self)
        about_action.triggered.connect(self._open_about)
        about_menu.addAction(about_action)
        help_action = QAction("Hilfe", self)
        help_action.triggered.connect(lambda: __import__('webbrowser').open("https://polze.net/tagmegently-help.html"))
        about_menu.addAction(help_action)

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

        self.filetotag_btn = QPushButton("🏷 Datei→Tag")
        self.filetotag_btn.setEnabled(False)
        self.filetotag_btn.setStyleSheet(secondary_ss)
        self.filetotag_btn.setToolTip("Liest Tag-Werte aus Dateiname/Ordnerstruktur anhand einer Maske")
        self.filetotag_btn.clicked.connect(self._open_filetotag)

        self.quick_filetotag_btn = QPushButton("⚡")
        self.quick_filetotag_btn.setEnabled(False)
        self.quick_filetotag_btn.setFixedWidth(30)
        self.quick_filetotag_btn.setStyleSheet(secondary_ss)
        self.quick_filetotag_btn.clicked.connect(self._quick_filetotag)
        self._update_quick_filetotag_tooltip()

        self.undo_btn = QPushButton("↩ Rückgängig")
        self.undo_btn.setEnabled(False)
        self.undo_btn.setStyleSheet(secondary_ss)
        self.undo_btn.clicked.connect(self._undo_last_action)

        self.adolar_sync_btn = QPushButton("🚀 Sync")
        self.adolar_sync_btn.setVisible(False)
        self.adolar_sync_btn.setStyleSheet(secondary_ss)
        self.adolar_sync_btn.setToolTip("Ungesyncte Änderungen erneut an Adolar senden")
        self.adolar_sync_btn.clicked.connect(self._sync_pending_adolar_changes)

        self.replace_rules_btn = QPushButton("X→Y")
        self.replace_rules_btn.setToolTip(
            "Ersetzungsregeln für den generierten Dateinamen beim Umbenennen\n"
            "z.B. '(' im Tag → '[' im Dateinamen"
        )
        self.replace_rules_btn.setStyleSheet(secondary_ss)
        self.replace_rules_btn.clicked.connect(self._open_replace_rules)

        self.autonumber_btn = QPushButton("# Nummerierung")
        self.autonumber_btn.setEnabled(False)
        self.autonumber_btn.setToolTip(
            "Schreibt Track-Nummern (1, 2, 3…) in die Tags der markierten Dateien\n"
            "in der Reihenfolge wie sie in der Liste erscheinen"
        )
        self.autonumber_btn.setStyleSheet(secondary_ss)
        self.autonumber_btn.clicked.connect(self._autonumber_tracks)

        self.bpm_btn = QPushButton("♩ BPM")
        self.bpm_btn.setEnabled(False)
        self.bpm_btn.setToolTip("Berechnet BPM für markierte MP3s und schreibt sie in den Tag\n(überspringt Dateien mit vorhandenem BPM-Tag)")
        self.bpm_btn.setStyleSheet(secondary_ss)
        self.bpm_btn.clicked.connect(self._calculate_bpm)

        self.select_all_btn = QPushButton("Alle")
        self.select_all_btn.setStyleSheet(secondary_ss)
        self.select_all_btn.clicked.connect(self._select_all)

        self.deselect_btn = QPushButton("Keine")
        self.deselect_btn.setStyleSheet(secondary_ss)
        self.deselect_btn.clicked.connect(self._deselect_all)

        self.move_up_btn = QPushButton("▲ Hoch")
        self.move_up_btn.setEnabled(False)
        self.move_up_btn.setStyleSheet(secondary_ss)
        self.move_up_btn.setToolTip("Markierte Zeile in der Liste nach oben verschieben")
        self.move_up_btn.clicked.connect(self._move_file_row_up)

        self.move_down_btn = QPushButton("▼ Runter")
        self.move_down_btn.setEnabled(False)
        self.move_down_btn.setStyleSheet(secondary_ss)
        self.move_down_btn.setToolTip("Markierte Zeile in der Liste nach unten verschieben")
        self.move_down_btn.clicked.connect(self._move_file_row_down)

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
        toolbar_layout.addWidget(self.filetotag_btn)
        toolbar_layout.addWidget(self.quick_filetotag_btn)
        toolbar_layout.addWidget(self.replace_rules_btn)
        toolbar_layout.addWidget(self.autonumber_btn)
        toolbar_layout.addWidget(self.bpm_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self.select_all_btn)
        toolbar_layout.addWidget(self.deselect_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self.move_up_btn)
        toolbar_layout.addWidget(self.move_down_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self.cover_scan_btn)
        toolbar_layout.addWidget(self.cancel_scan_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self.undo_btn)
        toolbar_layout.addWidget(self.adolar_sync_btn)
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

        # Adolar bar — only shown once an Adolar connection is configured
        self._adolar_bar_container = QWidget()
        self._adolar_bar_layout = QVBoxLayout(self._adolar_bar_container)
        self._adolar_bar_layout.setContentsMargins(4, 4, 4, 2)
        self._adolar_bar_layout.setSpacing(0)
        tree_layout.addWidget(self._adolar_bar_container)

        # Quick-access panel (special folders + favorites) — rebuilt dynamically
        self._quick_container = QWidget()
        self._quick_container.setStyleSheet("background-color: #181825;")
        self._quick_layout = QVBoxLayout(self._quick_container)
        self._quick_layout.setContentsMargins(4, 4, 4, 2)
        self._quick_layout.setSpacing(1)
        tree_layout.addWidget(self._quick_container)
        self._rebuild_quick_access()
        self._rebuild_adolar_bar()

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
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)
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

        # Column definitions: (header, tag_key, default_visible, resizeMode)
        # Col 2 (Dateiname) stores full path in UserRole
        self.COLUMNS = [
            ("🖼",          'cover_flag',   True,  'fixed'),
            ("Track",       'tracknumber',  True,  'contents'),
            ("Dateiname",   'filename',     True,  'stretch'),
            ("Künstler",    'artist',       True,  'contents'),
            ("Album",       'album',        True,  'stretch'),
            ("Titel",       'title',        True,  'stretch'),
            ("Jahr",        'year',         True,  'contents'),
            ("Genre",       'genre',        True,  'contents'),
            ("Dauer",       'duration',     True,  'contents'),
            ("Album Artist",'album_artist', True,  'contents'),
            ("BPM",         'bpm',          True,  'contents'),
            ("Bitrate",     'bitrate',      False, 'contents'),
            ("Kommentar",   'comment',      False, 'stretch'),
            ("Label",       'label',        False, 'contents'),
            ("Disc#",       'discnumber',   False, 'contents'),
            ("Original-Jahr", 'original_year', False, 'contents'),
        ]
        # Load saved visibility
        saved_vis = self._load_config().get('column_visibility', {})
        self._col_visible = {}
        for i, (hdr, key, default, _) in enumerate(self.COLUMNS):
            self._col_visible[i] = saved_vis.get(str(i), default)

        self.file_table = QTableWidget(0, len(self.COLUMNS))
        self.file_table.setHorizontalHeaderLabels([c[0] for c in self.COLUMNS])
        hh = self.file_table.horizontalHeader()
        DEFAULT_WIDTHS = {
            'fixed': 28, 'stretch': 180, 'contents': 90
        }
        for i, (_, _, _, mode) in enumerate(self.COLUMNS):
            if mode == 'fixed':
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.file_table.setColumnWidth(i, 28)
            else:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self.file_table.setColumnWidth(i, DEFAULT_WIDTHS.get(mode, 90))
        hh.setStretchLastSection(False)
        self.file_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        for i in range(len(self.COLUMNS)):
            if not self._col_visible[i]:
                self.file_table.setColumnHidden(i, True)
        # Right-click header for column visibility; drag to reorder
        hh.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hh.customContextMenuRequested.connect(self._show_column_menu)
        hh.setSectionsMovable(True)
        hh.sectionMoved.connect(self._save_column_order)
        # Restore saved column order
        saved_order = self._load_config().get('column_order', [])
        if len(saved_order) == len(self.COLUMNS):
            for visual_idx, logical_idx in enumerate(saved_order):
                current_visual = hh.visualIndex(logical_idx)
                if current_visual != visual_idx:
                    hh.moveSection(current_visual, visual_idx)
        # Re-apply Interactive after moveSection (moveSection can reset resize modes)
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.file_table.setColumnWidth(0, 28)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_table.setSortingEnabled(True)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.verticalHeader().setDefaultSectionSize(22)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setShowGrid(False)
        self.file_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.file_table.doubleClicked.connect(self._on_file_double_clicked)
        self.file_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_table.customContextMenuRequested.connect(self._show_file_context_menu)
        files_layout.addWidget(self.file_table)

        splitter.addWidget(files_widget)
        splitter.setSizes([280, 900])
        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit")

    _QUICK_BTN_STYLE = ("QPushButton { text-align:left; background:transparent; color:#a6adc8;"
                        " border:none; padding:3px 6px; font-size:12px; border-radius:4px; }"
                        "QPushButton:hover { background:#313244; color:#cdd6f4; }")

    def _rebuild_quick_access(self):
        # Clear existing buttons
        while self._quick_layout.count():
            item = self._quick_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Special folders
        from PyQt6.QtCore import QStandardPaths
        special = [
            ('🎵 Musik',     QStandardPaths.StandardLocation.MusicLocation),
            ('⬇ Downloads', QStandardPaths.StandardLocation.DownloadLocation),
            ('🖥 Desktop',  QStandardPaths.StandardLocation.DesktopLocation),
            ('📄 Dokumente', QStandardPaths.StandardLocation.DocumentsLocation),
            ('🎬 Videos',   QStandardPaths.StandardLocation.MoviesLocation),
        ]
        for label, loc in special:
            paths = QStandardPaths.standardLocations(loc)
            if paths:
                btn = QPushButton(label)
                btn.setStyleSheet(self._QUICK_BTN_STYLE)
                btn.clicked.connect(lambda checked, p=paths[0]: self._navigate_tree(p))
                self._quick_layout.addWidget(btn)

        # Favorites
        favorites = self._load_config().get('favorites', [])
        if favorites:
            sep = QLabel()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background:#313244; margin:2px 4px;")
            self._quick_layout.addWidget(sep)
        for fav_path in favorites:
            name = Path(fav_path).name or fav_path
            btn = QPushButton(f"⭐ {name}")
            btn.setStyleSheet(self._QUICK_BTN_STYLE.replace('#a6adc8', '#f9e2af'))
            btn.setToolTip(fav_path)
            btn.clicked.connect(lambda checked, p=fav_path: self._navigate_tree(p))
            self._quick_layout.addWidget(btn)

    def _rebuild_adolar_bar(self):
        while self._adolar_bar_layout.count():
            item = self._adolar_bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        config = self._load_adolar_config()
        configured = bool(config.get('url') and config.get('token') and config.get('local_path'))
        if hasattr(self, 'adolar_sync_btn'):
            self.adolar_sync_btn.setVisible(configured and bool(config.get('sync_log')))
        if not configured:
            return

        btn = QPushButton("🚀  ADOLAR")
        font = QFont("Orbitron", 11)
        font.setBold(True)
        btn.setFont(font)
        btn.setStyleSheet(
            "QPushButton { text-align:left; background:#2a2140; color:#cba6f7;"
            " border:1px solid #45475a; border-radius:5px; padding:6px 10px; }"
            "QPushButton:hover { background:#3a2d5c; border-color:#cba6f7; }"
        )
        btn.setToolTip(f"{config.get('url', '')} — Bibliothek: {config.get('library_name') or config.get('library_id', '')}")
        btn.clicked.connect(self._on_adolar_bar_clicked)
        self._adolar_bar_layout.addWidget(btn)

    def _on_adolar_bar_clicked(self):
        config = self._load_adolar_config()
        url = config.get('url', '')
        token = config.get('token', '')
        local_path = config.get('local_path', '')
        if not (url and token and local_path):
            return
        try:
            r = requests.get(f"{url}/api/me", headers={'Authorization': f'Bearer {token}'}, timeout=5)
        except requests.exceptions.RequestException as e:
            QMessageBox.warning(self, "Adolar", f"Keine Verbindung zu {url} möglich.\n\n{e}")
            self._adolar_active = False
            return

        if r.status_code == 200 and r.json().get('role') == 'admin':
            self._adolar_active = True
            self.status_bar.showMessage(f"Adolar verbunden — {config.get('library_name', '')}")
        elif r.status_code in (401, 403):
            QMessageBox.warning(self, "Adolar",
                                 "Token ungültig oder abgelaufen. Bitte über Tools → Adolar-Verbindung prüfen.")
            self._adolar_active = False
            return
        else:
            QMessageBox.warning(self, "Adolar", f"Unerwartete Antwort von Adolar (HTTP {r.status_code}).")
            self._adolar_active = False
            return

        sync_log = config.get('sync_log', [])
        if sync_log:
            reply = QMessageBox.question(
                self, "Adolar",
                f"Es gibt {len(sync_log)} ungesyncte Änderung(en). Jetzt syncen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Discard,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._sync_pending_adolar_changes()
            elif reply == QMessageBox.StandardButton.Discard:
                self._save_adolar_config({'sync_log': []})
                self._rebuild_adolar_bar()

        if Path(local_path).is_dir():
            self._navigate_tree(local_path)

    def _translate_to_adolar_path(self, local_path):
        """Map a local filesystem path to the corresponding path on the Adolar
        side, using the local_path/adolar_path prefix pair from the config.
        Adolar paths are POSIX-style (server-side), so the mapped remainder
        uses forward slashes regardless of the local OS."""
        config = self._load_adolar_config()
        local_root = config.get('local_path', '')
        adolar_root = config.get('adolar_path', '')
        if not local_root or not adolar_root:
            return None
        local_path_norm = str(Path(local_path))
        local_root_norm = str(Path(local_root))
        if not local_path_norm.lower().startswith(local_root_norm.lower()):
            return None
        rel = local_path_norm[len(local_root_norm):].lstrip('\\/').replace('\\', '/')
        adolar_root_clean = adolar_root.rstrip('/')
        return f"{adolar_root_clean}/{rel}" if rel else adolar_root_clean

    def _notify_adolar_rescan(self, folder_path):
        """Queue a folder for a debounced rescan trigger — coalesces rapid
        successive edits into a single request per folder instead of firing
        one request per file write."""
        if not self._adolar_active or not folder_path:
            return
        self._adolar_pending_folders.add(folder_path)
        if self._adolar_debounce_timer is None:
            self._adolar_debounce_timer = QTimer(self)
            self._adolar_debounce_timer.setSingleShot(True)
            self._adolar_debounce_timer.timeout.connect(self._flush_adolar_rescan)
        self._adolar_debounce_timer.start(2500)

    def _flush_adolar_rescan(self):
        folders = list(self._adolar_pending_folders)
        self._adolar_pending_folders.clear()
        config = self._load_adolar_config()
        url = config.get('url', '')
        token = config.get('token', '')
        if not (url and token):
            return
        for folder in folders:
            adolar_path = self._translate_to_adolar_path(folder)
            if not adolar_path:
                continue
            try:
                r = requests.post(
                    f"{url}/api/scan/start",
                    headers={'Authorization': f'Bearer {token}'},
                    json={'path': adolar_path}, timeout=5,
                )
                if r.status_code == 200:
                    self._log_adolar_sync_success('rescan', {'path': adolar_path})
                else:
                    self._log_adolar_sync_failure('rescan', {'path': adolar_path, 'status': r.status_code})
            except requests.exceptions.RequestException:
                self._log_adolar_sync_failure('rescan', {'path': adolar_path})

    def _notify_adolar_renames(self, moves):
        """moves: list of (old_local_path, new_local_path) — called right after
        a successful rename/move so Adolar's DB stays in sync."""
        if not self._adolar_active or not moves:
            return
        config = self._load_adolar_config()
        url = config.get('url', '')
        token = config.get('token', '')
        library_id = config.get('library_id', '')
        if not (url and token and library_id):
            return
        for old_local, new_local in moves:
            old_adolar = self._translate_to_adolar_path(old_local)
            new_adolar = self._translate_to_adolar_path(new_local)
            if not old_adolar or not new_adolar:
                continue
            try:
                r = requests.post(
                    f"{url}/api/admin/libraries/{library_id}/rename-path",
                    headers={'Authorization': f'Bearer {token}'},
                    json={'old_path': old_adolar, 'new_path': new_adolar}, timeout=5,
                )
                if r.status_code == 200:
                    self._log_adolar_sync_success('rename', {'old_path': old_adolar, 'new_path': new_adolar})
                else:
                    self._log_adolar_sync_failure(
                        'rename', {'old_path': old_adolar, 'new_path': new_adolar, 'status': r.status_code})
            except requests.exceptions.RequestException:
                self._log_adolar_sync_failure('rename', {'old_path': old_adolar, 'new_path': new_adolar})

    def _log_adolar_sync_failure(self, kind, data):
        config = self._load_adolar_config()
        log = config.get('sync_log', [])
        entry = {'type': kind, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'), **data}
        log.append(entry)
        self._save_adolar_config({'sync_log': log})
        self._rebuild_adolar_bar()

    def _log_adolar_sync_success(self, kind, data):
        """Keep the last 20 successful syncs (newest first) for the
        'Letzte Syncs' view in AdolarConfigDialog."""
        config = self._load_adolar_config()
        history = config.get('sync_history', [])
        entry = {'type': kind, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'), **data}
        history.insert(0, entry)
        self._save_adolar_config({'sync_history': history[:20]})

    def _sync_pending_adolar_changes(self):
        config = self._load_adolar_config()
        url = config.get('url', '')
        token = config.get('token', '')
        library_id = config.get('library_id', '')
        log = config.get('sync_log', [])
        if not (url and token):
            self.status_bar.showMessage("Adolar nicht konfiguriert.")
            return
        if not log:
            self.status_bar.showMessage("Keine ungesyncten Änderungen.")
            return
        remaining = []
        synced = 0
        for entry in log:
            try:
                if entry.get('type') == 'rescan':
                    r = requests.post(
                        f"{url}/api/scan/start",
                        headers={'Authorization': f'Bearer {token}'},
                        json={'path': entry.get('path')}, timeout=5,
                    )
                elif entry.get('type') == 'rename' and library_id:
                    r = requests.post(
                        f"{url}/api/admin/libraries/{library_id}/rename-path",
                        headers={'Authorization': f'Bearer {token}'},
                        json={'old_path': entry.get('old_path'), 'new_path': entry.get('new_path')},
                        timeout=5,
                    )
                else:
                    remaining.append(entry)
                    continue
                if r.status_code == 200:
                    synced += 1
                    if entry.get('type') == 'rescan':
                        self._log_adolar_sync_success('rescan', {'path': entry.get('path')})
                    else:
                        self._log_adolar_sync_success(
                            'rename', {'old_path': entry.get('old_path'), 'new_path': entry.get('new_path')})
                else:
                    remaining.append(entry)
            except requests.exceptions.RequestException:
                remaining.append(entry)
        self._save_adolar_config({'sync_log': remaining})
        self._rebuild_adolar_bar()
        self.status_bar.showMessage(f"{synced} Änderung(en) synchronisiert, {len(remaining)} weiterhin offen.")

    def _load_favorites(self):
        return self._load_config().get('favorites', [])

    def _save_favorites(self, favs):
        self._save_config({'favorites': favs})

    def _show_tree_context_menu(self, pos):
        idx = self.tree_view.indexAt(pos)
        if not idx.isValid():
            return
        path = self.fs_model.filePath(idx)
        if not path or not Path(path).is_dir():
            return

        favs = self._load_favorites()
        is_fav = path in favs

        menu = QMenu(self)
        if is_fav:
            fav_action = menu.addAction("⭐ Aus Favoriten entfernen")
        else:
            fav_action = menu.addAction("⭐ Zu Favoriten hinzufügen")
        menu.addSeparator()
        del_action = menu.addAction("🗑  In Papierkorb löschen")

        chosen = menu.exec(self.tree_view.viewport().mapToGlobal(pos))
        if chosen == fav_action:
            if is_fav:
                favs.remove(path)
            else:
                favs.append(path)
            self._save_favorites(favs)
            self._rebuild_quick_access()
        elif chosen == del_action:
            name = Path(path).name
            reply = QMessageBox.question(
                self, "Löschen",
                f"'{name}' in den Papierkorb verschieben?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    from send2trash import send2trash
                    send2trash(str(Path(path)))
                    # Refresh tree
                    self.fs_model.setRootPath('')
                    self.status_bar.showMessage(f"'{name}' in den Papierkorb verschoben.")
                    if self._current_folder and self._current_folder.startswith(path):
                        self._current_folder = None
                        self.file_table.setRowCount(0)
                        self._files = []
                except Exception as e:
                    QMessageBox.warning(self, "Fehler", str(e))

    def _navigate_tree(self, path):
        """Expand all parent nodes, select and scroll to path."""
        def do_navigate():
            try:
                p = Path(path)
                # Expand every ancestor so the target becomes visible
                current = Path(p.parts[0])
                for part in p.parts[1:]:
                    current = current / part
                    idx = self.fs_model.index(str(current))
                    if idx.isValid():
                        self.tree_view.expand(idx)
                # Select and scroll
                idx = self.fs_model.index(path)
                if idx.isValid():
                    self.tree_view.setCurrentIndex(idx)
                    self.tree_view.setFocus()
                    QTimer.singleShot(100, _scroll)
            except Exception:
                pass

        def _scroll():
            idx = self.fs_model.index(path)
            if idx.isValid():
                self.tree_view.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtCenter)
                self.tree_view.setFocus()

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
        self.filetotag_btn.setEnabled(False)
        self.quick_filetotag_btn.setEnabled(False)
        self.autonumber_btn.setEnabled(False)
        self.bpm_btn.setEnabled(False)

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

    def _open_external_folder(self, path=None):
        """Activate this window and optionally load a folder received at launch."""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

        if not path:
            return
        try:
            valid = Path(path).is_dir()
        except OSError:
            valid = False
        if not valid:
            QMessageBox.warning(self, "Ordner nicht gefunden", f"Der Ordner ist nicht verfügbar:\n{path}")
            return
        normalized = os.path.normpath(path)
        self._navigate_tree(normalized)
        self._load_folder(normalized)

    def _handle_instance_message(self, message):
        if not isinstance(message, dict):
            return
        self._open_external_folder(message.get('folder'))

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

            # Col 0: cover indicator
            has_cover = tags.get('cover') is not None
            ci = QTableWidgetItem('♪' if has_cover else '')
            ci.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if has_cover:
                ci.setForeground(QColor('#a6e3a1'))
            self.file_table.setItem(i, 0, ci)

            # Col 1: track
            track = tags.get('tracknumber', '').split('/')[0]
            self.file_table.setItem(i, 1, QTableWidgetItem(track.zfill(2) if track else ''))

            # Col 2: filename + path in UserRole
            fi = QTableWidgetItem(mp3_path.name)
            fi.setData(Qt.ItemDataRole.UserRole, path_str)
            self.file_table.setItem(i, 2, fi)

            self.file_table.setItem(i, 3, QTableWidgetItem(tags.get('artist', '')))
            self.file_table.setItem(i, 4, QTableWidgetItem(tags.get('album', '')))
            self.file_table.setItem(i, 5, QTableWidgetItem(tags.get('title', '')))
            self.file_table.setItem(i, 6, QTableWidgetItem(tags.get('year', '')))
            self.file_table.setItem(i, 7, QTableWidgetItem(tags.get('genre', '')))
            self.file_table.setItem(i, 8, QTableWidgetItem(format_duration(tags.get('duration', 0))))
            self.file_table.setItem(i, 9, QTableWidgetItem(tags.get('album_artist', '')))
            self.file_table.setItem(i, 10, QTableWidgetItem(tags.get('bpm', '')))
            self.file_table.setItem(i, 11, QTableWidgetItem(str(tags.get('bitrate', ''))))
            self.file_table.setItem(i, 12, QTableWidgetItem(tags.get('comment', '')))
            self.file_table.setItem(i, 13, QTableWidgetItem(tags.get('label', '')))
            self.file_table.setItem(i, 14, QTableWidgetItem(tags.get('discnumber', '')))
            self.file_table.setItem(i, 15, QTableWidgetItem(tags.get('original_year', '')))

        self.file_table.setSortingEnabled(True)
        self._select_all()
        self.status_bar.showMessage(
            f"{len(raw)} MP3-Datei(en) geladen  —  {self._current_folder}"
        )

    def _get_selected_paths(self):
        """Return set of currently selected file paths."""
        paths = set()
        for idx in self.file_table.selectionModel().selectedRows():
            item = self.file_table.item(idx.row(), 2)
            if item:
                paths.add(item.data(Qt.ItemDataRole.UserRole))
        return paths

    def _reload_keep_selection(self):
        """Reload current folder but restore the previous selection afterwards."""
        if not self._current_folder:
            return
        self._notify_adolar_rescan(self._current_folder)
        prev = self._get_selected_paths()
        self._load_folder(self._current_folder)
        if prev:
            # After load, _select_all runs — override with previous selection
            QTimer.singleShot(0, lambda: self._restore_selection(prev))

    def _restore_selection(self, paths):
        self.file_table.clearSelection()
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 2)
            if item and item.data(Qt.ItemDataRole.UserRole) in paths:
                self.file_table.selectRow(row)
        self._on_selection_changed()

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
        self.filetotag_btn.setEnabled(has_sel)
        self.quick_filetotag_btn.setEnabled(has_sel)
        self.autonumber_btn.setEnabled(has_sel)
        self.bpm_btn.setEnabled(has_sel)
        self.move_up_btn.setEnabled(selected == 1)
        self.move_down_btn.setEnabled(selected == 1)
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

    def _move_file_row_up(self):
        self._move_file_row(-1)

    def _move_file_row_down(self):
        self._move_file_row(1)

    def _move_file_row(self, delta):
        rows = [idx.row() for idx in self.file_table.selectionModel().selectedRows()]
        if len(rows) != 1:
            return
        row = rows[0]
        target = row + delta
        if target < 0 or target >= self.file_table.rowCount():
            return
        was_sorting = self.file_table.isSortingEnabled()
        self.file_table.setSortingEnabled(False)
        for col in range(self.file_table.columnCount()):
            item_a = self.file_table.takeItem(row, col)
            item_b = self.file_table.takeItem(target, col)
            self.file_table.setItem(row, col, item_b)
            self.file_table.setItem(target, col, item_a)
        self.file_table.setSortingEnabled(was_sorting)
        self.file_table.selectRow(target)

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

    def _show_file_context_menu(self, pos):
        selected = self._get_selected_files()
        if not selected:
            return
        menu = QMenu(self)
        action = menu.addAction("🏷  Tag bearbeiten")
        if menu.exec(self.file_table.viewport().mapToGlobal(pos)):
            self._open_tag_editor(selected)

    def _open_tag_editor(self, files):
        if len(files) == 1:
            path, tags = files[0]
            fresh = load_mp3_tags(path)
            dlg = TagEditorDialog(path, fresh, parent=self)
            if dlg.exec() and self._current_folder:
                self._reload_keep_selection()
        else:
            dlg = BatchTagEditorDialog(files, parent=self)
            if dlg.exec() and self._current_folder:
                self._reload_keep_selection()

    def _on_file_double_clicked(self, index):
        path = self.file_table.item(index.row(), 2).data(Qt.ItemDataRole.UserRole)
        if path:
            self._open_tag_editor([(path, {})])

    def _sort_for_discogs(self, files):
        """Sort files by track tag (if present), else by natural filename order."""
        def key(item):
            path, tags = item
            track = tags.get('tracknumber', '').split('/')[0]
            if track.isdigit():
                return (0, int(track), Path(path).name.lower())
            return (1, 0, natural_sort_key(Path(path)))
        return sorted(files, key=key)

    def _open_discogs(self):
        selected = self._sort_for_discogs(self._get_selected_files())
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
            self._reload_keep_selection()
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
            self._reload_keep_selection()

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
        self._update_quick_rename_tooltip()
        if self._current_folder:
            self._reload_keep_selection()

    def _open_filetotag(self):
        selected = self._get_selected_files()
        if not selected:
            return
        fresh = [(path, load_mp3_tags(path)) for path, _ in selected]
        masks = self._load_filetotag_masks()
        last_mask = self._load_config().get('last_filetotag_mask', '')
        dlg = FileToTagDialog(fresh, masks=masks, last_mask=last_mask, parent=self)
        dlg.masks_changed.connect(self._save_filetotag_masks)
        dlg.exec()
        self._update_quick_filetotag_tooltip()
        if self._current_folder:
            self._reload_keep_selection()

    def _update_quick_filetotag_tooltip(self):
        mask = self._load_config().get('last_filetotag_mask', '')
        if not mask:
            masks = self._load_filetotag_masks()
            mask = masks[0] if masks else ''
        self.quick_filetotag_btn.setToolTip(f"Schnell Datei→Tag\nMaske: {mask}")

    def _quick_filetotag(self):
        """Extract tags from filename/path for selected files using the last saved mask."""
        selected = self._get_selected_files()
        if not selected:
            return
        mask = self._load_config().get('last_filetotag_mask', '')
        if not mask:
            masks = self._load_filetotag_masks()
            mask = masks[0] if masks else '%6-%2'
        fresh = [(p, load_mp3_tags(p)) for p, _ in selected]
        dlg = FileToTagDialog(fresh, masks=self._load_filetotag_masks(),
                              last_mask=mask, parent=self)
        dlg.mask_input.setCurrentText(mask)
        dlg._write_tags()
        self._update_quick_filetotag_tooltip()
        if self._current_folder:
            self._reload_keep_selection()

    def _set_undo(self, undo_info):
        self._last_undo = undo_info
        self.undo_btn.setEnabled(True)
        self.undo_btn.setToolTip(undo_info.get('label', 'Rückgängig machen'))

    def _undo_last_action(self):
        undo = self._last_undo
        if not undo:
            return
        errors = []
        if undo['type'] == 'tag_write':
            for path, old_tags in undo['entries']:
                ok = write_mp3_tags(path, old_tags)
                if not ok:
                    errors.append(Path(path).name)
        elif undo['type'] == 'rename':
            for old_path, new_path in reversed(undo['moves']):
                try:
                    Path(new_path).rename(old_path)
                except Exception as e:
                    errors.append(f"{Path(new_path).name}: {e}")
            for fj in undo.get('folder_jpg_created', []):
                try:
                    Path(fj).unlink(missing_ok=True)
                except Exception:
                    pass

        self._last_undo = None
        self.undo_btn.setEnabled(False)
        self.undo_btn.setToolTip('')

        msg = "Rückgängig gemacht."
        if errors:
            msg += f"  {len(errors)} Fehler: " + ", ".join(errors)
        self.status_bar.showMessage(msg)
        if self._current_folder:
            self._reload_keep_selection()

    def _open_replace_rules(self):
        rules = self._load_config().get('rename_replacements', [])
        dlg = ReplaceRulesDialog(rules, parent=self)
        dlg.exec()

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
            self._reload_keep_selection()
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
        self._cover_scan_dlg = CoverScanDialog(scan_root, parent=self)
        self._cover_scan_dlg.load_folder.connect(self._load_folder)
        self._cover_scan_dlg.show()

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
        dlg._do_rename()
        self._update_quick_rename_tooltip()
        # Reload — files may have moved to a different folder
        if self._current_folder:
            self._reload_keep_selection()

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
            self._reload_keep_selection()
        msg = f"# {total} Dateien nummeriert (1–{total}, {width}-stellig)."
        if errors:
            msg += f"  {len(errors)} Fehler."
        self.status_bar.showMessage(msg)

    def _save_column_order(self):
        hh = self.file_table.horizontalHeader()
        order = [hh.logicalIndex(v) for v in range(hh.count())]
        self._save_config({'column_order': order})

    def _show_column_menu(self, pos):
        menu = QMenu(self)
        # Only allow toggling columns 3+ (first 3 are always visible)
        for i, (hdr, _, _, _) in enumerate(self.COLUMNS):
            if i < 3:
                continue
            action = menu.addAction(hdr)
            action.setCheckable(True)
            action.setChecked(self._col_visible.get(i, True))
            action.setData(i)
        chosen = menu.exec(self.file_table.horizontalHeader().mapToGlobal(pos))
        if chosen:
            col = chosen.data()
            visible = chosen.isChecked()
            self._col_visible[col] = visible
            self.file_table.setColumnHidden(col, not visible)
            # Persist
            self._save_config({'column_visibility': {str(k): v for k, v in self._col_visible.items()}})

    def _calculate_bpm(self):
        selected = self._get_selected_files()
        if not selected:
            return
        self.bpm_btn.setEnabled(False)
        self.status_bar.showMessage(f"Berechne BPM für {len(selected)} Datei(en)…")
        self._bpm_thread = BpmCalculationThread(selected)
        self._bpm_thread.progress.connect(self._on_bpm_progress)
        self._bpm_thread.finished.connect(self._on_bpm_done)
        self._bpm_thread.start()

    def _on_bpm_progress(self, done, total, filename):
        self.status_bar.showMessage(f"BPM {done+1}/{total}: {filename}")

    def _on_bpm_done(self, written, skipped):
        self.bpm_btn.setEnabled(True)
        self.status_bar.showMessage(
            f"BPM fertig — {written} geschrieben, {skipped} übersprungen (bereits vorhanden)"
        )
        if self._current_folder:
            self._reload_keep_selection()

    def _open_about(self):
        import webbrowser
        dlg = QDialog(self)
        dlg.setWindowTitle("Über Adolar Taggster")
        dlg.setFixedSize(340, 260)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Adolar Taggster")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #89b4fa;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        for text, style in [
            ("Version: 2.0", "color: #a6adc8; font-size: 12px;"),
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

        mail_btn = QPushButton("adolartaggster@polze.net")
        mail_btn.setStyleSheet("QPushButton { background:transparent; color:#89b4fa; border:none; font-size:12px; text-decoration:underline; } QPushButton:hover { color:#b4d0ff; }")
        mail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mail_btn.clicked.connect(lambda: webbrowser.open("mailto:adolartaggster@polze.net"))
        layout.addWidget(mail_btn)

        layout.addStretch()
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)

        dlg.exec()

    def _open_settings(self):
        numeric_track = self._load_config().get('numeric_track_display', False)
        dlg = SettingsDialog(self._discogs_token, numeric_track, parent=self)
        if dlg.exec():
            self._discogs_token = dlg.get_token()
            self._save_token(self._discogs_token)
            self._save_config({'numeric_track_display': dlg.get_numeric_track()})

    def _open_adolar_config(self):
        config = self._load_adolar_config()
        dlg = AdolarConfigDialog(config, parent=self)
        if dlg.exec():
            new_config = dlg.get_config()
            if new_config:
                self._save_adolar_config(new_config)
            if hasattr(self, '_rebuild_adolar_bar'):
                self._rebuild_adolar_bar()


def _create_icon_image(size=64):
    """Generate the Taggster icon as a Pillow image."""
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
    if size != 64:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img


def _make_icon():
    """Generate app icon programmatically via Pillow."""
    try:
        img = _create_icon_image()
        buf = BytesIO()
        img.save(buf, format='PNG')
        pix = QPixmap()
        pix.loadFromData(buf.getvalue())
        return QIcon(pix)
    except Exception:
        return QIcon()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle('Fusion')        # must come before setStyleSheet
    app.setStyleSheet(DARK_STYLE)

    folder = _folder_from_arguments(sys.argv[1:])
    instance = SingleInstanceController(app)
    message = {'action': 'open', 'folder': folder}
    if instance.send_to_primary(message):
        return 0
    if not instance.listen():
        # Another copy may have won a simultaneous-start race. Try it once more.
        if instance.send_to_primary(message, timeout=1500):
            return 0
        QMessageBox.critical(
            None, APP_NAME,
            "Taggster konnte die Kommunikation mit der bereits laufenden Instanz nicht öffnen.")
        return 1

    window = MainWindow()
    window.setWindowIcon(_make_icon())
    instance.message_received.connect(window._handle_instance_message)
    window.show()
    if folder:
        QTimer.singleShot(0, lambda: window._open_external_folder(folder))
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
