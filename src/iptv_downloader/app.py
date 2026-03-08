"""
Основной модуль приложения IPTV Downloader.
Управление рабочим процессом, координация компонентов.
"""

import signal
import sys
from datetime import datetime
from typing import Optional, List

from .config import DOWNLOADS_DIR, __version__, ensure_directories
from .models import Channel, PlaylistInfo
from .playlist import (
    download_playlist,
    load_playlist_history,
    parse_m3u_playlist,
    save_playlist_info,
    validate_url,
)
from .epg import (
    get_programs_for_channel,
    get_programs_for_period,
    load_epg_data,
)
from .recorder import (
    RecordingManager,
    check_ffmpeg,
    get_ffmpeg_info,
    get_max_quality_url,
    get_stream_qualities,
)
from . import ui
from .utils import (
    check_disk_space,
    estimate_file_size,
    format_file_size,
    format_duration,
    get_file_size,
    get_unique_filepath,
    sanitize_filename,
)


class IPTVDownloader:
    """Основной класс приложения."""
    
    # Резервный EPG URL
    DEFAULT_EPG_URL = "http://ru.epg.one/epg2.xml.gz"
    
    def __init__(self):
        self.channels: List[Channel] = []
        self.current_channel: Optional[Channel] = None
        self.current_epg_url: Optional[str] = None
        self.recording_manager = RecordingManager()
        self.epg_url_from_playlist: Optional[str] = None
        
        # Настроить обработку сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame) -> None:
        """Обработчик сигналов прерывания."""
        print("\n\n[!] Получен сигнал прерывания")
        self.recording_manager.stop_recording()
        sys.exit(0)
    
    def run(self) -> None:
        """Запустить основной цикл приложения."""
        ui.print_header(f"🎬 IPTV Downloader v{__version__}")
        
        # Проверка ffmpeg
        if not check_ffmpeg():
            ui.display_error("ffmpeg не найден в системе!")
            print("\nУстановите ffmpeg:")
            print("  - Windows: https://ffmpeg.org/download.html")
            print("  - macOS: brew install ffmpeg")
            print("  - Linux: sudo apt install ffmpeg")
            return
        
        ui.display_success(f"ffmpeg: {get_ffmpeg_info()}")
        
        # Создать директории
        ensure_directories()
        
        # Запросить ссылку на плейлист
        playlist_url = self._get_playlist_url()
        if not playlist_url:
            return
        
        # Скачать плейлист
        ui.display_info("Загрузка плейлиста...")
        playlist_path = download_playlist(playlist_url)
        if not playlist_path:
            ui.display_error("Не удалось скачать плейлист")
            return
        
        ui.display_success(f"Плейлист сохранен: {playlist_path}")
        
        # Распарсить плейлист
        ui.display_info("Обработка плейлиста...")
        self.channels, self.epg_url_from_playlist = parse_m3u_playlist(playlist_path)
        
        if not self.channels:
            ui.display_error("Каналы не найдены в плейлисте")
            return
        
        ui.display_success(f"Найдено каналов: {len(self.channels)}")
        
        # Сохранить в историю
        playlist_info = PlaylistInfo(
            url=playlist_url,
            filepath=str(playlist_path),
            timestamp=datetime.now(),
            channels_count=len(self.channels),
            epg_url=self.epg_url_from_playlist or "",
        )
        save_playlist_info(playlist_info)
        
        # Основной цикл выбора каналов
        while True:
            self._process_channel_selection()
            
            if not ui.should_continue():
                break
        
        ui.display_success("Работа завершена")
    
    def _get_playlist_url(self) -> Optional[str]:
        """Запросить у пользователя ссылку на плейлист."""
        # Показать историю (только уникальные URL)
        history = load_playlist_history()
        if history:
            # Оставить только уникальные URL (последние вхождения)
            seen_urls = set()
            unique_history = []
            for item in reversed(history):
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    unique_history.insert(0, item)

            print("\n📋 Последние плейлисты:")
            for i, item in enumerate(unique_history[-5:], 1):
                print(f"  {i}. {item.url}")
            print("  0. Ввести ссылку вручную")
            print()

            # Предложить выбор из истории
            choice = input("Выберите плейлист (0-5): ").strip()
            try:
                idx = int(choice)
                if 1 <= idx <= min(5, len(unique_history)):
                    selected = unique_history[-idx]
                    ui.display_info(f"Выбран плейлист: {selected.url}")
                    return selected.url
                elif idx == 0:
                    pass  # Продолжить к ручному вводу
                else:
                    ui.display_warning("Неверный номер, введите ссылку вручную")
            except ValueError:
                pass  # Продолжить к ручному вводу

        while True:
            url = ui.get_user_input(
                prompt="Введите ссылку на IPTV плейлист (или 'q' для выхода):",
                validator=lambda x: x.lower() == "q" or validate_url(x),
                error_message="[!] Неверный формат URL. Должен начинаться с http:// или https://",
            )

            if url.lower() == "q":
                return None

            return url
    
    def _process_channel_selection(self) -> None:
        """Обработать выбор канала."""
        # Показать список каналов
        ui.display_channels(self.channels)
        
        # Получить выбор
        channel = ui.get_channel_choice(self.channels)
        
        if channel == "refresh":
            return
        
        if not channel:
            return
        
        self.current_channel = channel
        ui.display_success(f"Выбран канал: {channel.name}")
        
        # Получить URL потока
        stream_url = channel.url
        if not stream_url:
            ui.display_error("URL потока не найден")
            return
        
        # Анализ потоков
        ui.display_info("Анализ доступных потоков...")
        qualities = get_stream_qualities(stream_url)
        
        if len(qualities) > 1:
            ui.display_qualities([(q.quality, q.url) for q in qualities])
        
        # Выбрать режим записи
        mode = ui.get_recording_mode()
        
        if mode == "archive":
            self._archive_mode(stream_url)
        elif mode == "live":
            self._live_mode(stream_url)
        else:
            ui.display_info("Возврат в меню каналов")
    
    def _archive_mode(self, stream_url: str) -> None:
        """Режим записи из архива."""
        ui.display_info("Проверка доступности архива...")
        
        # Получить EPG URL
        epg_url = self.epg_url_from_playlist or self.DEFAULT_EPG_URL
        
        # Загрузить EPG
        epg_data = load_epg_data(epg_url)
        
        if not epg_data:
            ui.display_error("Архив передач недоступен")
            ui.display_info("Переключаюсь на режим прямого эфира...")
            self._live_mode(stream_url)
            return
        
        # Получить программы для канала
        programs = get_programs_for_channel(
            epg_data,
            self.current_channel.tvg_id,
            self.current_channel.name,
        )
        
        if not programs:
            ui.display_error("Нет доступных передач в архиве")
            return
        
        # Выбор периода
        period = ui.get_period_choice()
        programs = get_programs_for_period(programs, period)
        
        if not programs:
            ui.display_error("Нет передач за выбранный период")
            return
        
        # Показать список
        ui.display_programs(programs)
        
        # Получить выбор программы
        print("\nВведите номер передачи для скачивания (или 'q' для выхода):")
        try:
            choice = int(input("> ").strip())
            if 1 <= choice <= len(programs):
                program = programs[choice - 1]
            else:
                ui.display_error("Неверный номер")
                return
        except ValueError:
            ui.display_error("Введите число")
            return
        
        # Скачать передачу
        safe_title = sanitize_filename(program.title)
        filename = f"{self.current_channel.name}_{safe_title}"
        
        ui.display_info(f"Запись передачи: {program.title}")
        self._download_stream(stream_url, filename, None)
    
    def _live_mode(self, stream_url: str) -> None:
        """Режим прямого эфира."""
        ui.display_info("Режим прямого эфира")
        
        # Получить лучшее качество
        qualities = get_stream_qualities(stream_url)
        max_quality_url = get_max_quality_url(qualities)
        
        if max_quality_url != stream_url:
            ui.display_success("Выбрано максимальное качество")
        
        # Запросить длительность
        duration_seconds = ui.get_recording_duration()
        
        if duration_seconds:
            # Проверка размера
            estimated_size = estimate_file_size(duration_seconds)
            estimated_gb = estimated_size / (1024**3)
            
            if estimated_gb > 10:
                ui.display_warning(
                    f"Примерный размер файла ({estimated_gb:.1f} ГБ) превышает 10 ГБ"
                )
                if not ui.confirm_action("Продолжить"):
                    return
            
            # Проверка места на диске
            ok, error = check_disk_space(DOWNLOADS_DIR, estimated_size)
            if not ok:
                ui.display_error(error)
                return
        
        # Сформировать имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.current_channel.name}_{timestamp}"
        
        # Начать запись
        self._download_stream(max_quality_url, filename, duration_seconds)
    
    def _download_stream(
        self,
        stream_url: str,
        filename_base: str,
        duration_seconds: Optional[int],
    ) -> None:
        """Скачать поток."""
        # Сформировать путь
        safe_name = sanitize_filename(filename_base)
        output_path = get_unique_filepath(DOWNLOADS_DIR / f"{safe_name}.mp4")
        
        # Начать запись
        if not self.recording_manager.start_recording(
            stream_url, output_path, duration_seconds
        ):
            ui.display_error("Не удалось запустить запись")
            ui.display_error("Проверьте лог ошибок: error.log")
            return

        # Информация о записи
        print("\n[*] Запуск записи...")
        print(f"    Файл: {output_path.name}")
        if duration_seconds:
            print(f"    Длительность: {format_duration(duration_seconds)}")

        ui.display_recording_help()

        # Мониторинг
        try:
            while self.recording_manager.is_recording:
                import time
                time.sleep(1)

                status = self.recording_manager.get_status()

                if not status.is_active:
                    break

                ui.display_recording_status(status)

        except KeyboardInterrupt:
            print("\n\n[!] Получен сигнал остановки")

        finally:
            self.recording_manager.stop_recording()

        # Результат
        if output_path.exists() and output_path.stat().st_size > 0:
            file_size = get_file_size(output_path)
            ui.display_success("Запись завершена!")
            print(f"    Файл: {output_path}")
            if file_size:
                print(f"    Размер: {format_file_size(file_size)}")
        else:
            ui.display_error("Файл не был создан или запись не удалась")
            ui.display_error("Проверьте лог ошибок: error.log")
