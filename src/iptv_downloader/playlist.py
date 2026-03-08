"""
Модуль для работы с IPTV плейлистами.
Загрузка, парсинг и сохранение плейлистов формата M3U/M3U8.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple

import requests

from .config import DEFAULT_TIMEOUT, HISTORY_DIR, LINKS_FILE, USER_AGENT
from .models import Channel, PlaylistInfo


def validate_url(url: str) -> bool:
    """
    Проверить корректность URL.
    
    Args:
        url: Строка URL для проверки.
        
    Returns:
        True если URL начинается с http:// или https://
    """
    return url.startswith("http://") or url.startswith("https://")


def download_playlist(url: str, save_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Скачать плейлист по URL и сохранить в директорию.
    
    Args:
        url: URL плейлиста.
        save_dir: Директория для сохранения (по умолчанию HISTORY_DIR).
        
    Returns:
        Путь к сохранённому файлу или None при ошибке.
    """
    if save_dir is None:
        save_dir = HISTORY_DIR
    
    save_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            url, 
            timeout=DEFAULT_TIMEOUT, 
            allow_redirects=True,
            headers=headers
        )
        response.raise_for_status()
        
        # Определить расширение по содержимому или URL
        content_type = response.headers.get("Content-Type", "").lower()
        if ".m3u8" in url or "m3u8" in content_type:
            extension = ".m3u8"
        else:
            extension = ".m3u"
        
        # Создать имя файла с датой
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"playlist_{timestamp}{extension}"
        filepath = save_dir / filename
        
        # Сохранить файл
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(response.text)
        
        return filepath
        
    except requests.RequestException as e:
        return None
    except IOError:
        return None


def extract_epg_url(content: str) -> Optional[str]:
    """
    Извлечь URL EPG из содержимого плейлиста.
    
    Args:
        content: Содержимое плейлиста.
        
    Returns:
        URL EPG или None.
    """
    match = re.search(r'url-tvg="([^"]*)"', content)
    return match.group(1) if match else None


def parse_m3u_playlist(filepath: Path) -> Tuple[List[Channel], Optional[str]]:
    """
    Распарсить M3U/M3U8 плейлист и извлечь список каналов.
    
    Args:
        filepath: Путь к файлу плейлиста.
        
    Returns:
        Кортеж (список каналов, EPG URL).
    """
    channels: List[Channel] = []
    epg_url: Optional[str] = None
    
    try:
        # Пробуем разные кодировки
        content = None
        for encoding in ["utf-8", "latin-1", "cp1251"]:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            return [], None
        
        # Извлечь EPG URL из плейлиста
        epg_url = extract_epg_url(content)
        
        # Разбить на строки
        lines = content.strip().split("\n")
        current_channel: dict = {}
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            if line.startswith("#EXTINF:"):
                # Парсить метаданные канала
                current_channel = {
                    "name": "",
                    "url": "",
                    "logo": "",
                    "group": "",
                    "tvg_id": "",
                    "tvg_rec": 0,
                }
                
                # Извлечь название канала (после последней запятой)
                if "," in line:
                    name_part = line.split(",")[-1].strip()
                    current_channel["name"] = name_part
                
                # Извлечь логотип
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                if logo_match:
                    current_channel["logo"] = logo_match.group(1)
                
                # Извлечь группу
                group_match = re.search(r'group-title="([^"]*)"', line)
                if group_match:
                    current_channel["group"] = group_match.group(1)
                
                # Извлечь tvg-id
                tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
                if tvg_id_match:
                    current_channel["tvg_id"] = tvg_id_match.group(1)
                
                # Извлечь tvg-rec (архив в днях)
                tvg_rec_match = re.search(r'tvg-rec="(\d+)"', line)
                if tvg_rec_match:
                    current_channel["tvg_rec"] = int(tvg_rec_match.group(1))
            
            elif line.startswith("#"):
                continue
            
            elif line.startswith("http://") or line.startswith("https://"):
                # Это URL потока
                if current_channel:
                    current_channel["url"] = line
                    channels.append(Channel.from_dict(current_channel))
                    current_channel = {}
    
    except Exception:
        pass
    
    return channels, epg_url


def save_playlist_info(info: PlaylistInfo) -> bool:
    """
    Сохранить информацию о плейлисте в историю.
    
    Args:
        info: Информация о плейлисте.
        
    Returns:
        True при успехе.
    """
    import yaml
    
    history: List[dict] = []
    
    # Загрузить существующую историю
    if LINKS_FILE.exists():
        try:
            with open(LINKS_FILE, "r", encoding="utf-8") as f:
                history = yaml.safe_load(f) or []
        except Exception:
            history = []
    
    # Добавить новую запись
    history.append(info.to_dict())
    
    # Сохранить
    try:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        with open(LINKS_FILE, "w", encoding="utf-8") as f:
            yaml.dump(history, f, allow_unicode=True, default_flow_style=False)
        return True
    except Exception:
        return False


def load_playlist_history() -> List[PlaylistInfo]:
    """
    Загрузить историю плейлистов.
    
    Returns:
        Список информации о плейлистах.
    """
    import yaml
    
    history: List[PlaylistInfo] = []
    
    if LINKS_FILE.exists():
        try:
            with open(LINKS_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or []
            for item in data:
                history.append(PlaylistInfo.from_dict(item))
        except Exception:
            pass
    
    return history
