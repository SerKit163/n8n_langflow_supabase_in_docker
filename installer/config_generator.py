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
    
    # Проверяем какие сервисы включены
    n8n_enabled = config.get('n8n_enabled', True)
    langflow_enabled = config.get('langflow_enabled', True)
    # Supabase всегда включен
    
    # Настраиваем CORS для Langflow
    # Если есть домен, используем его с протоколом, иначе *
    if langflow_enabled and langflow_domain and routing_mode == 'subdomain' and letsencrypt_email:
        # Используем домен с HTTPS и HTTP
        langflow_cors_origins = f"https://{langflow_domain},http://{langflow_domain}"
    elif langflow_enabled and langflow_domain:
        # Используем домен с HTTP
        langflow_cors_origins = f"http://{langflow_domain}"
    else:
        # Используем * для локальной разработки
        langflow_cors_origins = '*'
    
    # Для отключенных сервисов используем пустые значения или значения по умолчанию только если включены
    # Заменяем переменные
    replacements = {
        'PROXY_TYPE': config.get('proxy_type', 'caddy'),
        'ROUTING_MODE': routing_mode,
        'N8N_ENABLED': 'true' if n8n_enabled else 'false',
        'LANGFLOW_ENABLED': 'true' if langflow_enabled else 'false',
        'N8N_DOMAIN': n8n_domain if n8n_enabled else '',
        'LANGFLOW_DOMAIN': langflow_domain if langflow_enabled else '',
        'SUPABASE_DOMAIN': supabase_domain,
        'OLLAMA_DOMAIN': ollama_domain if ollama_enabled else '',
        'BASE_DOMAIN': config.get('base_domain', ''),
        'N8N_PATH': config.get('n8n_path', '/n8n') if n8n_enabled else '',
        'LANGFLOW_PATH': config.get('langflow_path', '/langflow') if langflow_enabled else '',
        'SUPABASE_PATH': config.get('supabase_path', '/supabase'),
        'OLLAMA_PATH': config.get('ollama_path', '/ollama') if ollama_enabled else '',
        'LETSENCRYPT_EMAIL': letsencrypt_email,
        'LETSENCRYPT_STAGING': 'true' if config.get('letsencrypt_staging', False) else 'false',
        'N8N_PORT': str(config.get('n8n_port', 5678)) if n8n_enabled else '',
        'LANGFLOW_PORT': str(config.get('langflow_port', 7860)) if langflow_enabled else '',
        'SUPABASE_PORT': str(config.get('supabase_port', 8000)),
        'SUPABASE_KB_PORT': str(config.get('supabase_kb_port', 3000)),
        'OLLAMA_PORT': str(config.get('ollama_port', 11434)) if ollama_enabled else '',
        'N8N_MEMORY_LIMIT': config.get('n8n_memory_limit', '2g') if n8n_enabled else '',
        'LANGFLOW_MEMORY_LIMIT': config.get('langflow_memory_limit', '4g') if langflow_enabled else '',
        'SUPABASE_MEMORY_LIMIT': config.get('supabase_memory_limit', '1g'),
        'OLLAMA_MEMORY_LIMIT': config.get('ollama_memory_limit', '2g') if ollama_enabled else '',
        'N8N_CPU_LIMIT': str(config.get('n8n_cpu_limit', 0.5)) if n8n_enabled else '',
        'LANGFLOW_CPU_LIMIT': str(config.get('langflow_cpu_limit', 0.5)) if langflow_enabled else '',
        'SUPABASE_CPU_LIMIT': str(config.get('supabase_cpu_limit', 0.3)),
        'OLLAMA_CPU_LIMIT': str(config.get('ollama_cpu_limit', 1.0)) if ollama_enabled else '',
        'SUPABASE_ADMIN_PASSWORD': config.get('supabase_admin_password', ''),
        'POSTGRES_PASSWORD': config.get('postgres_password', generate_password()),
        'SUPABASE_ADMIN_LOGIN': config.get('supabase_admin_login', 'admin'),
        'SUPABASE_ADMIN_PASSWORD': config.get('supabase_admin_password', ''),
        'SUPABASE_ADMIN_PASSWORD_HASH': config.get('supabase_admin_password_hash', ''),
        'JWT_SECRET': config.get('jwt_secret', ''),
        'ANON_KEY': config.get('anon_key', ''),
        'SERVICE_ROLE_KEY': config.get('service_role_key', ''),
        'OLLAMA_ENABLED': 'true' if ollama_enabled else 'false',
        'N8N_PROTOCOL': n8n_protocol if n8n_enabled else '',
        'WEBHOOK_URL': webhook_url if n8n_enabled else '',
        'SUPABASE_PUBLIC_URL': supabase_public_url,
        'LANGFLOW_CORS_ORIGINS': langflow_cors_origins if langflow_enabled else '*',
        # Если Langflow включен и настроен суперпользователь, отключаем авто-логин
        'LANGFLOW_AUTO_LOGIN': 'false' if (langflow_enabled and config.get('langflow_superuser')) else 'true',
        'LANGFLOW_SUPERUSER': config.get('langflow_superuser', '') if langflow_enabled else '',
        'LANGFLOW_SUPERUSER_PASSWORD': config.get('langflow_superuser_password', '') if langflow_enabled else '',
        'LANGFLOW_SECRET_KEY': config.get('langflow_secret_key', '') if langflow_enabled else '',
        # Новые пользователи неактивны по умолчанию (требуют активации администратором)
        'LANGFLOW_NEW_USER_IS_ACTIVE': 'false' if langflow_enabled else 'true',
        # Переменные для nginx-proxy (заполняются только если routing_mode=subdomain и домены указаны)
        'VIRTUAL_HOST_N8N': n8n_domain if routing_mode == 'subdomain' and n8n_enabled else '',
        'LETSENCRYPT_HOST_N8N': n8n_domain if routing_mode == 'subdomain' and n8n_enabled and n8n_domain and letsencrypt_email else '',
        'VIRTUAL_HOST_LANGFLOW': langflow_domain if routing_mode == 'subdomain' and langflow_enabled else '',
        'LETSENCRYPT_HOST_LANGFLOW': langflow_domain if routing_mode == 'subdomain' and langflow_enabled and langflow_domain and letsencrypt_email else '',
        'VIRTUAL_HOST_SUPABASE': supabase_domain if routing_mode == 'subdomain' else '',
        'LETSENCRYPT_HOST_SUPABASE': supabase_domain if routing_mode == 'subdomain' and supabase_domain and letsencrypt_email else '',
        'VIRTUAL_HOST_OLLAMA': ollama_domain if routing_mode == 'subdomain' and ollama_enabled else '',
        'LETSENCRYPT_HOST_OLLAMA': ollama_domain if routing_mode == 'subdomain' and ollama_enabled and ollama_domain and letsencrypt_email else '',
    }
    
    # Функция для экранирования значений, которые могут содержать специальные символы Docker Compose
    def escape_docker_value(value: str) -> str:
        """
        Экранирует специальные символы в значениях для Docker Compose
        Экранирует $ как $$ чтобы предотвратить интерпретацию как переменной
        """
        if not isinstance(value, str):
            value = str(value)
        # Экранируем $ как $$ (Docker Compose синтаксис для экранирования)
        # Это предотвратит интерпретацию подстрок вида ${something} как переменных
        # Заменяем все $ на $$, кроме тех, которые уже экранированы ($$)
        import re
        # Экранируем $ которые не являются частью уже экранированного $$
        # Паттерн: $ который не предшествует другому $
        value = re.sub(r'(?<!\$)\$(?!\$)', '$$', value)
        return value
    
    # Заменяем все переменные в шаблоне
    # Для секретов и паролей экранируем специальные символы
    secret_keys = ['POSTGRES_PASSWORD', 'SUPABASE_ADMIN_PASSWORD', 'JWT_SECRET', 
                   'ANON_KEY', 'SERVICE_ROLE_KEY', 'SUPABASE_ADMIN_PASSWORD_HASH',
                   'LANGFLOW_SUPERUSER_PASSWORD', 'LANGFLOW_SECRET_KEY']
    
    for key, value in replacements.items():
        # Экранируем секреты и пароли
        if key in secret_keys:
            escaped_value = escape_docker_value(str(value))
            content = content.replace(f'{{{key}}}', escaped_value)
        else:
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
N8N_ENABLED={N8N_ENABLED}
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
LANGFLOW_ENABLED={LANGFLOW_ENABLED}
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
    proxy_type = config.get('proxy_type', 'caddy')
    
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
    
    # Заменяем Caddy на nginx-proxy если нужно
    if proxy_type == 'nginx-proxy':
        content = replace_caddy_with_nginx_proxy(content, config)
        # Добавляем переменные окружения для nginx-proxy
        if config.get('routing_mode') == 'subdomain':
            content = add_nginx_proxy_env_vars(content, config)
    
    # ВАЖНО: проверяем что ollama_enabled явно True
    if isinstance(ollama_enabled, str):
        ollama_enabled = ollama_enabled.lower() in ('true', '1', 'yes', 'on')
    
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
    
    # Проверяем какие сервисы включены
    n8n_enabled = config.get('n8n_enabled', True)
    langflow_enabled = config.get('langflow_enabled', True)
    # Supabase всегда включен
    
    # URL-кодируем пароль PostgreSQL для использования в connection string
    # Это необходимо для правильной обработки специальных символов (!, %, @ и т.д.)
    from urllib.parse import quote_plus
    postgres_password = config.get('postgres_password', '')
    postgres_password_encoded = quote_plus(postgres_password) if postgres_password else ''
    
    # Генерируем connection string с URL-кодированным паролем
    if postgres_password_encoded:
        postgres_connection_url = f"postgresql://postgres:{postgres_password_encoded}@supabase-db:5432/postgres"
    else:
        postgres_connection_url = "postgresql://postgres:${POSTGRES_PASSWORD}@supabase-db:5432/postgres"
    
    # Настраиваем CORS для Langflow
    # Если есть домен, используем его с протоколом, иначе *
    langflow_domain = config.get('langflow_domain', '') or ''
    letsencrypt_email = config.get('letsencrypt_email', '') or ''
    routing_mode = config.get('routing_mode', '')
    
    if langflow_enabled and langflow_domain and routing_mode == 'subdomain' and letsencrypt_email:
        # Используем домен с HTTPS
        langflow_cors_origins = f"https://{langflow_domain},http://{langflow_domain}"
    elif langflow_enabled and langflow_domain:
        # Используем домен с HTTP
        langflow_cors_origins = f"http://{langflow_domain}"
    else:
        # Используем * для локальной разработки
        langflow_cors_origins = '*'
    
    # Заменяем CORS в шаблоне
    import re
    content = re.sub(
        r'\$\{LANGFLOW_CORS_ORIGINS:-\*\}',
        langflow_cors_origins,
        content
    )
    
    # Заменяем connection strings в шаблоне на URL-кодированные версии
    # Заменяем все connection strings с ${POSTGRES_PASSWORD} на URL-кодированную версию
    if postgres_password_encoded:
        # Заменяем только в connection strings (не в переменных окружения POSTGRES_PASSWORD)
        content = re.sub(
            r'postgresql://postgres:\$\{POSTGRES_PASSWORD\}@supabase-db:5432/postgres',
            postgres_connection_url,
            content
        )
    
    # Удаляем невыбранные сервисы
    if not n8n_enabled:
        # Удаляем секцию n8n
        n8n_pattern = r'  n8n:.*?(?=\n  [a-z]|\nvolumes:|\Z)'
        content = re.sub(n8n_pattern, '', content, flags=re.DOTALL)
        # Удаляем n8n_data из volumes
        content = re.sub(r'  n8n_data:\s*driver: local\n', '', content)
    
    if not langflow_enabled:
        # Удаляем секцию langflow
        langflow_pattern = r'  langflow:.*?(?=\n  [a-z]|\nvolumes:|\Z)'
        content = re.sub(langflow_pattern, '', content, flags=re.DOTALL)
        # Удаляем langflow_data из volumes
        content = re.sub(r'  langflow_data:\s*driver: local\n', '', content)
    
    # Если Ollama не включен, удаляем его из шаблона (CPU или GPU)
    if not ollama_enabled:
        # Удаляем секцию ollama
        ollama_pattern = r'  ollama:.*?(?=\n  [a-z]|\nvolumes:|\Z)'
        content = re.sub(ollama_pattern, '', content, flags=re.DOTALL)
        # Удаляем ollama_data из volumes
        content = re.sub(r'  ollama_data:\s*driver: local\n', '', content)
    
    # Если режим 'none' (только порты), автоматически включаем порты
    routing_mode = config.get('routing_mode', '')
    use_direct_ports = config.get('use_direct_ports', False) or routing_mode == 'none'
    
    if use_direct_ports:
        import re
        # Раскомментируем порты для включенных сервисов
        if n8n_enabled:
            # Раскомментируем порты для n8n
            n8n_port = config.get('n8n_port', 5678)
            # Паттерн для закомментированных портов с переменными ${N8N_PORT}
            content = re.sub(
                r'(\s+n8n:[^\n]*\n(?:(?!\s+[a-z-]+:)[^\n]*\n)*?)(\s+)# ВАЖНО: Не открываем порт наружу напрямую! Прокси через Caddy\.\n(\s+)# ports:\n(\s+)#\s+- "\$\{N8N_PORT\}:\d+"',
                rf'\1\2# Прямой доступ через порт (режим без доменов)\n\3ports:\n\4  - "{n8n_port}:5678"',
                content,
                flags=re.MULTILINE
            )
        
        if langflow_enabled:
            # Раскомментируем порты для langflow
            langflow_port = config.get('langflow_port', 7860)
            # Паттерн для закомментированных портов
            content = re.sub(
                r'(\s+langflow:[^\n]*\n(?:(?!\s+[a-z-]+:)[^\n]*\n)*?)(\s+)# ВАЖНО: Не открываем порт наружу напрямую! Прокси через Caddy\.\n(\s+)# ports:\n(\s+)#\s+- "\d+:\d+"',
                rf'\1\2# Прямой доступ через порт (режим без доменов)\n\3ports:\n\4  - "{langflow_port}:7860"',
                content,
                flags=re.MULTILINE
            )
        
        # Раскомментируем порты для supabase-studio
        supabase_port = config.get('supabase_kb_port', 3000)
        # Паттерн для закомментированных портов с переменными ${SUPABASE_KB_PORT}
        # Формат в шаблоне: "127.0.0.1:${SUPABASE_KB_PORT:-3000}:3000"
        content = re.sub(
            r'(\s+supabase-studio:[^\n]*\n(?:(?!\s+[a-z-]+:)[^\n]*\n)*?)(\s+)# ВАЖНО: Не открываем порт наружу напрямую! Прокси через Caddy\.\n(\s+)# ports:\n(\s+)#\s+- "127\.0\.0\.1:\$\{SUPABASE_KB_PORT[^"]+\}:\d+"',
            rf'\1\2# Прямой доступ через порт (режим без доменов)\n\3ports:\n\4  - "{supabase_port}:3000"',
            content,
            flags=re.MULTILINE
        )
    
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


def replace_caddy_with_nginx_proxy(content: str, config: Dict) -> str:
    """Заменяет секцию Caddy на nginx-proxy и acme-companion"""
    import re
    
    # Удаляем секцию caddy
    caddy_pattern = r'  caddy:.*?(?=\n  [a-z]|\nvolumes:|\Z)'
    content = re.sub(caddy_pattern, '', content, flags=re.DOTALL)
    
    # Удаляем caddy volumes
    content = re.sub(r'  caddy_data:\s*driver: local\n', '', content)
    content = re.sub(r'  caddy_config:\s*driver: local\n', '', content)
    
    # Определяем ACME CA URI для staging
    letsencrypt_staging = config.get('letsencrypt_staging', False)
    acme_ca_uri = 'https://acme-staging-v02.api.letsencrypt.org/directory' if letsencrypt_staging else ''
    acme_ca_env = f'\n      - ACME_CA_URI={acme_ca_uri}' if acme_ca_uri else ''
    
    # Добавляем nginx-proxy и acme-companion перед volumes
    nginx_proxy_section = f"""  nginx-proxy:
    image: nginxproxy/nginx-proxy:latest
    container_name: nginx-proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/tmp/docker.sock:ro
      - nginx_proxy_certs:/etc/nginx/certs:ro
      - nginx_proxy_vhost:/etc/nginx/vhost.d
      - nginx_proxy_html:/usr/share/nginx/html
    networks:
      - proxy
    restart: unless-stopped
    labels:
      - "com.github.nginx-proxy.nginx-proxy"

  nginx-proxy-acme:
    image: nginxproxy/acme-companion:latest
    container_name: nginx-proxy-acme
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - nginx_proxy_certs:/etc/nginx/certs:rw
      - nginx_proxy_vhost:/etc/nginx/vhost.d
      - nginx_proxy_html:/usr/share/nginx/html
      - nginx_proxy_acme:/etc/acme.sh
    networks:
      - proxy
    restart: unless-stopped
    environment:
      - DEFAULT_EMAIL=${{LETSENCRYPT_EMAIL:-}}
      - NGINX_PROXY_CONTAINER=nginx-proxy{acme_ca_env}
    depends_on:
      - nginx-proxy

"""
    
    # Вставляем перед volumes
    content = re.sub(r'(\nvolumes:)', r'\n' + nginx_proxy_section + r'\1', content)
    
    # Добавляем volumes для nginx-proxy
    nginx_volumes = """  nginx_proxy_certs:
    driver: local
  nginx_proxy_vhost:
    driver: local
  nginx_proxy_html:
    driver: local
  nginx_proxy_acme:
    driver: local
"""
    # Добавляем volumes после последнего volume или перед networks
    if '  ollama_data:' in content:
        content = re.sub(r'(  ollama_data:\s*driver: local\n)', r'\1' + nginx_volumes, content)
    else:
        # Если ollama_data нет, добавляем перед networks
        content = re.sub(r'(\nnetworks:)', r'\n' + nginx_volumes + r'\1', content)
    
    return content


def add_nginx_proxy_env_vars(content: str, config: Dict) -> str:
    """Добавляет переменные окружения VIRTUAL_HOST и LETSENCRYPT_HOST для nginx-proxy"""
    import re
    
    n8n_enabled = config.get('n8n_enabled', True)
    langflow_enabled = config.get('langflow_enabled', True)
    ollama_enabled = config.get('ollama_enabled', False)
    
    n8n_domain = config.get('n8n_domain', '') or ''
    langflow_domain = config.get('langflow_domain', '') or ''
    supabase_domain = config.get('supabase_domain', '') or ''
    ollama_domain = config.get('ollama_domain', '') or ''
    letsencrypt_email = config.get('letsencrypt_email', '') or ''
    
    # Добавляем переменные для n8n
    if n8n_enabled and n8n_domain:
        env_vars = f'      - VIRTUAL_HOST={n8n_domain}\n'
        if letsencrypt_email:
            env_vars += f'      - LETSENCRYPT_HOST={n8n_domain}\n'
        # Находим секцию n8n и добавляем после environment
        pattern = r'(\s+n8n:[^\n]*\n(?:(?!\s+environment:)[^\n]*\n)*?\s+environment:\s*\n)'
        replacement = r'\1' + env_vars
        content = re.sub(pattern, replacement, content)
    
    # Добавляем переменные для langflow
    if langflow_enabled and langflow_domain:
        env_vars = f'      - VIRTUAL_HOST={langflow_domain}\n'
        if letsencrypt_email:
            env_vars += f'      - LETSENCRYPT_HOST={langflow_domain}\n'
        pattern = r'(\s+langflow:[^\n]*\n(?:(?!\s+environment:)[^\n]*\n)*?\s+environment:\s*\n)'
        replacement = r'\1' + env_vars
        content = re.sub(pattern, replacement, content)
    
    # Добавляем переменные для supabase-studio
    if supabase_domain:
        env_vars = f'      - VIRTUAL_HOST={supabase_domain}\n'
        if letsencrypt_email:
            env_vars += f'      - LETSENCRYPT_HOST={supabase_domain}\n'
        pattern = r'(\s+supabase-studio:[^\n]*\n(?:(?!\s+environment:)[^\n]*\n)*?\s+environment:\s*\n)'
        replacement = r'\1' + env_vars
        content = re.sub(pattern, replacement, content)
    
    # Добавляем переменные для ollama
    if ollama_enabled and ollama_domain:
        env_vars = f'      - VIRTUAL_HOST={ollama_domain}\n'
        if letsencrypt_email:
            env_vars += f'      - LETSENCRYPT_HOST={ollama_domain}\n'
        pattern = r'(\s+ollama:[^\n]*\n(?:(?!\s+environment:)[^\n]*\n)*?\s+environment:\s*\n)'
        replacement = r'\1' + env_vars
        content = re.sub(pattern, replacement, content)
    
    return content


def hash_password_for_caddy(password: str) -> str:
    """
    Генерирует bcrypt хеш пароля для Caddy basicauth
    Использует команду caddy hash-password если доступна, иначе использует bcrypt
    Возвращает хеш в base64 кодировке для избежания символов $ в .env файле
    """
    import base64
    
    # Пытаемся использовать caddy hash-password (если Caddy установлен локально)
    try:
        result = subprocess.run(
            ['caddy', 'hash-password', '--plaintext', password],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            bcrypt_hash = result.stdout.strip()
            # Кодируем в base64 чтобы убрать символы $
            return base64.b64encode(bcrypt_hash.encode('utf-8')).decode('utf-8')
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Если caddy недоступен, используем bcrypt через Python
    try:
        import bcrypt
        # Генерируем bcrypt хеш с cost factor 10 (стандарт для Caddy)
        salt = bcrypt.gensalt(rounds=10)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        bcrypt_hash = hashed.decode('utf-8')
        # Кодируем в base64 чтобы убрать символы $
        return base64.b64encode(bcrypt_hash.encode('utf-8')).decode('utf-8')
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
                bcrypt_hash = result.stdout.strip()
                # Кодируем в base64 чтобы убрать символы $
                return base64.b64encode(bcrypt_hash.encode('utf-8')).decode('utf-8')
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Если ничего не работает, возвращаем пустую строку и выводим предупреждение
        # Пользователю нужно будет вручную сгенерировать хеш
        print(f"⚠️  Не удалось автоматически сгенерировать хеш пароля для Caddy basicauth.")
        print(f"   Установите bcrypt: pip install bcrypt")
        print(f"   Или используйте команду: docker run --rm caddy:latest caddy hash-password --plaintext '{password}'")
        return ''


def decode_password_hash(encoded_hash: str) -> str:
    """
    Декодирует base64-закодированный bcrypt хеш обратно в оригинальный формат
    Используется при генерации Caddyfile
    """
    import base64
    if not encoded_hash:
        return ''
    try:
        return base64.b64decode(encoded_hash.encode('utf-8')).decode('utf-8')
    except Exception:
        # Если декодирование не удалось, возможно это уже оригинальный хеш (для обратной совместимости)
        return encoded_hash


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
    letsencrypt_staging = config.get('letsencrypt_staging', False)
    
    # Проверяем какие сервисы включены (по умолчанию False для безопасности)
    n8n_enabled = config.get('n8n_enabled', False)
    langflow_enabled = config.get('langflow_enabled', False)
    ollama_enabled = config.get('ollama_enabled', False)
    # Supabase всегда включен
    
    # Получаем домены только для включенных сервисов
    if n8n_enabled:
        n8n_domain = config.get('n8n_domain', '') or 'localhost'
    else:
        n8n_domain = ''
    
    if langflow_enabled:
        langflow_domain = config.get('langflow_domain', '') or 'localhost'
    else:
        langflow_domain = ''
    
    supabase_domain = config.get('supabase_domain', '') or 'localhost'
    
    if ollama_enabled:
        ollama_domain = config.get('ollama_domain', '') or 'localhost'
    else:
        ollama_domain = ''
    
    # Если режим поддоменов, используем домены, иначе localhost
    if routing_mode == 'subdomain':
        # Используем реальные домены только для включенных сервисов
        if n8n_enabled:
            n8n_domain = n8n_domain or 'n8n.localhost'
        if langflow_enabled:
            langflow_domain = langflow_domain or 'langflow.localhost'
        supabase_domain = supabase_domain or 'supabase.localhost'
        if ollama_enabled:
            ollama_domain = ollama_domain or 'ollama.localhost'
    else:
        # Для режима портов не используем Caddy, но оставляем localhost для совместимости
        if n8n_enabled:
            n8n_domain = 'localhost'
        if langflow_enabled:
            langflow_domain = 'localhost'
        supabase_domain = 'localhost'
        if ollama_enabled:
            ollama_domain = 'localhost'
    
    # Генерируем хеш пароля для Supabase Studio basicauth
    supabase_admin_login = config.get('supabase_admin_login', 'admin')
    supabase_admin_password = config.get('supabase_admin_password', '')
    # Используем уже сгенерированный хеш из конфига, если есть
    supabase_password_hash_encoded = config.get('supabase_admin_password_hash', '')
    
    # Если хеш не задан, но есть пароль - генерируем хеш (в base64)
    if not supabase_password_hash_encoded and supabase_admin_password:
        supabase_password_hash_encoded = hash_password_for_caddy(supabase_admin_password)
    
    # Декодируем base64 хеш для использования в Caddyfile (Caddy требует оригинальный bcrypt формат)
    supabase_password_hash = decode_password_hash(supabase_password_hash_encoded) if supabase_password_hash_encoded else ''
    
    # Если хеш не сгенерирован, удаляем секцию basic_auth из Supabase Studio
    if not supabase_password_hash:
        import re
        # Удаляем блок basic_auth для Supabase Studio
        basicauth_pattern = r'    basic_auth \{[^}]*\{SUPABASE_ADMIN_LOGIN\}[^}]*\{SUPABASE_ADMIN_PASSWORD_HASH\}[^}]*\}\n'
        content = re.sub(basicauth_pattern, '', content)
    
    # Добавляем acme_ca для staging если выбрано
    if letsencrypt_staging:
        # Ищем глобальный блок и добавляем staging acme_ca
        global_block_pattern = r'(\{\s*\n\s*email\s+\{[^}]+\}\s*\n?)(.*?)(\})'
        
        def add_staging_acme(match):
            email_line = match.group(1)  # "    email {CADDY_EMAIL}\n"
            rest = match.group(2)  # остальное содержимое
            footer = match.group(3)  # "}"
            
            # Удаляем старые acme_ca если есть
            rest = re.sub(r'\s+acme_ca\s+[^\n]+\n?', '', rest)
            rest = re.sub(r'\s+# Let\'s Encrypt.*?\n', '', rest, flags=re.MULTILINE)
            rest = re.sub(r'\s+# Caddy автоматически.*?\n', '', rest, flags=re.MULTILINE)
            
            # Добавляем staging
            staging_config = '    # Let\'s Encrypt Staging - для тестирования (более высокие лимиты)\n'
            staging_config += '    # ⚠ Staging сертификаты НЕ доверяются браузерами!\n'
            staging_config += '    acme_ca https://acme-staging-v02.api.letsencrypt.org/directory\n'
            staging_config += '    # Caddy автоматически перенаправляет HTTP на HTTPS\n'
            
            rest = staging_config + rest
            return f"{email_line}{rest}{footer}"
        
        content = re.sub(global_block_pattern, add_staging_acme, content, flags=re.DOTALL)
    
    # Заменяем переменные (только для включенных сервисов)
    replacements = {
        'CADDY_EMAIL': letsencrypt_email or 'admin@example.com',
        'N8N_DOMAIN': n8n_domain if n8n_enabled else '',
        'LANGFLOW_DOMAIN': langflow_domain if langflow_enabled else '',
        'SUPABASE_DOMAIN': supabase_domain,
        'OLLAMA_DOMAIN': ollama_domain if ollama_enabled else '',
        'SUPABASE_ADMIN_LOGIN': supabase_admin_login,
        'SUPABASE_ADMIN_PASSWORD_HASH': supabase_password_hash,  # Используем декодированный хеш для Caddyfile
    }
    
    # Заменяем все переменные
    for key, value in replacements.items():
        content = content.replace(f'{{{key}}}', str(value))
    
    import re
    
    # Удаляем секции для невыбранных сервисов или если домен пустой
    # Важно: проверяем после замены переменных, чтобы удалить блоки с пустыми доменами
    if not n8n_enabled or not n8n_domain or n8n_domain == 'localhost':
        # Удаляем блок n8n (от # N8N до следующего блока или конца)
        n8n_pattern = r'# N8N.*?(?=\n# [A-Z]|\n\n\n|\Z)'
        content = re.sub(n8n_pattern, '', content, flags=re.DOTALL)
    
    if not langflow_enabled or not langflow_domain or langflow_domain == 'localhost':
        # Удаляем блок langflow (от # Langflow до следующего блока или конца)
        langflow_pattern = r'# Langflow.*?(?=\n# [A-Z]|\n\n\n|\Z)'
        content = re.sub(langflow_pattern, '', content, flags=re.DOTALL)
    
    # Удаляем секцию Ollama если она не включена или домен пустой
    if not ollama_enabled or not ollama_domain or ollama_domain == 'localhost':
        ollama_pattern = r'# Ollama.*?(?=\n# [A-Z]|\n\n\n|\Z)'
        content = re.sub(ollama_pattern, '', content, flags=re.DOTALL)
    
    # Удаляем пустые строки (более 2 подряд)
    content = re.sub(r'\n{3,}', '\n\n', content)
    
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

