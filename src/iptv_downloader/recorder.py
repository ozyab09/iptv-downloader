"""
Модуль для записи IPTV потоков.
Управление процессом ffmpeg, мониторинг записи.
"""

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from .config import FFMPEG_DEFAULT_ARGS, FFMPEG_HLS_FLAGS
from .models import RecordingStatus, StreamQuality


def check_ffmpeg() -> bool:
    """
    Проверить наличие ffmpeg в системе.
    
    Returns:
        True если ffmpeg доступен.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_ffmpeg_info() -> str:
    """
    Получить информацию о версии ffmpeg.
    
    Returns:
        Строка с информацией о версии.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.split("\n")[0] if result.returncode == 0 else "Неизвестно"
    except Exception:
        return "Неизвестно"


def get_stream_qualities(url: str, timeout: int = 10) -> List[StreamQuality]:
    """
    Получить доступные качества потока из M3U8 плейлиста.

    Args:
        url: URL потока.
        timeout: Таймаут запроса.

    Returns:
        Список доступных качеств.
    """
    import requests

    qualities: List[StreamQuality] = []

    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        content = response.text

        # Проверить, это ли master playlist (содержит несколько вариантов качества)
        if "#EXT-X-STREAM-INF" in content:
            lines = content.strip().split("\n")
            current_quality: dict = {}

            for line in lines:
                line = line.strip()

                if line.startswith("#EXT-X-STREAM-INF:"):
                    current_quality = {}
                    # Извлечь разрешение
                    res_match = line.split("RESOLUTION=")
                    if len(res_match) > 1:
                        res = res_match[1].split(",")[0]
                        if "x" in res:
                            parts = res.split("x")
                            current_quality["width"] = int(parts[0])
                            current_quality["height"] = int(parts[1])
                            current_quality["quality"] = f"{parts[1]}p"

                    # Извлечь битрейт
                    bw_match = line.split("BANDWIDTH=")
                    if len(bw_match) > 1:
                        bw = bw_match[1].split(",")[0]
                        current_quality["bandwidth"] = int(bw)

                elif line.startswith("http://") or line.startswith("https://"):
                    if current_quality:
                        current_quality["url"] = line
                        if "quality" not in current_quality:
                            current_quality["quality"] = "unknown"
                        qualities.append(StreamQuality(
                            quality=current_quality.get("quality", "unknown"),
                            url=line,
                            bandwidth=current_quality.get("bandwidth", 0),
                            width=current_quality.get("width", 0),
                            height=current_quality.get("height", 0),
                        ))
                        current_quality = {}
            
            # Если нашли варианты, вернуть их
            if qualities:
                return qualities

        # Это media playlist (с сегментами) или прямой поток
        # ffmpeg может работать с ним напрямую
        qualities.append(StreamQuality(quality="best", url=url))

    except Exception:
        qualities.append(StreamQuality(quality="best", url=url))

    return qualities


def get_max_quality_url(qualities: List[StreamQuality]) -> str:
    """
    Получить URL потока максимального качества.
    
    Args:
        qualities: Список доступных качеств.
        
    Returns:
        URL лучшего качества.
    """
    if not qualities:
        return ""
    
    if len(qualities) == 1:
        return qualities[0].url
    
    # Сортировать по качеству (разрешение > битрейт)
    def quality_key(q: StreamQuality):
        if q.height > 0:
            return (0, q.height, q.bandwidth)
        elif q.bandwidth > 0:
            return (1, q.bandwidth, 0)
        else:
            return (2, 0, 0)
    
    sorted_qualities = sorted(qualities, key=quality_key, reverse=True)
    return sorted_qualities[0].url


class RecordingManager:
    """Управление записью потока."""
    
    def __init__(self):
        self.ffmpeg_process: Optional[subprocess.Popen] = None
        self.is_recording = False
        self.start_time: Optional[datetime] = None
        self.expected_end_time: Optional[datetime] = None
        self.output_path: Optional[Path] = None
    
    def start_recording(
        self,
        stream_url: str,
        output_path: Path,
        duration_seconds: Optional[int] = None,
    ) -> bool:
        """
        Начать запись потока.

        Args:
            stream_url: URL потока для записи.
            output_path: Путь для сохранения файла.
            duration_seconds: Длительность в секундах (None для бессрочной).

        Returns:
            True если запись успешно запущена.
        """
        try:
            # Построить команду ffmpeg
            cmd = ["ffmpeg", "-i", stream_url]
            cmd.extend(FFMPEG_DEFAULT_ARGS)
            cmd.extend(FFMPEG_HLS_FLAGS)  # Добавить HLS флаги для стабильности

            # Если указана длительность
            if duration_seconds:
                cmd.extend(["-t", str(duration_seconds)])
                self.expected_end_time = datetime.now() + timedelta(
                    seconds=duration_seconds
                )

            cmd.extend(["-y", str(output_path)])

            # Запустить процесс
            self.ffmpeg_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
            )

            self.is_recording = True
            self.start_time = datetime.now()
            self.output_path = output_path

            return True

        except Exception as e:
            import logging
            logging.error(f"Ошибка запуска ffmpeg: {e}")
            return False
    
    def stop_recording(self) -> None:
        """Остановить запись."""
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            try:
                # Отправить сигнал завершения
                self.ffmpeg_process.stdin.write(b"q")
                self.ffmpeg_process.stdin.flush()
                self.ffmpeg_process.wait(timeout=10)
            except Exception:
                try:
                    self.ffmpeg_process.terminate()
                    self.ffmpeg_process.wait(timeout=5)
                except Exception:
                    self.ffmpeg_process.kill()
        
        self.is_recording = False
    
    def get_status(self) -> RecordingStatus:
        """
        Получить статус записи.
        
        Returns:
            RecordingStatus с текущей информацией.
        """
        if not self.is_recording:
            return RecordingStatus(
                is_active=False,
                message="Запись не активна",
            )
        
        if self.ffmpeg_process:
            return_code = self.ffmpeg_process.poll()
            if return_code is not None:
                self.is_recording = False
                if return_code == 0:
                    return RecordingStatus(
                        is_active=False,
                        message="Запись завершена успешно",
                    )
                else:
                    return RecordingStatus(
                        is_active=False,
                        message=f"Запись прервана (код: {return_code})",
                    )
        
        elapsed = datetime.now() - self.start_time if self.start_time else timedelta()
        elapsed_seconds = int(elapsed.total_seconds())
        
        if self.expected_end_time:
            remaining = self.expected_end_time - datetime.now()
            remaining_seconds = max(0, int(remaining.total_seconds()))
            
            if remaining_seconds > 0:
                return RecordingStatus(
                    is_active=True,
                    message="Запись идет: {} (осталось: {})".format(
                        self._format_duration(elapsed_seconds),
                        self._format_duration(remaining_seconds),
                    ),
                    elapsed_seconds=elapsed_seconds,
                    remaining_seconds=remaining_seconds,
                )
            else:
                return RecordingStatus(
                    is_active=False,
                    message="Время записи истекло",
                    elapsed_seconds=elapsed_seconds,
                )
        
        return RecordingStatus(
            is_active=True,
            message=f"Запись идет: {self._format_duration(elapsed_seconds)}",
            elapsed_seconds=elapsed_seconds,
        )
    
    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Форматировать длительность в читаемый вид."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}ч {minutes}м {secs}с"
        elif minutes > 0:
            return f"{minutes}м {secs}с"
        else:
            return f"{secs}с"
