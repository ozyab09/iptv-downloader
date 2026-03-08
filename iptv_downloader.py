#!/usr/bin/env python3
"""
IPTV Downloader - Скрипт для скачивания IPTV потоков.
Точка входа для запуска из корня проекта.
"""

import sys
from pathlib import Path

# Добавить src в путь
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from iptv_downloader import IPTVDownloader


def main():
    """Запустить приложение."""
    downloader = IPTVDownloader()
    downloader.run()


if __name__ == "__main__":
    main()
