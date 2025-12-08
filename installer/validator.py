"""
Модуль валидации ввода пользователя
"""
import re
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse


def validate_domain(domain: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует доменное имя
    
    Returns:
        (is_valid, error_message)
    """
    if not domain:
        return False, "Домен не может быть пустым"
    
    # Убираем протокол если есть
    domain = domain.replace('http://', '').replace('https://', '').replace('www.', '')
    
    # Проверяем формат
    domain_pattern = re.compile(
        r'^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$',
        re.IGNORECASE
    )
    
    if not domain_pattern.match(domain):
        return False, "Неверный формат домена. Пример: example.com или subdomain.example.com"
    
    # Проверяем длину
    if len(domain) > 253:
        return False, "Домен слишком длинный (максимум 253 символа)"
    
    return True, None


def validate_port(port: int, check_available: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Валидирует номер порта
    
    Args:
        port: Номер порта
        check_available: Проверять доступность порта
        
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(port, int):
        try:
            port = int(port)
        except ValueError:
            return False, "Порт должен быть числом"
    
    if port < 1 or port > 65535:
        return False, "Порт должен быть в диапазоне 1-65535"
    
    if port < 1024:
        return False, "Порты ниже 1024 требуют root прав"
    
    if check_available:
        if not is_port_available(port):
            return False, f"Порт {port} уже занят"
    
    return True, None


def is_port_available(port: int) -> bool:
    """Проверяет доступен ли порт"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует email адрес
    
    Returns:
        (is_valid, error_message)
    """
    if not email:
        return False, "Email не может быть пустым"
    
    email_pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    if not email_pattern.match(email):
        return False, "Неверный формат email. Пример: user@example.com"
    
    return True, None


def validate_path(path: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует путь (для режима path routing)
    
    Returns:
        (is_valid, error_message)
    """
    if not path:
        return False, "Путь не может быть пустым"
    
    if not path.startswith('/'):
        return False, "Путь должен начинаться с /"
    
    if not re.match(r'^/[a-z0-9/-]*$', path, re.IGNORECASE):
        return False, "Путь может содержать только буквы, цифры, / и -"
    
    if path.endswith('/') and path != '/':
        return False, "Путь не должен заканчиваться на / (кроме корня)"
    
    return True, None


def validate_memory(memory: str) -> Tuple[bool, Optional[float], Optional[str]]:
    """
    Валидирует значение памяти (например "2g", "512m")
    
    Returns:
        (is_valid, value_in_gb, error_message)
    """
    if not memory:
        return False, None, "Значение памяти не может быть пустым"
    
    memory = memory.strip().lower()
    
    # Парсим формат типа "2g", "512m", "1.5g"
    pattern = re.compile(r'^(\d+(?:\.\d+)?)\s*([gkm]?b?)$')
    match = pattern.match(memory)
    
    if not match:
        return False, None, "Неверный формат. Используйте формат: 2g, 512m, 1.5g"
    
    value = float(match.group(1))
    unit = match.group(2) or 'g'
    
    # Конвертируем в GB
    if unit.startswith('k'):
        value_gb = value / (1024 * 1024)
    elif unit.startswith('m'):
        value_gb = value / 1024
    else:  # g или gb
        value_gb = value
    
    if value_gb <= 0:
        return False, None, "Значение памяти должно быть больше 0"
    
    if value_gb > 128:
        return False, None, "Значение памяти слишком большое (максимум 128 GB)"
    
    return True, value_gb, None


def validate_cpu(cpu: str) -> Tuple[bool, Optional[float], Optional[str]]:
    """
    Валидирует значение CPU (например "0.5", "1.0", "2")
    
    Returns:
        (is_valid, value, error_message)
    """
    if not cpu:
        return False, None, "Значение CPU не может быть пустым"
    
    try:
        value = float(cpu)
    except ValueError:
        return False, None, "CPU должен быть числом"
    
    if value <= 0:
        return False, None, "CPU должен быть больше 0"
    
    if value > 32:
        return False, None, "CPU слишком большое (максимум 32 ядра)"
    
    return True, value, None


def validate_api_key(key: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует API ключ
    
    Returns:
        (is_valid, error_message)
    """
    if not key:
        return False, "API ключ не может быть пустым"
    
    if len(key) < 16:
        return False, "API ключ должен быть минимум 16 символов"
    
    if len(key) > 256:
        return False, "API ключ слишком длинный (максимум 256 символов)"
    
    return True, None

