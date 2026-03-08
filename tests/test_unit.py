"""
Unit тесты для IPTV Downloader.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iptv_downloader.models import Channel, Program, StreamQuality, PlaylistInfo
from iptv_downloader.utils import (
    sanitize_filename,
    get_unique_filepath,
    format_duration,
    bytes_to_gb,
    bytes_to_mb,
    estimate_file_size,
)
from iptv_downloader.playlist import validate_url, extract_epg_url
from iptv_downloader.epg import _parse_epg_time, filter_programs_by_date


# =============================================================================
# Тесты моделей
# =============================================================================

class TestChannel:
    """Тесты модели Channel."""
    
    def test_create_channel(self):
        channel = Channel(
            name="Test Channel",
            url="http://example.com/stream.m3u8",
            group="Entertainment",
        )
        assert channel.name == "Test Channel"
        assert channel.url == "http://example.com/stream.m3u8"
        assert channel.group == "Entertainment"
    
    def test_channel_to_dict(self):
        channel = Channel(
            name="Test",
            url="http://test.com",
            tvg_id="123",
        )
        data = channel.to_dict()
        assert data["name"] == "Test"
        assert data["url"] == "http://test.com"
        assert data["tvg_id"] == "123"
    
    def test_channel_from_dict(self):
        data = {
            "name": "Test Channel",
            "url": "http://test.com",
            "logo": "http://test.com/logo.png",
            "group": "News",
            "tvg_id": "456",
            "tvg_rec": 7,
        }
        channel = Channel.from_dict(data)
        assert channel.name == "Test Channel"
        assert channel.tvg_id == "456"
        assert channel.tvg_rec == 7


class TestProgram:
    """Тесты модели Program."""
    
    def test_program_duration(self):
        start = datetime(2024, 1, 1, 10, 0)
        stop = datetime(2024, 1, 1, 11, 30)
        program = Program(title="Test", start=start, stop=stop)
        assert program.duration == 5400  # 1.5 часа в секундах
    
    def test_program_start_formatted(self):
        start = datetime(2024, 1, 15, 14, 30)
        program = Program(title="Test", start=start)
        assert program.start_formatted == "15.01 14:30"
    
    def test_program_to_dict(self):
        start = datetime(2024, 1, 1, 10, 0)
        program = Program(title="Show", start=start)
        data = program.to_dict()
        assert data["title"] == "Show"
        assert "start" in data


class TestStreamQuality:
    """Тесты модели StreamQuality."""
    
    def test_resolution_property(self):
        quality = StreamQuality(
            quality="720p",
            url="http://test.com",
            width=1280,
            height=720,
        )
        assert quality.resolution == "1280x720"
    
    def test_resolution_fallback(self):
        quality = StreamQuality(
            quality="best",
            url="http://test.com",
        )
        assert quality.resolution == "best"


class TestPlaylistInfo:
    """Тесты модели PlaylistInfo."""
    
    def test_playlist_info_to_dict(self):
        info = PlaylistInfo(
            url="http://test.com/playlist.m3u",
            filepath="/path/to/playlist.m3u",
            timestamp=datetime(2024, 1, 1, 12, 0),
            channels_count=100,
        )
        data = info.to_dict()
        assert data["url"] == "http://test.com/playlist.m3u"
        assert data["channels_count"] == 100


# =============================================================================
# Тесты утилит
# =============================================================================

class TestSanitizeFilename:
    """Тесты функции sanitize_filename."""
    
    def test_remove_invalid_chars(self):
        assert sanitize_filename("file<name>.txt") == "file_name_.txt"
        assert sanitize_filename('file"name.txt') == "file_name.txt"
    
    def test_trim_long_name(self):
        long_name = "a" * 250 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 200
        assert result.endswith(".txt")
    
    def test_strip_whitespace(self):
        assert sanitize_filename("  file name  ") == "file name"


class TestFormatDuration:
    """Тесты функции format_duration."""
    
    def test_seconds_only(self):
        assert format_duration(30) == "30с"
    
    def test_minutes_and_seconds(self):
        assert format_duration(90) == "1м 30с"
    
    def test_hours_minutes_seconds(self):
        assert format_duration(3665) == "1ч 1м 5с"


class TestBytesConversion:
    """Тесты конвертации байт."""
    
    def test_bytes_to_gb(self):
        assert bytes_to_gb(1024**3) == 1.0
        assert bytes_to_gb(2 * 1024**3) == 2.0
    
    def test_bytes_to_mb(self):
        assert bytes_to_mb(1024**2) == 1.0
        assert bytes_to_mb(500 * 1024**2) == 500.0


class TestEstimateFileSize:
    """Тесты оценки размера файла."""
    
    def test_estimate_size(self):
        # 1 час при 5 Мбит/с ≈ 2.25 ГБ
        size = estimate_file_size(3600, 5.0)
        assert size > 2 * 1024**3  # Больше 2 ГБ
        assert size < 3 * 1024**3  # Меньше 3 ГБ


# =============================================================================
# Тесты плейлистов
# =============================================================================

class TestValidateUrl:
    """Тесты валидации URL."""
    
    def test_valid_http(self):
        assert validate_url("http://example.com") is True
    
    def test_valid_https(self):
        assert validate_url("https://example.com") is True
    
    def test_invalid_url(self):
        assert validate_url("ftp://example.com") is False
        assert validate_url("example.com") is False
        assert validate_url("") is False


class TestExtractEpgUrl:
    """Тесты извлечения EPG URL."""
    
    def test_extract_from_header(self):
        content = '#EXTM3U url-tvg="http://epg.example.com/guide.xml"'
        assert extract_epg_url(content) == "http://epg.example.com/guide.xml"
    
    def test_no_epg_url(self):
        content = "#EXTM3U\n#EXTINF:0,Channel"
        assert extract_epg_url(content) is None


# =============================================================================
# Тесты EPG
# =============================================================================

class TestParseEpgTime:
    """Тесты парсинга времени EPG."""
    
    def test_parse_valid_time(self):
        result = _parse_epg_time("20240115143000 +0300")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30
    
    def test_parse_invalid_time(self):
        assert _parse_epg_time("") is None
        assert _parse_epg_time("invalid") is None
        assert _parse_epg_time("2024") is None


class TestFilterProgramsByDate:
    """Тесты фильтрации программ по дате."""
    
    def test_filter_today(self):
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        
        programs = [
            Program(title="Today Show", start=today),
            Program(title="Yesterday Show", start=yesterday),
        ]
        
        filtered = filter_programs_by_date(programs, days_ago=0)
        assert len(filtered) == 1
        assert filtered[0].title == "Today Show"
    
    def test_filter_yesterday(self):
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        
        programs = [
            Program(title="Today Show", start=today),
            Program(title="Yesterday Show", start=yesterday),
        ]
        
        filtered = filter_programs_by_date(programs, days_ago=1)
        assert len(filtered) == 1
        assert filtered[0].title == "Yesterday Show"


# =============================================================================
# Тесты уникальности файлов
# =============================================================================

class TestUniqueFilepath:
    """Тесты функции get_unique_filepath."""
    
    def test_no_conflict(self, tmp_path):
        filepath = tmp_path / "test.txt"
        result = get_unique_filepath(filepath)
        assert result == filepath
    
    def test_with_conflict(self, tmp_path):
        filepath = tmp_path / "test.txt"
        filepath.touch()
        
        result = get_unique_filepath(filepath)
        assert result.name == "test_1.txt"
    
    def test_multiple_conflicts(self, tmp_path):
        filepath = tmp_path / "test.txt"
        filepath.touch()
        (tmp_path / "test_1.txt").touch()
        (tmp_path / "test_2.txt").touch()
        
        result = get_unique_filepath(filepath)
        assert result.name == "test_3.txt"
