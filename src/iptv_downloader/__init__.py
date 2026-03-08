"""
IPTV Downloader - Скрипт для скачивания IPTV потоков.

Пакет для загрузки и записи видео из IPTV плейлистов.
"""

from .config import __version__
from .app import IPTVDownloader

__all__ = ["IPTVDownloader", "__version__"]
