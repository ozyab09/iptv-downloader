"""
Конфигурация и константы проекта IPTV Downloader.
"""

from pathlib import Path
from typing import Final

# Версия приложения
__version__: Final = "1.0.0"

# Базовые директории
BASE_DIR: Final = Path(__file__).parent.parent.parent.resolve()
HISTORY_DIR: Final = BASE_DIR / "history"
DOWNLOADS_DIR: Final = BASE_DIR / "downloads"

# Файлы
LINKS_FILE: Final = HISTORY_DIR / "links.yml"
EPG_FILE: Final = HISTORY_DIR / "epg.xml.gz"
EPG_CACHE_FILE: Final = HISTORY_DIR / "epg_cache.yml"
ERROR_LOG: Final = BASE_DIR / "error.log"

# Таймауты и ограничения
DEFAULT_TIMEOUT: Final = 30  # секунд для HTTP запросов
MAX_FILE_SIZE_GB: Final = 10  # предупреждение о размере файла
EPG_CACHE_HOURS: Final = 6  # время кэширования EPG

# HTTP заголовки
USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Паттерны для валидации
URL_PATTERN: Final = r"^https?://"

# FFmpeg настройки
FFMPEG_DEFAULT_ARGS: Final = [
    "-c", "copy",  # Копировать без перекодирования
    "-bsf:a", "aac_adtstoasc",  # Конвертировать аудио битстрим
    "-movflags", "+faststart",  # Оптимизировать для воспроизведения
]

# FFmpeg HLS flags для потоков
FFMPEG_HLS_FLAGS: Final = [
    "-fflags", "+discard_corrupt",  # Отбрасывать повреждённые пакеты
    "-flags", "+low_delay",  # Низкая задержка
    "-strict", "experimental",  # Разрешить экспериментальные кодеки
    "-rw_timeout", "30000000",  # Таймаут чтения 30 секунд (в микросекундах)
    "-allowed_extensions", "ALL",  # Разрешить все расширения для HLS сегментов
    "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",  # User-Agent
    "-referer", "http://allway.tv/",  # Referer
]


def ensure_directories() -> None:
    """Создать необходимые директории если они не существуют."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
