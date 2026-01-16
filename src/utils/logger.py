"""
Logger utility with colored output and file logging
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    USE_COLORS = True
except ImportError:
    USE_COLORS = False
    # Fallback colors (empty strings if colorama not available)
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = BLACK = WHITE = ''
    class Style:
        RESET_ALL = BRIGHT = DIM = ''

logs_dir = Path('logs')
logs_dir.mkdir(exist_ok=True)


def get_log_file_name() -> Path:
    """Get log file name for today"""
    date = datetime.now().strftime('%Y-%m-%d')
    return logs_dir / f'bot-{date}.log'


def write_to_file(message: str) -> None:
    """Write message to log file"""
    try:
        log_file = get_log_file_name()
        timestamp = datetime.now().isoformat()
        log_entry = f'[{timestamp}] {message}\n'
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception:
        # Silently fail to avoid infinite loops
        pass


def format_address(address: str) -> str:
    """Format address for display"""
    return f'{address[:6]}...{address[-4:]}'


def mask_address(address: str) -> str:
    """Mask address for display"""
    return f'{address[:6]}{"*" * 34}{address[-4:]}'


def header(title: str) -> None:
    """Print header"""
    print(f'\n{Fore.CYAN}{Style.BRIGHT}{"=" * 70}{Style.RESET_ALL}')
    print(f'{Fore.CYAN}{Style.BRIGHT}  {title}{Style.RESET_ALL}')
    print(f'{Fore.CYAN}{Style.BRIGHT}{"=" * 70}{Style.RESET_ALL}\n')
    write_to_file(f'HEADER: {title}')


def info(message: str) -> None:
    """Print info message"""
    print(f'{Fore.BLUE}[INFO]{Style.RESET_ALL} {message}')
    write_to_file(f'INFO: {message}')


def trade_detect(message: str) -> None:
    """Print detected trade message in MAGENTA"""
    # Use Magenta for visibility
    print(f'{Fore.MAGENTA}[DETECTED]{Style.RESET_ALL} {message}')
    write_to_file(f'DETECTED: {message}')


def success(message: str) -> None:
    """Print success message"""
    print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}')
    write_to_file(f'SUCCESS: {message}')


def warning(message: str) -> None:
    """Print warning message"""
    print(f'{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}')
    write_to_file(f'WARNING: {message}')


def error(message: str) -> None:
    """Print error message"""
    print(f'{Fore.RED}[ERROR]{Style.RESET_ALL} {message}', file=sys.stderr)
    write_to_file(f'ERROR: {message}')


def debug(message: str) -> None:
    """Print debug message"""
    if USE_COLORS:
        print(f'{Fore.CYAN}[DEBUG]{Style.RESET_ALL} {message}')
    else:
        print(f'[DEBUG] {message}')
    write_to_file(f'DEBUG: {message}')

__all__ = ['header', 'info', 'success', 'warning', 'error', 'trade_detect', 'debug']
