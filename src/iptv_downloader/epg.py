"""
Модуль для работы с EPG (электронной программой передач).
Загрузка, кэширование и парсинг XMLTV формата.
"""

import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List

import requests
import yaml

from .config import (
    DEFAULT_TIMEOUT,
    EPG_FILE,
    EPG_CACHE_FILE,
    EPG_CACHE_HOURS,
    HISTORY_DIR,
    USER_AGENT,
)
from .models import Program


def download_epg(epg_url: str) -> bool:
    """
    Скачать EPG данные и сохранить в кэш.
    
    Args:
        epg_url: URL для загрузки EPG.
        
    Returns:
        True при успехе.
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            epg_url,
            timeout=DEFAULT_TIMEOUT,
            stream=True,
            headers=headers,
        )
        response.raise_for_status()
        
        # Сохранить сжатый файл
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        with open(EPG_FILE, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Сохранить метаданные кэша
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "url": epg_url,
            "size": EPG_FILE.stat().st_size if EPG_FILE.exists() else 0,
        }
        with open(EPG_CACHE_FILE, "w", encoding="utf-8") as f:
            yaml.dump(cache_data, f, allow_unicode=True)
        
        return True
        
    except Exception:
        return False


def is_epg_cache_valid() -> bool:
    """
    Проверить актуальность кэша EPG.
    
    Returns:
        True если кэш действителен (не старше EPG_CACHE_HOURS).
    """
    if not EPG_CACHE_FILE.exists() or not EPG_FILE.exists():
        return False
    
    try:
        with open(EPG_CACHE_FILE, "r", encoding="utf-8") as f:
            cache_data = yaml.safe_load(f)
        
        if not cache_data:
            return False
        
        timestamp = datetime.fromisoformat(cache_data.get("timestamp", ""))
        age = datetime.now() - timestamp
        
        return age.total_seconds() < EPG_CACHE_HOURS * 3600
        
    except Exception:
        return False


def load_epg_data(epg_url: Optional[str] = None) -> Optional[Dict[str, List[Program]]]:
    """
    Загрузить данные EPG.
    Использует кэш если он актуален, иначе загружает заново.
    
    Args:
        epg_url: URL для загрузки (если нужно обновить кэш).
        
    Returns:
        Словарь {channel_id: [programs]} или None.
    """
    # Проверить кэш
    if is_epg_cache_valid() and not epg_url:
        return parse_epg_file(EPG_FILE)
    
    # Загрузить новый EPG
    if epg_url:
        if download_epg(epg_url):
            return parse_epg_file(EPG_FILE)
    elif EPG_FILE.exists():
        # Использовать старый файл если URL не указан
        return parse_epg_file(EPG_FILE)
    
    return None


def parse_epg_file(filepath: Path) -> Optional[Dict[str, List[Program]]]:
    """
    Распарсить XMLTV файл EPG.
    
    Args:
        filepath: Путь к файлу EPG.
        
    Returns:
        Словарь {channel_id: [programs]} или None.
    """
    try:
        # Открыть файл (сжатый или нет)
        if str(filepath).endswith(".gz"):
            f = gzip.open(filepath, "rb")
        else:
            f = open(filepath, "rb")
        
        content = f.read()
        f.close()
        
        # Распарсить XML
        root = ET.fromstring(content)
        
        # Собрать каналы
        channels: Dict[str, str] = {}
        for channel in root.findall(".//channel"):
            channel_id = channel.get("id")
            if channel_id:
                display_name = channel.find("display-name")
                channels[channel_id] = display_name.text if display_name is not None else channel_id
        
        # Собрать программы
        programs: Dict[str, List[Program]] = {ch_id: [] for ch_id in channels}
        
        for programme in root.findall(".//programme"):
            channel_id = programme.get("channel")
            if channel_id and channel_id in programs:
                title_elem = programme.find("title")
                desc_elem = programme.find("desc")
                icon_elem = programme.find("icon")
                
                # Парсить время
                start = _parse_epg_time(programme.get("start", ""))
                stop = _parse_epg_time(programme.get("stop", ""))
                
                program = Program(
                    title=title_elem.text if title_elem is not None else "Без названия",
                    start=start,
                    stop=stop,
                    description=desc_elem.text if desc_elem is not None else "",
                    icon=icon_elem.get("src") if icon_elem is not None else "",
                    channel_id=channel_id,
                )
                programs[channel_id].append(program)
        
        return programs
        
    except Exception:
        return None


def _parse_epg_time(time_str: str) -> Optional[datetime]:
    """
    Распарсить время в формате XMLTV.
    
    Args:
        time_str: Строка времени в формате YYYYMMDDHHMMSS +ZONE.
        
    Returns:
        datetime или None.
    """
    if not time_str or len(time_str) < 14:
        return None
    
    try:
        # Формат: 20240101120000 +0300
        time_part = time_str[:14]
        return datetime.strptime(time_part, "%Y%m%d%H%M%S")
    except ValueError:
        return None


def get_programs_for_channel(
    epg_data: Dict[str, List[Program]],
    tvg_id: str,
    channel_name: str,
) -> List[Program]:
    """
    Получить программы для конкретного канала.
    
    Args:
        epg_data: Данные EPG.
        tvg_id: TVG ID канала.
        channel_name: Имя канала для поиска.
        
    Returns:
        Список программ.
    """
    if tvg_id and tvg_id in epg_data:
        return epg_data[tvg_id]
    
    # Поиск по имени канала
    channel_name_lower = channel_name.lower()
    for ch_id, progs in epg_data.items():
        # Имя канала может быть в первой программе
        if progs:
            # Проверяем channel_id
            if channel_name_lower in ch_id.lower():
                return progs
    
    return []


def filter_programs_by_date(
    programs: List[Program],
    days_ago: int = 0,
) -> List[Program]:
    """
    Отфильтровать программы по дате.
    
    Args:
        programs: Список программ.
        days_ago: Сколько дней назад (0 = сегодня, 1 = вчера).
        
    Returns:
        Отфильтрованный список программ.
    """
    target_date = (datetime.now() - timedelta(days=days_ago)).date()
    
    result = []
    for program in programs:
        if program.start and program.start.date() == target_date:
            result.append(program)
    
    return result


def get_programs_for_period(
    programs: List[Program],
    period: str = "all",
) -> List[Program]:
    """
    Получить программы за период.
    
    Args:
        programs: Список программ.
        period: 'yesterday', 'today', или 'all'.
        
    Returns:
        Отфильтрованный список программ.
    """
    if period == "yesterday":
        return filter_programs_by_date(programs, days_ago=1)
    elif period == "today":
        return filter_programs_by_date(programs, days_ago=0)
    else:
        return programs
