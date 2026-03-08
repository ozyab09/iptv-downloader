"""
Вспомогательные утилиты.
Работа с файлами, именами, дисковым пространством.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Optional, Tuple

from .config import MAX_FILE_SIZE_GB


def sanitize_filename(filename: str) -> str:
    """
    Очистить имя файла от недопустимых символов.
    
    Args:
        filename: Исходное имя файла.
        
    Returns:
        Безопасное имя файла.
    """
    # Заменить недопустимые символы на подчеркивание
    invalid_chars = r'[<>:"/\\|？*]'
    sanitized = re.sub(invalid_chars, "_", filename)
    
    # Удалить control characters
    sanitized = "".join(c for c in sanitized if ord(c) >= 32)
    
    # Обрезать длинные имена
    if len(sanitized) > 200:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[: 200 - len(ext)] + ext
    
    return sanitized.strip()


def get_unique_filepath(filepath: Path) -> Path:
    """
    Получить уникальный путь к файлу, добавляя суффикс при конфликте имен.
    
    Args:
        filepath: Исходный путь к файлу.
        
    Returns:
        Уникальный путь.
    """
    if not filepath.exists():
        return filepath
    
    counter = 1
    stem = filepath.stem
    suffix = filepath.suffix
    directory = filepath.parent
    
    while True:
        new_filepath = directory / f"{stem}_{counter}{suffix}"
        if not new_filepath.exists():
            return new_filepath
        counter += 1


def get_available_disk_space(path: Path) -> int:
    """
    Получить свободное место на диске в байтах.
    
    Args:
        path: Путь для проверки.
        
    Returns:
        Количество свободных байт.
    """
    try:
        return shutil.disk_usage(path).free
    except Exception:
        return float("inf")  # Если не удалось определить, считать бесконечным


def bytes_to_gb(bytes_val: int) -> float:
    """
    Конвертировать байты в гигабайты.
    
    Args:
        bytes_val: Количество байт.
        
    Returns:
        Количество гигабайт.
    """
    return bytes_val / (1024**3)


def bytes_to_mb(bytes_val: int) -> float:
    """
    Конвертировать байты в мегабайты.
    
    Args:
        bytes_val: Количество байт.
        
    Returns:
        Количество мегабайт.
    """
    return bytes_val / (1024**2)


def format_duration(seconds: int) -> str:
    """
    Форматировать длительность в читаемый вид.
    
    Args:
        seconds: Длительность в секундах.
        
    Returns:
        Форматированная строка.
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}ч {minutes}м {secs}с"
    elif minutes > 0:
        return f"{minutes}м {secs}с"
    else:
        return f"{secs}с"


def estimate_file_size(duration_seconds: int, bitrate_mbps: float = 5.0) -> int:
    """
    Оценить размер файла для записи.
    
    Args:
        duration_seconds: Длительность в секундах.
        bitrate_mbps: Битрейт в Мбит/с (по умолчанию 5).
        
    Returns:
        Примерный размер в байтах.
    """
    # Битрейт в байтах в секунду
    bytes_per_second = (bitrate_mbps * 1024 * 1024) / 8
    return int(duration_seconds * bytes_per_second)


def check_disk_space(
    path: Path,
    required_bytes: int,
    warning_threshold_gb: float = MAX_FILE_SIZE_GB,
) -> Tuple[bool, Optional[str]]:
    """
    Проверить наличие места на диске.
    
    Args:
        path: Путь для проверки.
        required_bytes: Требуемое количество байт.
        warning_threshold_gb: Порог для предупреждения в ГБ.
        
    Returns:
        Кортеж (успех, сообщение об ошибке).
    """
    available = get_available_disk_space(path)
    
    # Проверка на превышение порога
    required_gb = bytes_to_gb(required_bytes)
    if required_gb > warning_threshold_gb:
        return False, f"Размер файла ({required_gb:.1f} ГБ) превышает лимит ({warning_threshold_gb} ГБ)"
    
    # Проверка наличия места
    if required_bytes > available:
        available_gb = bytes_to_gb(available)
        return False, f"Недостаточно места (требуется {required_gb:.1f} ГБ, доступно {available_gb:.1f} ГБ)"
    
    return True, None


def cleanup_temp_files(directory: Path, pattern: str = "*.tmp") -> int:
    """
    Очистить временные файлы.
    
    Args:
        directory: Директория для очистки.
        pattern: Паттерн имён файлов.
        
    Returns:
        Количество удалённых файлов.
    """
    count = 0
    for filepath in directory.glob(pattern):
        try:
            filepath.unlink()
            count += 1
        except Exception:
            pass
    return count


def get_file_size(filepath: Path) -> Optional[int]:
    """
    Получить размер файла в байтах.
    
    Args:
        filepath: Путь к файлу.
        
    Returns:
        Размер файла или None.
    """
    try:
        return filepath.stat().st_size
    except Exception:
        return None


def format_file_size(size_bytes: int) -> str:
    """
    Форматировать размер файла в читаемый вид.
    
    Args:
        size_bytes: Размер в байтах.
        
    Returns:
        Форматированная строка.
    """
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} КБ"
    elif size_bytes < 1024**3:
        return f"{size_bytes / (1024**2):.1f} МБ"
    else:
        return f"{size_bytes / (1024**3):.1f} ГБ"
