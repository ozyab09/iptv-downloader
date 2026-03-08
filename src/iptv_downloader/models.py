"""
Модели данных для IPTV Downloader.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class Channel:
    """Модель IPTV канала."""
    name: str
    url: str
    logo: str = ""
    group: str = ""
    tvg_id: str = ""
    tvg_rec: int = 0  # Доступность архива в днях
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь."""
        return {
            "name": self.name,
            "url": self.url,
            "logo": self.logo,
            "group": self.group,
            "tvg_id": self.tvg_id,
            "tvg_rec": self.tvg_rec,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Channel":
        """Создать из словаря."""
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            logo=data.get("logo", ""),
            group=data.get("group", ""),
            tvg_id=data.get("tvg_id", ""),
            tvg_rec=int(data.get("tvg_rec", 0)),
        )


@dataclass
class Program:
    """Модель телепрограммы (EPG)."""
    title: str
    start: datetime
    stop: Optional[datetime] = None
    description: str = ""
    icon: str = ""
    channel_id: str = ""
    
    @property
    def duration(self) -> int:
        """Длительность программы в секундах."""
        if self.stop and self.start:
            return int((self.stop - self.start).total_seconds())
        return 0
    
    @property
    def start_formatted(self) -> str:
        """Форматированное время начала."""
        if self.start:
            return self.start.strftime("%d.%m %H:%M")
        return ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь."""
        return {
            "title": self.title,
            "start": self.start.isoformat() if self.start else "",
            "stop": self.stop.isoformat() if self.stop else "",
            "description": self.description,
            "icon": self.icon,
            "channel_id": self.channel_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Program":
        """Создать из словаря."""
        start = None
        stop = None
        try:
            if data.get("start"):
                start = datetime.fromisoformat(data["start"])
            if data.get("stop"):
                stop = datetime.fromisoformat(data["stop"])
        except ValueError:
            pass
        
        return cls(
            title=data.get("title", ""),
            start=start,
            stop=stop,
            description=data.get("description", ""),
            icon=data.get("icon", ""),
            channel_id=data.get("channel_id", ""),
        )


@dataclass
class StreamQuality:
    """Модель качества потока."""
    quality: str  # Например: "1080p", "720p", "best"
    url: str
    bandwidth: int = 0  # Битрейт в битах в секунду
    width: int = 0  # Ширина видео
    height: int = 0  # Высота видео
    
    @property
    def resolution(self) -> str:
        """Разрешение в формате WxH."""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return self.quality
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь."""
        return {
            "quality": self.quality,
            "url": self.url,
            "bandwidth": self.bandwidth,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class PlaylistInfo:
    """Информация о загруженном плейлисте."""
    url: str
    filepath: str
    timestamp: datetime
    channels_count: int = 0
    epg_url: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь."""
        return {
            "url": self.url,
            "filepath": self.filepath,
            "timestamp": self.timestamp.isoformat(),
            "channels_count": self.channels_count,
            "epg_url": self.epg_url,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaylistInfo":
        """Создать из словаря."""
        timestamp = data.get("timestamp", "")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                timestamp = datetime.now()
        
        return cls(
            url=data.get("url", ""),
            filepath=data.get("filepath", ""),
            timestamp=timestamp,
            channels_count=int(data.get("channels_count", 0)),
            epg_url=data.get("epg_url", ""),
        )


@dataclass
class RecordingStatus:
    """Статус активной записи."""
    is_active: bool
    message: str
    elapsed_seconds: int = 0
    remaining_seconds: int = 0
    output_path: str = ""
    
    def __str__(self) -> str:
        return self.message
