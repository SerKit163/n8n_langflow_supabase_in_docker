"""
Вспомогательные утилиты
"""
import os
import secrets
import string
from pathlib import Path
from typing import Optional


def generate_secret_key(length: int = 64) -> str:
    """Генерирует случайный секретный ключ"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_password(length: int = 32) -> str:
    """Генерирует безопасный пароль"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def ensure_dir(path: str) -> Path:
    """Создает директорию если её нет"""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_project_root() -> Path:
    """Возвращает корневую директорию проекта"""
    return Path(__file__).parent.parent


def read_template(template_name: str) -> str:
    """Читает шаблон из папки templates"""
    template_path = get_project_root() / "templates" / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Шаблон {template_name} не найден")
    return template_path.read_text(encoding='utf-8')


def write_file(path: str, content: str) -> None:
    """Записывает файл с созданием директорий если нужно"""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding='utf-8')


def check_port_available(port: int) -> bool:
    """Проверяет доступен ли порт"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False


def format_bytes(bytes_value: int) -> str:
    """Форматирует байты в читаемый формат"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

