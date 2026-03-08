"""
Точка входа для запуска как модуля: python -m iptv_downloader
"""

from .app import IPTVDownloader


def main():
    """Запустить приложение."""
    downloader = IPTVDownloader()
    downloader.run()


if __name__ == "__main__":
    main()
