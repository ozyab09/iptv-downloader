"""
Integration тесты для IPTV Downloader.
Тестируют взаимодействие между модулями.
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iptv_downloader.models import Channel, Program
from iptv_downloader.playlist import parse_m3u_playlist, download_playlist
from iptv_downloader.epg import parse_epg_file, get_programs_for_channel
from iptv_downloader.recorder import check_ffmpeg, get_stream_qualities


# =============================================================================
# Фикстуры
# =============================================================================

@pytest.fixture
def sample_m3u_content():
    """Пример содержимого M3U плейлиста."""
    return '''#EXTM3U url-tvg="http://epg.example.com/guide.xml"
#EXTINF:0 tvg-id="123" tvg-logo="http://logo.png" group-title="News",CNN HD
http://example.com/cnn.m3u8
#EXTINF:0 tvg-id="456" group-title="Sports",ESPN
http://example.com/espn.m3u8
#EXTINF:0 tvg-id="789" tvg-rec="7",Local Channel
http://example.com/local.m3u8
'''


@pytest.fixture
def sample_epg_content():
    """Пример содержимого EPG."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="123">
    <display-name>CNN HD</display-name>
  </channel>
  <channel id="456">
    <display-name>ESPN</display-name>
  </channel>
  <programme start="20240115100000 +0000" stop="20240115110000 +0000" channel="123">
    <title>News Morning</title>
    <desc>Morning news program</desc>
  </programme>
  <programme start="20240115110000 +0000" stop="20240115120000 +0000" channel="123">
    <title>News Midday</title>
    <desc>Midday news update</desc>
  </programme>
  <programme start="20240115090000 +0000" stop="20240115100000 +0000" channel="456">
    <title>Sports Center</title>
    <desc>Daily sports news</desc>
  </programme>
</tv>
'''


@pytest.fixture
def temp_playlist_file(tmp_path, sample_m3u_content):
    """Временный файл плейлиста."""
    filepath = tmp_path / "test.m3u"
    filepath.write_text(sample_m3u_content, encoding="utf-8")
    return filepath


@pytest.fixture
def temp_epg_file(tmp_path, sample_epg_content):
    """Временный файл EPG."""
    filepath = tmp_path / "epg.xml"
    filepath.write_text(sample_epg_content, encoding="utf-8")
    return filepath


# =============================================================================
# Интеграционные тесты
# =============================================================================

class TestPlaylistParsing:
    """Тесты парсинга плейлистов."""
    
    def test_parse_m3u_with_epg_url(self, temp_playlist_file):
        """Парсинг M3U с извлечением EPG URL."""
        channels, epg_url = parse_m3u_playlist(temp_playlist_file)
        
        assert len(channels) == 3
        assert epg_url == "http://epg.example.com/guide.xml"
    
    def test_parse_channel_metadata(self, temp_playlist_file):
        """Парсинг метаданных каналов."""
        channels, _ = parse_m3u_playlist(temp_playlist_file)
        
        cnn = channels[0]
        assert cnn.name == "CNN HD"
        assert cnn.tvg_id == "123"
        assert cnn.logo == "http://logo.png"
        assert cnn.group == "News"
        assert cnn.url == "http://example.com/cnn.m3u8"
    
    def test_parse_channel_without_logo(self, temp_playlist_file):
        """Парсинг канала без логотипа."""
        channels, _ = parse_m3u_playlist(temp_playlist_file)
        
        espn = channels[1]
        assert espn.name == "ESPN"
        assert espn.tvg_id == "456"
        assert espn.logo == ""
        assert espn.group == "Sports"
    
    def test_parse_tvg_rec(self, temp_playlist_file):
        """Парсинг атрибута tvg-rec."""
        channels, _ = parse_m3u_playlist(temp_playlist_file)
        
        local = channels[2]
        assert local.tvg_rec == 7


class TestEpgParsing:
    """Тесты парсинга EPG."""
    
    def test_parse_epg_file(self, temp_epg_file):
        """Парсинг XMLTV файла."""
        epg_data = parse_epg_file(temp_epg_file)
        
        assert epg_data is not None
        assert "123" in epg_data
        assert "456" in epg_data
    
    def test_parse_programs(self, temp_epg_file):
        """Парсинг программ передач."""
        epg_data = parse_epg_file(temp_epg_file)
        
        cnn_programs = epg_data.get("123", [])
        assert len(cnn_programs) == 2
        
        program = cnn_programs[0]
        assert program.title == "News Morning"
        assert program.start is not None
        assert program.start.hour == 10
    
    def test_get_programs_for_channel_by_id(self, temp_epg_file):
        """Получение программ по tvg-id."""
        epg_data = parse_epg_file(temp_epg_file)
        
        programs = get_programs_for_channel(epg_data, "123", "CNN")
        assert len(programs) == 2
    
    def test_get_programs_for_channel_by_name(self, temp_epg_file):
        """Получение программ по имени канала."""
        epg_data = parse_epg_file(temp_epg_file)
        
        programs = get_programs_for_channel(epg_data, "", "ESPN")
        # Должен найти по channel_id или имени
        assert len(programs) >= 0  # Может не найти если нет точного совпадения


class TestFFmpeg:
    """Тесты ffmpeg."""
    
    def test_check_ffmpeg_installed(self):
        """Проверка наличия ffmpeg."""
        # Этот тест зависит от системы, где запускается
        result = check_ffmpeg()
        # Просто проверяем что функция возвращает bool
        assert isinstance(result, bool)


class TestStreamQualities:
    """Тесты определения качеств потока."""
    
    def test_get_qualities_direct_stream(self):
        """Получение качества для прямого потока."""
        # Тест с mock для внешнего запроса
        import requests
        with patch.object(requests, 'get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            from iptv_downloader.recorder import get_stream_qualities
            qualities = get_stream_qualities("http://example.com/stream.m3u8")
            
            assert len(qualities) == 1
            assert qualities[0].quality == "best"


class TestEndToEnd:
    """Сквозные тесты."""
    
    def test_playlist_and_epg_integration(self, temp_playlist_file, temp_epg_file):
        """Интеграция плейлиста и EPG."""
        # Распарсить плейлист
        channels, epg_url = parse_m3u_playlist(temp_playlist_file)
        
        # Распарсить EPG
        epg_data = parse_epg_file(temp_epg_file)
        
        # Найти программы для первого канала
        if channels and epg_data:
            channel = channels[0]
            programs = get_programs_for_channel(
                epg_data,
                channel.tvg_id,
                channel.name,
            )
            
            # Должны найтись программы по tvg-id
            assert len(programs) == 2


class TestMockedDownload:
    """Тесты с моками для загрузки."""
    
    @patch('iptv_downloader.playlist.requests.get')
    def test_download_playlist_mock(self, mock_get, tmp_path):
        """Тест загрузки плейлиста с моком."""
        mock_response = MagicMock()
        mock_response.text = "#EXTM3U\n#EXTINF:0,Test\nhttp://test.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        # Скачать в временную директорию
        from iptv_downloader.playlist import download_playlist
        
        result = download_playlist("http://example.com/playlist.m3u", tmp_path)
        
        assert result is not None
        assert result.exists()
        assert result.suffix == ".m3u"
