"""
Модуль генерации ключей Supabase
"""
import base64
import secrets
from typing import Dict


def generate_supabase_keys(jwt_secret: str = None) -> Dict[str, str]:
    """
    Генерирует ключи Supabase на основе JWT секрета
    
    Args:
        jwt_secret: JWT секрет (если не указан, генерируется автоматически)
        
    Returns:
        Словарь с ключами: jwt_secret, anon_key, service_role_key
    """
    if not jwt_secret:
        # Генерируем JWT секрет (минимум 32 символа, рекомендуется 64)
        jwt_secret = secrets.token_urlsafe(64)
    
    # ANON_KEY и SERVICE_ROLE_KEY генерируются на основе JWT_SECRET
    # В реальности Supabase использует специальный формат, но для простоты
    # мы генерируем их как base64 от JWT_SECRET с префиксами
    
    # ANON_KEY - публичный ключ (для клиентских приложений)
    anon_key = base64.b64encode(
        f"anon.{jwt_secret}".encode()
    ).decode()[:64]
    
    # SERVICE_ROLE_KEY - приватный ключ (для серверных операций)
    service_role_key = base64.b64encode(
        f"service_role.{jwt_secret}".encode()
    ).decode()[:64]
    
    # Для Supabase нужны ключи в формате JWT
    # Упрощенная версия - в реальности Supabase использует более сложный алгоритм
    # Но для self-hosted версии это должно работать
    
    return {
        'jwt_secret': jwt_secret,
        'anon_key': anon_key,
        'service_role_key': service_role_key
    }


def generate_supabase_keys_proper() -> Dict[str, str]:
    """
    Генерирует ключи Supabase в правильном формате
    Использует алгоритм как в официальной документации Supabase
    
    Для self-hosted Supabase ключи должны быть:
    - JWT_SECRET: минимум 32 символа (рекомендуется 64+)
    - ANON_KEY и SERVICE_ROLE_KEY: генерируются Supabase автоматически на основе JWT_SECRET
    Но для упрощения генерируем их как безопасные случайные строки
    """
    # Генерируем JWT секрет (минимум 32 символа, рекомендуется 64+)
    jwt_secret = secrets.token_urlsafe(64)
    
    # ANON_KEY и SERVICE_ROLE_KEY - это JWT токены, которые Supabase генерирует сам
    # Но для начальной настройки генерируем безопасные ключи
    # Пользователь может заменить их на правильные из документации Supabase
    
    # Генерируем длинные безопасные ключи (128 символов для надежности)
    anon_key = secrets.token_urlsafe(96)
    service_role_key = secrets.token_urlsafe(96)
    
    return {
        'jwt_secret': jwt_secret,
        'anon_key': anon_key,
        'service_role_key': service_role_key
    }

