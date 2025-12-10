"""
Модуль генерации конфигурационных файлов
"""
import os
import subprocess
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
    supabase_public_url = f"http://localhost:{config.get('supabase_kb_port', 3000)}"
    
    # Получаем домены и email для проверки
    n8n_domain = config.get('n8n_domain', '') or ''
    langflow_domain = config.get('langflow_domain', '') or ''
    supabase_domain = config.get('supabase_domain', '') or ''
    ollama_domain = config.get('ollama_domain', '') or ''
    letsencrypt_email = config.get('letsencrypt_email', '') or ''
    ollama_enabled = config.get('ollama_enabled', False)
    
    if routing_mode == 'subdomain':
        # Если домены указаны и есть email для SSL, используем HTTPS
        if n8n_domain and letsencrypt_email:
            n8n_protocol = 'https'
            webhook_url = f"https://{n8n_domain}/"
        
        if supabase_domain and letsencrypt_email:
            supabase_public_url = f"https://{supabase_domain}"
    
    # Заменяем переменные
    replacements = {
        'ROUTING_MODE': routing_mode,
        'N8N_DOMAIN': n8n_domain,
        'LANGFLOW_DOMAIN': langflow_domain,
        'SUPABASE_DOMAIN': supabase_domain,
        'OLLAMA_DOMAIN': ollama_domain,
        'BASE_DOMAIN': config.get('base_domain', ''),
        'N8N_PATH': config.get('n8n_path', '/n8n'),
        'LANGFLOW_PATH': config.get('langflow_path', '/langflow'),
        'SUPABASE_PATH': config.get('supabase_path', '/supabase'),
        'OLLAMA_PATH': config.get('ollama_path', '/ollama'),
        'LETSENCRYPT_EMAIL': letsencrypt_email,
        'N8N_PORT': str(config.get('n8n_port', 5678)),
        'LANGFLOW_PORT': str(config.get('langflow_port', 7860)),
        'SUPABASE_PORT': str(config.get('supabase_port', 8000)),
        'SUPABASE_KB_PORT': str(config.get('supabase_kb_port', 3000)),
        'OLLAMA_PORT': str(config.get('ollama_port', 11434)),
        'N8N_MEMORY_LIMIT': config.get('n8n_memory_limit', '2g'),
        'LANGFLOW_MEMORY_LIMIT': config.get('langflow_memory_limit', '4g'),
        'SUPABASE_MEMORY_LIMIT': config.get('supabase_memory_limit', '1g'),
        'OLLAMA_MEMORY_LIMIT': config.get('ollama_memory_limit', '2g'),
        'N8N_CPU_LIMIT': str(config.get('n8n_cpu_limit', 0.5)),
        'LANGFLOW_CPU_LIMIT': str(config.get('langflow_cpu_limit', 0.5)),
        'SUPABASE_CPU_LIMIT': str(config.get('supabase_cpu_limit', 0.3)),
        'OLLAMA_CPU_LIMIT': str(config.get('ollama_cpu_limit', 1.0)),
        'SUPABASE_ADMIN_PASSWORD': config.get('supabase_admin_password', ''),
        'POSTGRES_PASSWORD': config.get('postgres_password', generate_password()),
        'SUPABASE_ADMIN_LOGIN': config.get('supabase_admin_login', 'admin'),
        'SUPABASE_ADMIN_PASSWORD': config.get('supabase_admin_password', ''),
        'SUPABASE_ADMIN_PASSWORD_HASH': config.get('supabase_admin_password_hash', ''),
        'JWT_SECRET': config.get('jwt_secret', ''),
        'ANON_KEY': config.get('anon_key', ''),
        'SERVICE_ROLE_KEY': config.get('service_role_key', ''),
        'OLLAMA_ENABLED': 'true' if ollama_enabled else 'false',
        'N8N_PROTOCOL': n8n_protocol,
        'WEBHOOK_URL': webhook_url,
        'SUPABASE_PUBLIC_URL': supabase_public_url,
        # Переменные для nginx-proxy (заполняются только если routing_mode=subdomain и домены указаны)
        'VIRTUAL_HOST_N8N': n8n_domain if routing_mode == 'subdomain' else '',
        'LETSENCRYPT_HOST_N8N': n8n_domain if routing_mode == 'subdomain' and n8n_domain and letsencrypt_email else '',
        'VIRTUAL_HOST_LANGFLOW': langflow_domain if routing_mode == 'subdomain' else '',
        'LETSENCRYPT_HOST_LANGFLOW': langflow_domain if routing_mode == 'subdomain' and langflow_domain and letsencrypt_email else '',
        'VIRTUAL_HOST_SUPABASE': supabase_domain if routing_mode == 'subdomain' else '',
        'LETSENCRYPT_HOST_SUPABASE': supabase_domain if routing_mode == 'subdomain' and supabase_domain and letsencrypt_email else '',
        'VIRTUAL_HOST_OLLAMA': ollama_domain if routing_mode == 'subdomain' and ollama_enabled else '',
        'LETSENCRYPT_HOST_OLLAMA': ollama_domain if routing_mode == 'subdomain' and ollama_enabled and ollama_domain and letsencrypt_email else '',
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
N8N_PROTOCOL={N8N_PROTOCOL}
N8N_HOST=0.0.0.0
WEBHOOK_URL={WEBHOOK_URL}
N8N_MEMORY_LIMIT={N8N_MEMORY_LIMIT}
N8N_CPU_LIMIT={N8N_CPU_LIMIT}
# Переменные для nginx-proxy (автоматически заполняются при ROUTING_MODE=subdomain)
VIRTUAL_HOST_N8N={VIRTUAL_HOST_N8N}
LETSENCRYPT_HOST_N8N={LETSENCRYPT_HOST_N8N}

# ============================================
# LANGFLOW
# ============================================
LANGFLOW_VERSION=latest
LANGFLOW_PORT={LANGFLOW_PORT}
LANGFLOW_MEMORY_LIMIT={LANGFLOW_MEMORY_LIMIT}
LANGFLOW_CPU_LIMIT={LANGFLOW_CPU_LIMIT}
# Переменные для nginx-proxy (автоматически заполняются при ROUTING_MODE=subdomain)
VIRTUAL_HOST_LANGFLOW={VIRTUAL_HOST_LANGFLOW}
LETSENCRYPT_HOST_LANGFLOW={LETSENCRYPT_HOST_LANGFLOW}

# ============================================
# SUPABASE
# ============================================
SUPABASE_VERSION=latest
SUPABASE_PORT={SUPABASE_PORT}
SUPABASE_KB_PORT={SUPABASE_KB_PORT}
SUPABASE_PUBLIC_URL={SUPABASE_PUBLIC_URL}
SUPABASE_MEMORY_LIMIT={SUPABASE_MEMORY_LIMIT}
SUPABASE_CPU_LIMIT={SUPABASE_CPU_LIMIT}
POSTGRES_PASSWORD={POSTGRES_PASSWORD}
SUPABASE_ADMIN_LOGIN={SUPABASE_ADMIN_LOGIN}
JWT_SECRET={JWT_SECRET}
ANON_KEY={ANON_KEY}
SERVICE_ROLE_KEY={SERVICE_ROLE_KEY}
# Переменные для nginx-proxy (автоматически заполняются при ROUTING_MODE=subdomain)
VIRTUAL_HOST_SUPABASE={VIRTUAL_HOST_SUPABASE}
LETSENCRYPT_HOST_SUPABASE={LETSENCRYPT_HOST_SUPABASE}

# ============================================
# OLLAMA (опционально)
# ============================================
OLLAMA_ENABLED={OLLAMA_ENABLED}
OLLAMA_VERSION=latest
OLLAMA_PORT={OLLAMA_PORT}
OLLAMA_MEMORY_LIMIT={OLLAMA_MEMORY_LIMIT}
OLLAMA_CPU_LIMIT={OLLAMA_CPU_LIMIT}
# Переменные для nginx-proxy (автоматически заполняются при ROUTING_MODE=subdomain)
VIRTUAL_HOST_OLLAMA={VIRTUAL_HOST_OLLAMA}
LETSENCRYPT_HOST_OLLAMA={LETSENCRYPT_HOST_OLLAMA}

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
    
    # Если Ollama включен, добавляем его в CPU шаблон
    if template_name == "docker-compose.cpu.template" and ollama_enabled:
        # Проверяем, есть ли уже секция ollama
        if '  ollama:' not in content:
            import re
            # Находим место перед caddy для вставки ollama
            ollama_service = f"""  ollama:
    image: ${{OLLAMA_IMAGE:-ollama/ollama:latest}}
    container_name: ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
    # ВАЖНО: Не открываем порт наружу напрямую! Прокси через Caddy.
    # ports:
    #   - "${{OLLAMA_PORT}}:11434"
    deploy:
      resources:
        limits:
          memory: ${{OLLAMA_MEMORY_LIMIT}}
          cpus: '${{OLLAMA_CPU_LIMIT}}'
        reservations:
          memory: ${{OLLAMA_MEMORY_LIMIT}}
          cpus: '${{OLLAMA_CPU_LIMIT}}'
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - proxy
    restart: unless-stopped
    entrypoint: |
      sh -c "
        mkdir -p /root/.ollama
        chmod -R 755 /root/.ollama || true
        exec /bin/ollama serve
      "
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

"""
            # Вставляем перед caddy
            content = re.sub(r'(\n  caddy:)', r'\n' + ollama_service + r'\1', content)
            # Добавляем ollama_data в volumes если его нет
            if '  ollama_data:' not in content:
                content = re.sub(r'(  caddy_config:\s*driver: local\n)', r'\1  ollama_data:\n    driver: local\n', content)
    
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


def hash_password_for_caddy(password: str) -> str:
    """
    Генерирует bcrypt хеш пароля для Caddy basicauth
    Использует команду caddy hash-password если доступна, иначе использует bcrypt
    """
    # Пытаемся использовать caddy hash-password (если Caddy установлен локально)
    try:
        result = subprocess.run(
            ['caddy', 'hash-password', '--plaintext', password],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Если caddy недоступен, используем bcrypt через Python
    try:
        import bcrypt
        # Генерируем bcrypt хеш с cost factor 10 (стандарт для Caddy)
        salt = bcrypt.gensalt(rounds=10)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except ImportError:
        # Если bcrypt не установлен, генерируем хеш через Docker контейнер Caddy
        # Это работает если Docker доступен
        try:
            result = subprocess.run(
                ['docker', 'run', '--rm', 'caddy:latest', 'caddy', 'hash-password', '--plaintext', password],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Если ничего не работает, возвращаем пустую строку и выводим предупреждение
        # Пользователю нужно будет вручную сгенерировать хеш
        print(f"⚠️  Не удалось автоматически сгенерировать хеш пароля для Caddy basicauth.")
        print(f"   Установите bcrypt: pip install bcrypt")
        print(f"   Или используйте команду: docker run --rm caddy:latest caddy hash-password --plaintext '{password}'")
        return ''


def generate_caddyfile(config: Dict, output_path: str = "Caddyfile") -> None:
    """
    Генерирует Caddyfile из конфигурации
    """
    template_path = get_project_root() / "Caddyfile.template"
    
    if not template_path.exists():
        # Создаем базовый Caddyfile если шаблона нет
        content = generate_base_caddyfile_template()
    else:
        content = template_path.read_text(encoding='utf-8')
    
    routing_mode = config.get('routing_mode', '')
    letsencrypt_email = config.get('letsencrypt_email', '') or ''
    
    # Получаем домены
    n8n_domain = config.get('n8n_domain', '') or 'localhost'
    langflow_domain = config.get('langflow_domain', '') or 'localhost'
    supabase_domain = config.get('supabase_domain', '') or 'localhost'
    ollama_domain = config.get('ollama_domain', '') or 'localhost'
    ollama_enabled = config.get('ollama_enabled', False)
    
    # Если режим поддоменов, используем домены, иначе localhost
    if routing_mode == 'subdomain':
        # Используем реальные домены
        n8n_domain = n8n_domain or 'n8n.localhost'
        langflow_domain = langflow_domain or 'langflow.localhost'
        supabase_domain = supabase_domain or 'supabase.localhost'
        ollama_domain = ollama_domain or 'ollama.localhost'
    else:
        # Для режима портов не используем Caddy, но оставляем localhost для совместимости
        n8n_domain = 'localhost'
        langflow_domain = 'localhost'
        supabase_domain = 'localhost'
        ollama_domain = 'localhost'
    
    # Генерируем хеш пароля для Supabase Studio basicauth
    supabase_admin_login = config.get('supabase_admin_login', 'admin')
    supabase_admin_password = config.get('supabase_admin_password', '')
    # Используем уже сгенерированный хеш из конфига, если есть
    supabase_password_hash = config.get('supabase_admin_password_hash', '')
    
    # Если хеш не задан, но есть пароль - генерируем хеш
    if not supabase_password_hash and supabase_admin_password:
        supabase_password_hash = hash_password_for_caddy(supabase_admin_password)
    
    # Если хеш не сгенерирован, удаляем секцию basic_auth из Supabase Studio
    if not supabase_password_hash:
        import re
        # Удаляем блок basic_auth для Supabase Studio
        basicauth_pattern = r'    basic_auth \{[^}]*\{SUPABASE_ADMIN_LOGIN\}[^}]*\{SUPABASE_ADMIN_PASSWORD_HASH\}[^}]*\}\n'
        content = re.sub(basicauth_pattern, '', content)
    
    # Заменяем переменные
    replacements = {
        'CADDY_EMAIL': letsencrypt_email or 'admin@example.com',
        'N8N_DOMAIN': n8n_domain,
        'LANGFLOW_DOMAIN': langflow_domain,
        'SUPABASE_DOMAIN': supabase_domain,
        'OLLAMA_DOMAIN': ollama_domain if ollama_enabled else '',
        'SUPABASE_ADMIN_LOGIN': supabase_admin_login,
        'SUPABASE_ADMIN_PASSWORD_HASH': supabase_password_hash,
    }
    
    # Заменяем все переменные
    for key, value in replacements.items():
        content = content.replace(f'{{{key}}}', str(value))
    
    # Удаляем секцию Ollama если она не включена
    if not ollama_enabled:
        import re
        ollama_pattern = r'# Ollama.*?\n\n'
        content = re.sub(ollama_pattern, '', content, flags=re.DOTALL)
    
    write_file(output_path, content)


def generate_base_caddyfile_template() -> str:
    """Генерирует базовый шаблон Caddyfile"""
    return """{
    email admin@example.com
    auto_https disable_redirects
}

# N8N
localhost {
    reverse_proxy n8n:5678
}

# Langflow
localhost {
    reverse_proxy langflow:7860
}

# Supabase Studio
localhost {
    reverse_proxy supabase-studio:3000
}
"""


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
      - LANGFLOW_HOST=0.0.0.0
      - LANGFLOW_PORT=7860
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

