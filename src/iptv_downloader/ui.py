"""
Модуль пользовательского интерфейса.
Интерактивный ввод, отображение информации.
"""

import sys
from typing import Optional, List, Tuple, Any

from .models import Channel, Program, RecordingStatus


def print_header(title: str, width: int = 60) -> None:
    """Вывести заголовок."""
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width)


def print_separator(width: int = 60) -> None:
    """Вывести разделитель."""
    print("-" * width)


def display_channels(channels: List[Channel], show_groups: bool = True) -> None:
    """
    Отобразить нумерованный список каналов.
    
    Args:
        channels: Список каналов для отображения.
        show_groups: Показывать ли группы каналов.
    """
    print_header(f"📺 Доступные каналы ({len(channels)} шт.)")
    
    for i, channel in enumerate(channels, 1):
        if show_groups and channel.group:
            print(f"{i:3}. {channel.name} [{channel.group}]")
        else:
            print(f"{i:3}. {channel.name}")
    
    print_separator()


def display_programs(programs: List[Program], limit: int = 50) -> None:
    """
    Отобразить список программ.
    
    Args:
        programs: Список программ.
        limit: Максимальное количество для отображения.
    """
    display_list = programs[-limit:] if len(programs) > limit else programs
    
    if len(programs) > limit:
        print(f"[!] Найдено много передач ({len(programs)}). Показываем последние {limit}.")
    
    print_header(f"📺 Архив передач ({len(display_list)} передач)")
    
    for i, program in enumerate(display_list, 1):
        start_str = program.start_formatted if program.start else "Неизвестно"
        print(f"{i:3}. [{start_str}] {program.title}")
    
    print_separator()


def display_qualities(qualities: List[Tuple[str, str]]) -> None:
    """
    Отобразить доступные качества потока.
    
    Args:
        qualities: Список кортежей (качество, URL).
    """
    print(f"[+] Доступно качеств: {len(qualities)}")
    for quality, _ in qualities:
        print(f"    - {quality}")


def get_user_input(
    prompt: str,
    validator: Optional[callable] = None,
    error_message: str = "[!] Неверный ввод",
) -> str:
    """
    Получить ввод от пользователя с валидацией.
    
    Args:
        prompt: Текст приглашения.
        validator: Функция валидации (возвращает True если ввод корректен).
        error_message: Сообщение об ошибке.
        
    Returns:
        Введённая строка.
    """
    while True:
        print(prompt)
        user_input = input("> ").strip()
        
        if validator is None or validator(user_input):
            return user_input
        
        print(error_message)


def get_channel_choice(channels: List[Channel]) -> Optional[Channel]:
    """
    Получить выбор канала от пользователя.
    Поддерживает ввод номера или поиск по названию.
    
    Args:
        channels: Список доступных каналов.
        
    Returns:
        Выбранный канал или None.
    """
    while True:
        print("\nВведите номер канала или часть названия для поиска:")
        print("(или 'q' для выхода, 'r' для обновления списка)")
        
        user_input = input("> ").strip()
        
        if user_input.lower() == "q":
            return None
        
        if user_input.lower() == "r":
            return "refresh"  # type: ignore
        
        # Попытаться интерпретировать как номер
        try:
            channel_num = int(user_input)
            if 1 <= channel_num <= len(channels):
                return channels[channel_num - 1]
            else:
                print(f"[!] Номер должен быть от 1 до {len(channels)}")
                continue
        except ValueError:
            pass
        
        # Поиск по названию
        if len(user_input) >= 2:
            results = search_channels(channels, user_input)
            
            if not results:
                print(f"[!] Каналы с названием '{user_input}' не найдены")
                continue
            
            if len(results) == 1:
                print(f"\n[+] Найден канал: {results[0][1].name}")
                return results[0][1]
            
            # Несколько совпадений
            print(f"\nНайдено совпадений: {len(results)}")
            for num, channel in results:
                if channel.group:
                    print(f"  {num}. {channel.name} [{channel.group}]")
                else:
                    print(f"  {num}. {channel.name}")
            print("\nВведите номер нужного канала:")
            
            try:
                choice = int(input("> ").strip())
                for num, channel in results:
                    if num == choice:
                        return channel
                print("[!] Неверный номер")
            except ValueError:
                print("[!] Введите число")
        else:
            print("[!] Введите минимум 2 символа для поиска")


def search_channels(
    channels: List[Channel],
    query: str,
) -> List[Tuple[int, Channel]]:
    """
    Найти каналы по названию (регистронезависимый поиск).
    
    Args:
        channels: Список каналов.
        query: Строка поиска.
        
    Returns:
        Список кортежей (номер, канал).
    """
    query_lower = query.lower()
    results = []
    
    for i, channel in enumerate(channels, 1):
        if query_lower in channel.name.lower():
            results.append((i, channel))
    
    return results


def get_recording_mode() -> Optional[str]:
    """
    Получить выбор режима записи.
    
    Returns:
        'archive', 'live', или None.
    """
    print("\nВыберите режим записи:")
    print("1. Запись из архива (если доступно)")
    print("2. Запись прямого эфира")
    print("q. Выход в меню каналов")
    
    choice = input("> ").strip()
    
    if choice == "1":
        return "archive"
    elif choice == "2":
        return "live"
    else:
        return None


def get_recording_duration() -> Optional[int]:
    """
    Получить длительность записи от пользователя.
    
    Returns:
        Длительность в секундах или None.
    """
    print("\nВведите длительность записи:")
    print("  - в минутах (например, 30)")
    print("  - в секундах с 's' (например, 90s)")
    print("  - оставьте пустым для бессрочной записи")
    
    duration_input = input("> ").strip()
    
    if not duration_input:
        return None
    
    try:
        if duration_input.lower().endswith("s"):
            return int(duration_input[:-1])
        else:
            return int(duration_input) * 60
    except ValueError:
        return None


def get_period_choice() -> str:
    """
    Получить выбор периода для архива.
    
    Returns:
        'yesterday', 'today', или 'all'.
    """
    print("\nВыберите период:")
    print("1. Вчера")
    print("2. Сегодня")
    print("3. Все доступные")
    
    choice = input("> ").strip()
    
    if choice == "1":
        return "yesterday"
    elif choice == "2":
        return "today"
    else:
        return "all"


def display_recording_status(status: RecordingStatus) -> None:
    """
    Отобразить статус записи.
    
    Args:
        status: Текущий статус записи.
    """
    print(f"\r{status.message}", end="", flush=True)


def display_recording_help() -> None:
    """Вывести справку по управлению записью."""
    print("\n" + "-" * 60)
    print("Нажмите Ctrl+C для досрочной остановки записи")
    print("-" * 60)


def display_success(message: str) -> None:
    """Вывести сообщение об успехе."""
    print(f"\n[+] {message}")


def display_error(message: str) -> None:
    """Вывести сообщение об ошибке."""
    print(f"[!] {message}")


def display_warning(message: str) -> None:
    """Вывести предупреждение."""
    print(f"[!] Внимание: {message}")


def display_info(message: str) -> None:
    """Вывести информационное сообщение."""
    print(f"[*] {message}")


def confirm_action(prompt: str) -> bool:
    """
    Запросить подтверждение действия.
    
    Args:
        prompt: Текст вопроса.
        
    Returns:
        True если пользователь подтвердил.
    """
    print(f"{prompt} (y/n):")
    choice = input("> ").strip().lower()
    return choice == "y"


def should_continue() -> bool:
    """
    Спросить хочет ли пользователь продолжить.
    
    Returns:
        True если хочет продолжить.
    """
    print("\nХотите выбрать другой канал? (y/n):")
    choice = input("> ").strip().lower()
    return choice == "y"
