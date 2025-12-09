"""
Модуль генерации конфигурационных файлов
"""
import os
from pathlib import Path
from typing import Dict, Optional
from installer.utils import (
    get_project_root, read_template, write_file,
    generate_secret_key, generate_password
)


def generate_env_file(config: Dict, output_path: str = ".env") -> None:
    """
    Генерирует .env файл из конфигурации
    """
    template_path = get_project_root() / "templates" / "env.template"
    
    if template_path.exists():
        content = template_path.read_text(encoding='utf-8')
    else:
        # Базовый шаблон если файла нет
        content = generate_base_env_template()
    
    # Определяем протокол и URL для n8n в зависимости от режима маршрутизации
    routing_mode = config.get('routing_mode', '')
    n8n_protocol = 'http'
    webhook_url = f"http://localhost:{config.get('n8n_port', 5678)}/"
    supabase_public_url = f"http://localhost:{config.get('supabase_port', 8000)}"
    
    if routing_mode == 'subdomain':
        n8n_domain = config.get('n8n_domain', '')
        supabase_domain = config.get('supabase_domain', '')
        letsencrypt_email = config.get('letsencrypt_email', '')
        
        if n8n_domain and letsencrypt_email:
            n8n_protocol = 'https'
            webhook_url = f"https://{n8n_domain}/"
        
        if supabase_domain and letsencrypt_email:
            supabase_public_url = f"https://{supabase_domain}"
    
    # Заменяем переменные
    replacements = {
        'ROUTING_MODE': routing_mode,
        'N8N_DOMAIN': config.get('n8n_domain', ''),
        'LANGFLOW_DOMAIN': config.get('langflow_domain', ''),
        'SUPABASE_DOMAIN': config.get('supabase_domain', ''),
        'OLLAMA_DOMAIN': config.get('ollama_domain', ''),
        'BASE_DOMAIN': config.get('base_domain', ''),
        'N8N_PATH': config.get('n8n_path', '/n8n'),
        'LANGFLOW_PATH': config.get('langflow_path', '/langflow'),
        'SUPABASE_PATH': config.get('supabase_path', '/supabase'),
        'OLLAMA_PATH': config.get('ollama_path', '/ollama'),
        'LETSENCRYPT_EMAIL': config.get('letsencrypt_email', ''),
        'N8N_PORT': str(config.get('n8n_port', 5678)),
        'LANGFLOW_PORT': str(config.get('langflow_port', 7860)),
        'SUPABASE_PORT': str(config.get('supabase_port', 8000)),
        'SUPABASE_KB_PORT': str(config.get('supabase_kb_port', 3000)),
        'OLLAMA_PORT': str(config.get('ollama_port', 11434)),
        'N8N_MEMORY_LIMIT': config.get('n8n_memory_limit', '2g'),
        'LANGFLOW_MEMORY_LIMIT': config.get('langflow_memory_limit', '2g'),
        'SUPABASE_MEMORY_LIMIT': config.get('supabase_memory_limit', '1g'),
        'OLLAMA_MEMORY_LIMIT': config.get('ollama_memory_limit', '2g'),
        'N8N_CPU_LIMIT': str(config.get('n8n_cpu_limit', 0.5)),
        'LANGFLOW_CPU_LIMIT': str(config.get('langflow_cpu_limit', 0.5)),
        'SUPABASE_CPU_LIMIT': str(config.get('supabase_cpu_limit', 0.3)),
        'OLLAMA_CPU_LIMIT': str(config.get('ollama_cpu_limit', 1.0)),
        'LANGFLOW_API_KEY': config.get('langflow_api_key', ''),
        'POSTGRES_PASSWORD': config.get('postgres_password', generate_password()),
        'SUPABASE_ADMIN_LOGIN': config.get('supabase_admin_login', 'admin'),
        'JWT_SECRET': config.get('jwt_secret', ''),
        'ANON_KEY': config.get('anon_key', ''),
        'SERVICE_ROLE_KEY': config.get('service_role_key', ''),
        'OLLAMA_ENABLED': 'true' if config.get('ollama_enabled', False) else 'false',
        'N8N_PROTOCOL': n8n_protocol,
        'WEBHOOK_URL': webhook_url,
        'SUPABASE_PUBLIC_URL': supabase_public_url,
        # Переменные для nginx-proxy
        'VIRTUAL_HOST_N8N': config.get('n8n_domain', '') if routing_mode == 'subdomain' else '',
        'LETSENCRYPT_HOST_N8N': config.get('n8n_domain', '') if routing_mode == 'subdomain' and config.get('letsencrypt_email') else '',
        'VIRTUAL_HOST_LANGFLOW': config.get('langflow_domain', '') if routing_mode == 'subdomain' else '',
        'LETSENCRYPT_HOST_LANGFLOW': config.get('langflow_domain', '') if routing_mode == 'subdomain' and config.get('letsencrypt_email') else '',
        'VIRTUAL_HOST_SUPABASE': config.get('supabase_domain', '') if routing_mode == 'subdomain' else '',
        'LETSENCRYPT_HOST_SUPABASE': config.get('supabase_domain', '') if routing_mode == 'subdomain' and config.get('letsencrypt_email') else '',
        'VIRTUAL_HOST_OLLAMA': config.get('ollama_domain', '') if routing_mode == 'subdomain' and config.get('ollama_enabled') else '',
        'LETSENCRYPT_HOST_OLLAMA': config.get('ollama_domain', '') if routing_mode == 'subdomain' and config.get('ollama_enabled') and config.get('letsencrypt_email') else '',
    }
    
    # Заменяем все переменные в шаблоне
    for key, value in replacements.items():
        content = content.replace(f'{{{key}}}', str(value))
    
    write_file(output_path, content)


def generate_base_env_template() -> str:
    """Генерирует базовый шаблон .env если файла нет"""
    return """# ============================================
# РЕЖИМ МАРШРУТИЗАЦИИ
# ============================================
ROUTING_MODE={ROUTING_MODE}

# ============================================
# РЕЖИМ ПОДДОМЕНОВ (если ROUTING_MODE=subdomain)
# ============================================
N8N_DOMAIN={N8N_DOMAIN}
LANGFLOW_DOMAIN={LANGFLOW_DOMAIN}
SUPABASE_DOMAIN={SUPABASE_DOMAIN}
OLLAMA_DOMAIN={OLLAMA_DOMAIN}

# ============================================
# РЕЖИМ ПУТЕЙ (если ROUTING_MODE=path)
# ============================================
BASE_DOMAIN={BASE_DOMAIN}
N8N_PATH={N8N_PATH}
LANGFLOW_PATH={LANGFLOW_PATH}
SUPABASE_PATH={SUPABASE_PATH}
OLLAMA_PATH={OLLAMA_PATH}

# ============================================
# SSL/TLS
# ============================================
LETSENCRYPT_EMAIL={LETSENCRYPT_EMAIL}
SSL_ENABLED=true

# ============================================
# N8N
# ============================================
N8N_VERSION=latest
N8N_PORT={N8N_PORT}
N8N_MEMORY_LIMIT={N8N_MEMORY_LIMIT}
N8N_CPU_LIMIT={N8N_CPU_LIMIT}

# ============================================
# LANGFLOW
# ============================================
LANGFLOW_VERSION=latest
LANGFLOW_PORT={LANGFLOW_PORT}
LANGFLOW_MEMORY_LIMIT={LANGFLOW_MEMORY_LIMIT}
LANGFLOW_CPU_LIMIT={LANGFLOW_CPU_LIMIT}
LANGFLOW_API_KEY={LANGFLOW_API_KEY}

# ============================================
# SUPABASE
# ============================================
SUPABASE_VERSION=latest
SUPABASE_PORT={SUPABASE_PORT}
SUPABASE_MEMORY_LIMIT={SUPABASE_MEMORY_LIMIT}
SUPABASE_CPU_LIMIT={SUPABASE_CPU_LIMIT}
POSTGRES_PASSWORD={POSTGRES_PASSWORD}
SUPABASE_ADMIN_LOGIN={SUPABASE_ADMIN_LOGIN}
JWT_SECRET={JWT_SECRET}
ANON_KEY={ANON_KEY}
SERVICE_ROLE_KEY={SERVICE_ROLE_KEY}

# ============================================
# OLLAMA (опционально)
# ============================================
OLLAMA_ENABLED={OLLAMA_ENABLED}
OLLAMA_VERSION=latest
OLLAMA_PORT={OLLAMA_PORT}
OLLAMA_MEMORY_LIMIT={OLLAMA_MEMORY_LIMIT}
OLLAMA_CPU_LIMIT={OLLAMA_CPU_LIMIT}

# Примечание: OpenRouter подключается через API в сервисах (n8n, Langflow)
# Не требует настройки здесь
"""


def generate_docker_compose(config: Dict, hardware: Dict, output_path: str = "docker-compose.yml") -> None:
    """
    Генерирует docker-compose.yml файл
    """
    # Определяем какой шаблон использовать
    ollama_enabled = config.get('ollama_enabled', False)
    has_gpu = hardware.get('gpu', {}).get('available', False)
    
    if has_gpu and ollama_enabled:
        template_name = "docker-compose.gpu.template"
    else:
        template_name = "docker-compose.cpu.template"
    
    try:
        content = read_template(template_name)
    except FileNotFoundError:
        # Если шаблона нет, генерируем базовый
        content = generate_base_docker_compose(config, hardware)
        write_file(output_path, content)
        return
    
    # Если Ollama не включен, удаляем его из GPU шаблона
    if template_name == "docker-compose.gpu.template" and not ollama_enabled:
        # Удаляем секцию ollama
        import re
        ollama_pattern = r'  ollama:.*?(?=\n  [a-z]|\nvolumes:|\Z)'
        content = re.sub(ollama_pattern, '', content, flags=re.DOTALL)
        # Удаляем ollama_data из volumes
        content = re.sub(r'  ollama_data:\s*driver: local\n', '', content)
    
    # Шаблоны уже используют ${VAR} синтаксис, поэтому просто записываем как есть
    # Но нужно добавить env_file если его нет
    if 'env_file:' not in content and 'x-env-file:' not in content:
        import re
        # Убираем устаревший version и добавляем x-env-file
        # Удаляем строку version если есть
        content = re.sub(r"^version:\s*['\"]?3\.8['\"]?\s*\n", "", content, flags=re.MULTILINE)
        # Добавляем x-env-file в начало файла
        if not content.startswith('x-env-file'):
            content = "x-env-file: &env-file\n  env_file:\n    - .env\n\n" + content
        # Добавляем ссылку на env_file в каждый сервис
        # Ищем начало каждого сервиса (строки "  имя_сервиса:") и добавляем после них env_file
        # Заменяем паттерн: "  имя:\n    image:" на "  имя:\n    <<: *env-file\n    image:"
        pattern = r'(^  [a-z-]+:\n)(    image:)'
        replacement = r'\1    <<: *env-file\n\2'
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    write_file(output_path, content)


def generate_base_docker_compose(config: Dict, hardware: Dict) -> str:
    """Генерирует базовый docker-compose.yml"""
    # Это будет упрощенная версия, полная версия будет в шаблоне
    return """version: '3.8'

services:
  n8n:
    image: n8nio/n8n:latest
    ports:
      - "{N8N_PORT}:5678"
    environment:
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678
    deploy:
      resources:
        limits:
          memory: {N8N_MEMORY_LIMIT}
          cpus: '{N8N_CPU_LIMIT}'
    volumes:
      - n8n_data:/home/node/.n8n
    restart: unless-stopped

  langflow:
    image: langflowai/langflow:latest
    ports:
      - "{LANGFLOW_PORT}:7860"
    environment:
      - LANGFLOW_API_KEY={LANGFLOW_API_KEY}
    deploy:
      resources:
        limits:
          memory: {LANGFLOW_MEMORY_LIMIT}
          cpus: '{LANGFLOW_CPU_LIMIT}'
    volumes:
      - langflow_data:/app/data
    restart: unless-stopped

  supabase:
    image: supabase/postgres:latest
    ports:
      - "{SUPABASE_PORT}:5432"
    environment:
      - POSTGRES_PASSWORD={POSTGRES_PASSWORD}
    deploy:
      resources:
        limits:
          memory: {SUPABASE_MEMORY_LIMIT}
          cpus: '{SUPABASE_CPU_LIMIT}'
    volumes:
      - supabase_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  n8n_data:
  langflow_data:
  supabase_data:
"""

